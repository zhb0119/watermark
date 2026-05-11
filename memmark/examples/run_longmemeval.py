from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any, Dict

from memmark.backends import JsonMemoryStore
from memmark.baselines import build_baseline
from memmark.benchmarks.longmemeval import LongMemEvalDriver, load_longmemeval
from memmark.benchmarks.longmemeval.driver import result_to_jsonable


BASELINE_LABELS = ("watermark", "no_watermark", "signed_metadata_only", "random_replace")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", required=True)
    parser.add_argument("--output-dir", default="results/longmemeval")
    parser.add_argument("--backend", choices=("json", "amem", "graphiti"), default="amem")
    parser.add_argument("--baselines", nargs="+", default=list(BASELINE_LABELS))
    parser.add_argument("--payload-bits", default="1011010011" * 4)
    parser.add_argument("--secret-key", default=os.getenv("MEMMARK_KEY", "memmark-default-dev-key"))
    parser.add_argument("--amem-model-name", default="all-MiniLM-L6-v2")
    parser.add_argument("--max-examples", type=int)
    parser.add_argument("--start", type=int, default=0)
    parser.add_argument("--max-sessions", type=int)
    parser.add_argument("--max-turns-per-session", type=int)
    parser.add_argument("--ingestion-level", choices=("turn", "session"), default="session")
    parser.add_argument("--topk-context", type=int, default=10)
    parser.add_argument("--max-context-chars", type=int, default=12000)
    parser.add_argument("--llm-mode", choices=("real",), default="real")
    parser.add_argument("--progress", action="store_true")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    examples = load_longmemeval(args.input)
    end = None if args.max_examples is None else args.start + args.max_examples
    examples = examples[args.start:end]
    if not examples:
        raise SystemExit("No LongMemEval examples selected.")
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = Path(args.input).stem
    for label in args.baselines:
        llm_client = _build_llm_client()
        backend = _build_backend(args.backend, args.amem_model_name)
        wm = build_baseline(
            label,
            backend=backend,
            payload_bits=args.payload_bits,
            agent_id=f"memmark-longmemeval-{label}",
            user_id="memmark-user",
            session_id=f"longmemeval-{stem}-{label}",
            secret_key=args.secret_key,
        )
        driver = LongMemEvalDriver(
            watermarker=wm,
            llm_client=llm_client,
            topk_context=args.topk_context,
            ingestion_level=args.ingestion_level,
            max_sessions=args.max_sessions,
            max_turns_per_session=args.max_turns_per_session,
            max_context_chars=args.max_context_chars,
            progress=args.progress,
            progress_context={"baseline": label},
        )
        hyp_path = output_dir / f"{stem}_{label}.jsonl"
        detail_path = output_dir / f"{stem}_{label}.json"
        details = []
        with hyp_path.open("w", encoding="utf-8") as hyp_f:
            for item_i, example in enumerate(examples, start=1):
                if args.progress:
                    print(f"[example] baseline={label} {item_i}/{len(examples)} qid={example.question_id}", flush=True)
                result = driver.run(example)
                details.append(result_to_jsonable(result))
                print(json.dumps({"question_id": result.question_id, "hypothesis": result.hypothesis}, ensure_ascii=False), file=hyp_f, flush=True)
                _write_detail(detail_path, args, stem, label, details)
        _write_detail(detail_path, args, stem, label, details)
        print(f"[{label}] hypothesis={hyp_path} details={detail_path}")


def _build_llm_client():
    from memmark.llm import OpenAIChatClient

    return OpenAIChatClient()


def _build_backend(name: str, amem_model_name: str):
    if name == "json":
        return JsonMemoryStore()
    if name == "amem":
        from memmark.backends import load_amem

        return load_amem(model_name=amem_model_name)
    if name == "graphiti":
        from memmark.backends import load_graphiti

        return load_graphiti()
    raise ValueError(f"Unknown backend: {name}")


def _write_detail(path: Path, args: argparse.Namespace, stem: str, baseline: str, details: list[Dict[str, Any]]) -> None:
    out = {
        "config": vars(args),
        "dataset": {"name": stem, "examples_completed": len(details)},
        "baseline": baseline,
        "summary": _summary(details),
        "details": details,
    }
    path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")


def _summary(details: list[Dict[str, Any]]) -> Dict[str, Any]:
    if not details:
        return {"examples": 0, "write_failures": 0, "bits_embedded": 0, "audits_count": 0}
    return {
        "examples": len(details),
        "write_failures": sum(int(item.get("write_failures") or 0) for item in details),
        "bits_embedded": sum(int(item.get("bits_embedded") or 0) for item in details),
        "audits_count": sum(int(item.get("audits_count") or 0) for item in details),
        "memory_records_last": len(details[-1].get("memory_snapshot_final") or []),
    }


if __name__ == "__main__":
    main()
