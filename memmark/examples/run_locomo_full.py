"""End-to-end smoke for MemMark on LoCoMo.

Runs all 5 RQs (utility / capacity / R1+R2+R3 / robustness / integrity)
on a single LoCoMo conversation. Default backend is JsonMemoryStore so
this works with no external services; pass `--backend cognee|amem|graphiti`
to use the real SDK once the corresponding service is up.

Usage:
    python -m memmark.examples.run_locomo_full \\
        --locomo /Users/.../locomo/data/locomo10.json \\
        --conversation 0 \\
        --max-sessions 2 \\
        --max-qa 20 \\
        --backend json \\
        --output /tmp/memmark_locomo.json
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any, Dict

from memmark.backends import JsonMemoryStore
from memmark.baselines import build_baseline
from memmark.benchmarks.locomo import LoCoMoDriver, load_locomo
from memmark.benchmarks.locomo.driver import keyword_memory_extractor
from memmark.experiments import (
    run_rq1_utility,
    run_rq2_capacity,
    run_rq3_in_record,
    run_rq4_robustness,
    run_rq5_integrity,
)


BASELINE_LABELS = ("watermark", "no_watermark", "signed_metadata_only", "random_replace")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--locomo",
        default=os.getenv("MEMMARK_LOCOMO_PATH", "locomo/data/locomo10.json"),
    )
    parser.add_argument("--conversation", type=int, default=0)
    parser.add_argument("--max-sessions", type=int, default=2)
    parser.add_argument("--max-qa", type=int, default=20)
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
    for label in args.baselines:
        backend = _build_backend(args.backend)
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
            memory_extractor=keyword_memory_extractor,
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

    # RQ1 — Utility
    rq1 = run_rq1_utility(runs=runs)

    # RQ2 — Capacity (use the watermark run as the headline; report all)
    rq2 = {label: run_rq2_capacity(r) for label, r in runs.items()}

    # RQ3 — R1/R2/R3 verification (only meaningful with watermark mode)
    rq3 = {}
    if "watermark" in runs:
        rq3["watermark"] = run_rq3_in_record(
            driver_result=runs["watermark"],
            secret_key=args.secret_key,
        )
    if "signed_metadata_only" in runs:
        rq3["signed_metadata_only"] = run_rq3_in_record(
            driver_result=runs["signed_metadata_only"],
            secret_key=args.secret_key,
        )

    # RQ4 — robustness against memory-specific attacks
    rq4 = {}
    if "watermark" in runs:
        rq4["watermark"] = run_rq4_robustness(
            driver_result=runs["watermark"],
            secret_key=args.secret_key,
        )

    # RQ5 — integrity
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
