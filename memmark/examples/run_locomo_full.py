"""End-to-end runner for MemMark on LoCoMo.

Two LLM modes (the diff that turns this from a smoke into a paper run):

  --llm-mode stub  (default)  — extractor / carrier / QA all rule-based.
                                Zero API cost; smoke only.
  --llm-mode real             — LLM抽事实 + LLM 生成/打分候选 + LLM 答 QA.
                                这是"图里那 9 步"真实路径,跑 paper 用这个.

Backends:
  --backend json|amem|graphiti

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
from typing import Any, Dict, Optional  # noqa: F401

from memmark.backends import JsonMemoryStore
from memmark.baselines import build_baseline
from memmark.benchmarks.locomo import LoCoMoDriver, load_locomo
from memmark.benchmarks.locomo.qa_eval import (
    make_locomo_qa_judge,
    make_locomo_qa_responder,
)


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
        choices=("json", "amem", "graphiti"),
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
    parser.add_argument("--amem-model-name", default="all-MiniLM-L6-v2")
    parser.add_argument("--output", default="memmark_locomo_results.json")
    parser.add_argument("--async-assess", action="store_true")
    parser.add_argument("--async-max-concurrency", type=int, default=4)
    parser.add_argument(
        "--llm-mode",
        choices=("stub", "real"),
        default="stub",
        help=(
            "stub = no LLM (zero API cost; only viable with the JsonStore "
            "backend for plumbing checks). "
            "real = configure an OpenAI-compatible client; backends use it "
            "for their own internal evolution and we use it for fact "
            "extraction + QA. Required for paper numbers."
        ),
    )
    parser.add_argument("--progress", action="store_true")
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

    runs = {}
    for run_i, label in enumerate(args.baselines, start=1):
        # Per-baseline isolation: rebuild backend + LLM client +
        # qa_responder + qa_judge from scratch for every baseline. We
        # observed cross-baseline pollution where running watermark
        # then no_watermark left the shared LLM client / wrapper in a
        # state that caused signed_metadata_only and random_replace to
        # produce empty answers across all 196 questions on conv 8.
        # Cheap to rebuild (just wraps env API key); buys us provable
        # independence between baselines and is easier to reason about
        # than auditing every shared object's lifecycle.
        llm_client, qa_responder, qa_judge, _ = _build_qa_layer(args.llm_mode)
        backend = _build_backend(args.backend, args.amem_model_name)
        wm = build_baseline(
            label,
            backend=backend,
            payload_bits=args.payload_bits,
            agent_id=f"memmark-{label}",
            user_id="memmark-user",
            session_id=f"locomo-{conv.sample_id}-{label}",
            secret_key=args.secret_key,
        )
        driver = LoCoMoDriver(
            watermarker=wm,
            qa_responder=qa_responder,
            qa_judge=qa_judge,
            max_sessions=args.max_sessions,
            max_qa=args.max_qa,
            fact_extractor_llm=llm_client,
            async_assess=args.async_assess,
            async_max_concurrency=args.async_max_concurrency,
            progress=args.progress,
            progress_context={
                "conversation": args.conversation,
                "baseline": label,
            },
        )
        result = driver.run(conv)
        runs[label] = result
        print(
            f"[{label}] decisions={len(result.audits)} "
            f"bits_embedded={result.bits_embedded_total} "
            f"qa={len(result.qa_predictions)} "
            f"f1={result.qa_f1_mean:.3f} "
            f"bleu1={result.qa_bleu1_mean:.3f} "
            f"rougeL={result.qa_rougeL_mean:.3f}"
        )
        if args.progress:
            print(f"[run:{run_i}/{len(args.baselines)}:done] baseline={label}", flush=True)
        _write_baseline_checkpoint(args, conv, runs)

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

    details = {label: _run_details(r) for label, r in runs.items()}

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
        "details": details,
    }
    final_path = Path(args.output)
    final_path.parent.mkdir(parents=True, exist_ok=True)
    final_path.write_text(
        json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\nResults saved to {args.output}")
    if "watermark" in rq3:
        report = rq3["watermark"]
        print("\n=== Headline (R3 In-Record Attribution) ===")
        print(json.dumps(_to_jsonable(report), indent=2, ensure_ascii=False))


def _build_qa_layer(mode: str):
    """Return (llm_client, qa_responder, qa_judge, fact_extractor).

    The watermark no longer needs an external carrier planner — bits
    are embedded by ``WatermarkedSampler`` intercepting each backend's
    own internal LLM calls. We only need an LLM client for:

      * QA responder    — answers LoCoMo questions from the rendered
                          memory context (LoCoMo official prompt).
      * fact_extractor  — runs ``CONVERSATION2FACTS_PROMPT`` for the
                          ``fact``-mode ingestion path (A-MEM /
                          Mem0 protocol).

    QA judge is the LoCoMo official F1≥0.5 / cat-5 abstention rule;
    not an LLM-judge.
    """

    if mode == "stub":
        return None, None, None, None

    from memmark.llm import OpenAIChatClient

    llm_client = OpenAIChatClient()
    qa_responder = make_locomo_qa_responder(llm_client)
    qa_judge = make_locomo_qa_judge()
    return llm_client, qa_responder, qa_judge, llm_client


def _build_backend(name: str, amem_model_name: str):
    if name == "json":
        return JsonMemoryStore()
    if name == "amem":
        from memmark.backends import load_amem

        return load_amem(model_name=amem_model_name)
    if name == "cognee":
        from memmark.backends import load_cognee

        return load_cognee()
    if name == "graphiti":
        from memmark.backends import load_graphiti

        return load_graphiti()
    raise ValueError(f"Unknown backend: {name}")


def _write_baseline_checkpoint(args, conv, runs) -> None:
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    checkpoint_path = out_path.with_suffix(out_path.suffix + ".partial")
    latest_label = next(reversed(runs))
    baseline_path = out_path.with_name(
        f"{out_path.stem}_{latest_label}{out_path.suffix}"
    )
    baseline_out: Dict[str, Any] = {
        "config": vars(args),
        "conversation": {
            "sample_id": conv.sample_id,
            "session_count": len(conv.sessions),
            "qa_count": len(conv.qa),
        },
        "baseline": latest_label,
        "details": {latest_label: _run_details(runs[latest_label])},
    }
    out: Dict[str, Any] = {
        "config": vars(args),
        "conversation": {
            "sample_id": conv.sample_id,
            "session_count": len(conv.sessions),
            "qa_count": len(conv.qa),
        },
        "completed_baselines": list(runs.keys()),
        "details": {label: _run_details(r) for label, r in runs.items()},
    }
    checkpoint_path.write_text(
        json.dumps(_to_jsonable(out), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    baseline_path.write_text(
        json.dumps(_to_jsonable(baseline_out), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    out_path.write_text(
        json.dumps(_to_jsonable(out), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(
        f"[checkpoint] saved baseline={latest_label} to {baseline_path}; "
        f"completed_baselines={list(runs.keys())} to {checkpoint_path}"
    )


def _run_details(result) -> Dict[str, Any]:
    return _to_jsonable(
        {
            "summary": {
                "decisions": len(result.audits),
                "bits_embedded": result.bits_embedded_total,
                "qa_count": len(result.qa_predictions),
                "qa_accuracy": result.qa_accuracy,
                "qa_f1_mean": result.qa_f1_mean,
                "qa_bleu1_mean": result.qa_bleu1_mean,
                "qa_rougeL_mean": result.qa_rougeL_mean,
                "qa_judge_accuracy": result.qa_judge_accuracy,
                "qa_metrics_by_category": result.qa_metrics_by_category,
                "memory_count": len(result.memory_snapshot_final),
            },
            "qa_predictions": result.qa_predictions,
            "memory_snapshot_final": result.memory_snapshot_final,
            "extracted_events": result.extracted_events,
            "decisions": result.decisions,
            "audits": result.audits,
            "anchor": result.anchor,
        }
    )


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
