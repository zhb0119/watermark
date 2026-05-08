"""End-to-end runner for MemMark on LoCoMo.

Two LLM modes (the diff that turns this from a smoke into a paper run):

  --llm-mode stub  (default)  — extractor / carrier / QA all rule-based.
                                Zero API cost; smoke only.
  --llm-mode real             — LLM抽事实 + LLM 生成/打分候选 + LLM 答 QA.
                                这是"图里那 9 步"真实路径,跑 paper 用这个.

Backends:
  --backend json|amem|cognee|graphiti

Example (paper-quality 1 cell):

    export MEMMARK_API_KEY=...  MEMMARK_BASE_URL=...  MEMMARK_MODEL=...
    python -m memmark.examples.run_locomo_full \\
        --llm-mode real \\
        --backend amem \\
        --conversation 0 \\
        --baselines watermark no_watermark signed_metadata_only \\
        --output ./results/conv0_amem_real.json
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from memmark.backends import JsonMemoryStore
from memmark.baselines import build_baseline
from memmark.benchmarks.locomo import LoCoMoDriver, load_locomo
from memmark.benchmarks.locomo.driver import keyword_memory_extractor


BASELINE_LABELS = ("watermark", "no_watermark", "signed_metadata_only", "random_replace")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--locomo",
        default=os.getenv("MEMMARK_LOCOMO_PATH", "locomo/data/locomo10.json"),
    )
    parser.add_argument("--conversation", type=int, default=0)
    parser.add_argument(
        "--max-sessions",
        type=int,
        default=2,
        help="Cap sessions to keep smoke fast. Pass a large value (e.g. 999) for full LoCoMo.",
    )
    parser.add_argument(
        "--max-qa",
        type=int,
        default=20,
        help="Cap QA per conversation. Pass 9999 for full LoCoMo.",
    )
    parser.add_argument(
        "--backend",
        choices=("json", "cognee", "amem", "graphiti"),
        default="json",
    )
    parser.add_argument(
        "--baselines",
        nargs="+",
        default=list(BASELINE_LABELS),
        help="Which baselines to run on the same conversation.",
    )
    parser.add_argument("--payload-bits", default="1011010011" * 4)
    parser.add_argument(
        "--secret-key",
        default=os.getenv("MEMMARK_KEY", "memmark-default-dev-key"),
    )
    parser.add_argument("--output", default="memmark_locomo_results.json")
    parser.add_argument(
        "--llm-mode",
        choices=("stub", "real"),
        default="stub",
        help=(
            "stub = rule-based extractor / static paraphrase carriers / "
            "substring QA judge (zero API cost, smoke only). "
            "real = LLM extractor + LLMCarrierPlanner + LLM QA responder. "
            "Required for paper numbers."
        ),
    )
    parser.add_argument(
        "--async-assess",
        action="store_true",
        help=(
            "(real mode) fan out the 3 carrier-feasibility prompts in parallel "
            "via AsyncOpenAIChatClient. ~2x speedup."
        ),
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()

    conversations = load_locomo(args.locomo)
    if args.conversation >= len(conversations):
        raise SystemExit(
            f"--conversation {args.conversation} out of range "
            f"(0..{len(conversations) - 1})"
        )
    conv = conversations[args.conversation]

    # Build LLM client + extractor + carrier planner + QA responder once,
    # share across baselines.
    llm_client, extractor, planner_factory, qa_responder, qa_judge = _build_llm_layer(
        args.llm_mode, async_assess=args.async_assess
    )

    runs = {}
    for label in args.baselines:
        backend = _build_backend(args.backend)
        carrier_planner = planner_factory() if planner_factory else None
        wm = build_baseline(
            label,
            backend=backend,
            payload_bits=args.payload_bits,
            agent_id=f"memmark-{label}",
            user_id="memmark-user",
            session_id=f"locomo-{conv.sample_id}-{label}",
            secret_key=args.secret_key,
            carrier_planner=carrier_planner,
        )
        driver = LoCoMoDriver(
            watermarker=wm,
            memory_extractor=extractor,
            qa_responder=qa_responder,
            qa_judge=qa_judge,
            max_sessions=args.max_sessions,
            max_qa=args.max_qa,
        )
        result = driver.run(conv)
        runs[label] = result
        print(
            f"[{label}] decisions={len(result.audits)} "
            f"bits_embedded={result.bits_embedded_total} "
            f"qa={len(result.qa_predictions)} acc={result.qa_accuracy:.3f}"
        )

    # Lazy-import RQ runners (they pull torch via decoder→AgentMark)
    from memmark.experiments import (
        run_rq1_utility,
        run_rq2_capacity,
        run_rq3_in_record,
        run_rq4_robustness,
        run_rq5_integrity,
    )

    rq1 = run_rq1_utility(runs=runs)
    rq2 = {label: run_rq2_capacity(r) for label, r in runs.items()}

    rq3 = {}
    if "watermark" in runs:
        rq3["watermark"] = run_rq3_in_record(
            driver_result=runs["watermark"], secret_key=args.secret_key
        )
    if "signed_metadata_only" in runs:
        rq3["signed_metadata_only"] = run_rq3_in_record(
            driver_result=runs["signed_metadata_only"], secret_key=args.secret_key
        )

    rq4 = {}
    if "watermark" in runs:
        rq4["watermark"] = run_rq4_robustness(
            driver_result=runs["watermark"], secret_key=args.secret_key
        )

    rq5 = {label: run_rq5_integrity(r) for label, r in runs.items()}

    out: Dict[str, Any] = {
        "config": vars(args),
        "conversation": {
            "sample_id": conv.sample_id,
            "session_count": len(conv.sessions),
            "qa_count": len(conv.qa),
        },
        "rq1_utility": _to_jsonable(rq1),
        "rq2_capacity": {k: _to_jsonable(v) for k, v in rq2.items()},
        "rq3_in_record": {k: _to_jsonable(v) for k, v in rq3.items()},
        "rq4_robustness": {k: _to_jsonable(v) for k, v in rq4.items()},
        "rq5_integrity": {k: _to_jsonable(v) for k, v in rq5.items()},
    }
    Path(args.output).write_text(
        json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\nResults saved to {args.output}")
    if "watermark" in rq3:
        report = rq3["watermark"]
        print("\n=== Headline (R3 In-Record Attribution) ===")
        print(json.dumps(_to_jsonable(report), indent=2, ensure_ascii=False))


def _build_llm_layer(mode: str, *, async_assess: bool):
    """Return (llm_client, extractor, planner_factory, qa_responder, qa_judge)."""

    if mode == "stub":
        return None, keyword_memory_extractor, None, None, None

    # mode == "real"
    from memmark.carriers.planner import LLMCarrierPlanner
    from memmark.carriers.semantic_realization import SemanticRealizationCarrier
    from memmark.llm import OpenAIChatClient

    if async_assess:
        from memmark.llm import AsyncOpenAIChatClient

        llm_client = AsyncOpenAIChatClient()
    else:
        llm_client = OpenAIChatClient()

    extractor = _make_llm_extractor(llm_client)
    fallback = SemanticRealizationCarrier()

    def planner_factory():
        return LLMCarrierPlanner(
            llm_client=llm_client,
            fallback_carrier=fallback,
            merge_gen_and_score=True,
            async_assess=async_assess,
        )

    qa_responder = _make_llm_qa_responder(llm_client)
    qa_judge = _make_llm_qa_judge(llm_client)
    return llm_client, extractor, planner_factory, qa_responder, qa_judge


def _make_llm_extractor(llm_client):
    """Step 3 in the diagram: LLM extracts durable facts from a turn."""

    def extractor(turn, session_summary):
        text = (turn.text or "").strip()
        if not text:
            return []
        prompt = [
            {
                "role": "system",
                "content": (
                    "Extract durable long-term memory facts from this dialog turn. "
                    "Include stable preferences, plans, identity, dated events, "
                    "concrete numbers, locations. Skip greetings / chitchat. "
                    'Return strict JSON array of strings (e.g. ["..."]). '
                    "Return [] if nothing durable."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Speaker: {turn.speaker}\n"
                    f"DiaID: {turn.dia_id}\n"
                    f"Text: {text}\n"
                    f"Session summary: {session_summary or '(none)'}"
                ),
            },
        ]
        try:
            raw = llm_client.complete(prompt, temperature=0.0)
        except Exception:
            return []
        return _parse_str_array(raw)

    return extractor


def _make_llm_qa_responder(llm_client):
    """Step 8 in the diagram: answer QA using ONLY the memory snapshot."""

    def responder(question, memory_snapshot):
        prompt = [
            {
                "role": "system",
                "content": (
                    "You are a forensic auditor answering questions ONLY from "
                    "the long-term memory snapshot below. Be concise. If the "
                    "answer is not in memory, reply exactly: I don't know."
                ),
            },
            {
                "role": "user",
                "content": (
                    "Memory snapshot (JSON):\n"
                    f"{json.dumps(memory_snapshot, ensure_ascii=False)[:6000]}\n\n"
                    f"Question: {question.question}\n"
                    "Answer (concise):"
                ),
            },
        ]
        try:
            return llm_client.complete(prompt, temperature=0.0).strip()
        except Exception:
            return ""

    return responder


def _make_llm_qa_judge(llm_client):
    """LLM-as-judge for fuzzy match against gold answer.

    Falls back to simple substring match if the LLM call fails.
    """

    def judge(question, answer):
        if not answer:
            return False
        gold = (question.answer or "").strip()
        if not gold:
            return False
        # Cheap pre-check: exact / substring
        if gold.lower() in answer.lower() or answer.lower() in gold.lower():
            return True
        prompt = [
            {
                "role": "system",
                "content": (
                    "You judge whether a predicted answer is consistent with the gold answer. "
                    "Return strict JSON: {\"correct\": true} or {\"correct\": false}."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Question: {question.question}\n"
                    f"Gold: {gold}\n"
                    f"Predicted: {answer}"
                ),
            },
        ]
        try:
            raw = llm_client.complete(prompt, temperature=0.0)
            parsed = _parse_json_obj(raw)
            return bool(parsed.get("correct"))
        except Exception:
            return False

    return judge


def _parse_str_array(raw: str) -> List[str]:
    text = (raw or "").strip()
    if not text:
        return []
    start = text.find("[")
    end = text.rfind("]")
    if start < 0 or end < start:
        return []
    try:
        data = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return []
    out: List[str] = []
    if isinstance(data, list):
        for item in data:
            if isinstance(item, str) and item.strip():
                out.append(item.strip())
            elif isinstance(item, dict):
                v = item.get("text") or item.get("fact") or item.get("memory")
                if isinstance(v, str) and v.strip():
                    out.append(v.strip())
    return out


def _parse_json_obj(raw: str) -> dict:
    text = (raw or "").strip()
    if not text:
        return {}
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < start:
        return {}
    try:
        return json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return {}


def _build_backend(name: str):
    if name == "json":
        return JsonMemoryStore()
    if name == "amem":
        from memmark.backends import load_amem

        return load_amem()
    if name == "cognee":
        from memmark.backends import load_cognee

        return load_cognee()
    if name == "graphiti":
        from memmark.backends import load_graphiti

        return load_graphiti()
    raise ValueError(f"Unknown backend: {name}")


def _to_jsonable(obj: Any) -> Any:
    if is_dataclass(obj):
        return {k: _to_jsonable(v) for k, v in asdict(obj).items()}
    if isinstance(obj, (list, tuple)):
        return [_to_jsonable(v) for v in obj]
    if isinstance(obj, dict):
        return {str(k): _to_jsonable(v) for k, v in obj.items()}
    if hasattr(obj, "_asdict"):
        return _to_jsonable(obj._asdict())
    if hasattr(obj, "__dict__") and not isinstance(obj, type):
        return _to_jsonable(obj.__dict__)
    return obj


if __name__ == "__main__":
    main()
