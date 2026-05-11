from __future__ import annotations

import argparse
import importlib.util
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
    parser.add_argument("--rq-metrics", action="store_true")
    parser.add_argument("--longmemeval-root", default=os.getenv("LONGMEMEVAL_ROOT"))
    parser.add_argument("--judge-timeout", type=float, default=float(os.getenv("OPENROUTER_TIMEOUT", "30")))
    parser.add_argument("--judge-model", default="gpt-4o")
    parser.add_argument("--judge-base-url", default=os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1"))
    parser.add_argument("--judge-api-key", default=os.getenv("OPENROUTER_API_KEY"))
    parser.add_argument("--judge-provider-model", default=os.getenv("OPENROUTER_MODEL", "openai/gpt-4o"))
    parser.add_argument("--skip-official-eval", action="store_true")
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
        metric_details = []
        with hyp_path.open("w", encoding="utf-8") as hyp_f:
            for item_i, example in enumerate(examples, start=1):
                if args.progress:
                    print(f"[example] baseline={label} {item_i}/{len(examples)} qid={example.question_id}", flush=True)
                result = driver.run(example)
                full_detail = result_to_jsonable(result)
                metric_details.append(full_detail)
                details.append(_compact_detail(full_detail))
                print(json.dumps({"question_id": result.question_id, "hypothesis": result.hypothesis}, ensure_ascii=False), file=hyp_f, flush=True)
                _write_detail(detail_path, args, stem, label, details)
        _write_detail(detail_path, args, stem, label, details)
        if args.rq_metrics:
            eval_path = output_dir / f"{stem}_{label}.jsonl.eval-results-{args.judge_model}"
            official_eval = _load_existing_eval(eval_path) if args.skip_official_eval else _run_official_eval(args, hyp_path, Path(args.input), eval_path)
            metrics_path = output_dir / f"{stem}_{label}_rq_metrics.json"
            metrics = _compute_rq_metrics(args, stem, label, detail_path, metric_details, official_eval)
            metrics_path.write_text(json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"[{label}] rq_metrics={metrics_path}")
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
        "config": _safe_config(args),
        "dataset": {"name": stem, "examples_completed": len(details)},
        "baseline": baseline,
        "summary": _summary(details),
        "details": details,
    }
    path.write_text(json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")


def _compact_detail(item: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "question_id": item.get("question_id"),
        "question_type": item.get("question_type"),
        "question": item.get("question"),
        "answer_gold": item.get("answer_gold"),
        "hypothesis": item.get("hypothesis"),
        "answer_session_ids": item.get("answer_session_ids") or [],
        "qa_trace": {
            "mode": (item.get("qa_trace") or {}).get("mode"),
            "context_chars": (item.get("qa_trace") or {}).get("context_chars"),
            "retrieval_error": (item.get("qa_trace") or {}).get("retrieval_error"),
        },
        "memory_count": len(item.get("memory_snapshot_final") or []),
        "events_count": len(item.get("extracted_events") or []),
        "write_failures": item.get("write_failures", 0),
        "audits_count": item.get("audits_count", 0),
        "bits_embedded": item.get("bits_embedded", 0),
        "capacity_stats": item.get("capacity_stats") or {},
    }


def _safe_config(args: argparse.Namespace) -> Dict[str, Any]:
    config = vars(args).copy()
    for key in list(config):
        if "key" in key.lower() or "token" in key.lower():
            config[key] = "***"
    return config


def _run_official_eval(args: argparse.Namespace, hyp_path: Path, ref_path: Path, eval_path: Path) -> Dict[str, Any]:
    module = _load_official_eval_module(args.longmemeval_root)
    metric_model, metric_source = module.model_zoo[args.judge_model]
    provider_model = args.judge_provider_model or metric_model
    if metric_source != "openai":
        raise RuntimeError("LongMemEval RQ1 import currently supports openai-compatible judge models only.")
    from openai import OpenAI

    client = OpenAI(api_key=args.judge_api_key or os.getenv("OPENAI_API_KEY"), base_url=args.judge_base_url, timeout=args.judge_timeout)
    hypotheses = [json.loads(line) for line in hyp_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    references = json.loads(ref_path.read_text(encoding="utf-8"))
    qid2ref = {entry["question_id"]: entry for entry in references}
    logs = []
    by_type: Dict[str, list[int]] = {}
    eval_path.parent.mkdir(parents=True, exist_ok=True)
    with eval_path.open("w", encoding="utf-8") as out_f:
        for entry in hypotheses:
            qid = entry.get("question_id")
            if qid not in qid2ref:
                continue
            ref = qid2ref[qid]
            prompt = module.get_anscheck_prompt(
                ref["question_type"],
                ref["question"],
                ref["answer"],
                entry.get("hypothesis", ""),
                abstention="_abs" in str(qid),
            )
            try:
                completion = client.chat.completions.create(
                    model=provider_model,
                    messages=[{"role": "user", "content": prompt}],
                    n=1,
                    temperature=0,
                    max_tokens=10,
                    timeout=args.judge_timeout,
                )
                raw = completion.choices[0].message.content.strip()
                label = "yes" in raw.lower()
                error = ""
            except Exception as exc:
                raw = ""
                label = False
                error = f"{type(exc).__name__}: {exc}"
            item = dict(entry)
            item["autoeval_label"] = {"model": provider_model, "label": label, "raw": raw, "error": error}
            logs.append(item)
            by_type.setdefault(ref["question_type"], []).append(1 if label else 0)
            print(json.dumps(item, ensure_ascii=False), file=out_f)
    return {
        "model": provider_model,
        "accuracy": sum(1 for item in logs if item["autoeval_label"]["label"]) / len(logs) if logs else 0.0,
        "count": len(logs),
        "by_question_type": {k: {"accuracy": sum(v) / len(v), "count": len(v)} for k, v in by_type.items()},
        "eval_path": str(eval_path),
    }


def _load_existing_eval(eval_path: Path) -> Dict[str, Any]:
    logs = []
    if eval_path.exists():
        for line in eval_path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                logs.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return {
        "model": "",
        "accuracy": sum(1 for item in logs if (item.get("autoeval_label") or {}).get("label")) / len(logs) if logs else 0.0,
        "count": len(logs),
        "by_question_type": {},
        "eval_path": str(eval_path),
        "loaded_existing": True,
    }


def _compute_rq_metrics(args: argparse.Namespace, stem: str, label: str, detail_path: Path, details: list[Dict[str, Any]], official_eval: Dict[str, Any]) -> Dict[str, Any]:
    from memmark.benchmarks.locomo.driver import LoCoMoDriverResult, _capacity_stats
    from memmark.experiments import run_rq2_capacity, run_rq3_in_record, run_rq4_robustness, run_rq5_integrity

    final = details[-1] if details else {}
    result = LoCoMoDriverResult(
        sample_id=stem,
        decisions=final.get("decisions") or [],
        audits=final.get("audits") or [],
        anchor=final.get("anchor"),
        memory_snapshot_final=final.get("memory_snapshot_final") or [],
        qa_predictions=[
            {"question_id": item.get("question_id"), "judge_correct": False, "correct": False}
            for item in details
        ],
        capacity_stats=final.get("capacity_stats") or {},
        extracted_events=[ev for item in details for ev in (item.get("extracted_events") or [])],
        payload_bits=str((vars(args) or {}).get("payload_bits") or ""),
    )
    result = _rehydrate_result(result)
    result.capacity_stats = result.capacity_stats or _capacity_stats(result.audits, result.decisions)
    rq2 = run_rq2_capacity(result)
    rq3 = run_rq3_in_record(driver_result=result, secret_key=args.secret_key)
    rq4 = run_rq4_robustness(driver_result=result, secret_key=args.secret_key)
    rq5 = run_rq5_integrity(result)
    return {
        "benchmark": "longmemeval",
        "dataset": stem,
        "baseline": label,
        "detail_path": str(detail_path),
        "rq1_utility": {
            "official_eval": official_eval,
            "memory_count": len(result.memory_snapshot_final),
            "write_failures": sum(1 for ev in result.extracted_events if not ev.get("applied")),
            "bits_embedded": sum(a.bits_embedded for a in result.audits),
            "capacity_bits_per_decision": result.capacity_stats.get("bits_per_decision", 0.0),
        },
        "rq2_capacity": _to_jsonable(rq2),
        "rq3_in_record": _to_jsonable(rq3),
        "rq4_robustness": _to_jsonable(rq4),
        "rq5_integrity": _to_jsonable(rq5),
    }


def _load_official_eval_module(root: str | None):
    if not root:
        try:
            from memmark.benchmarks.longmemeval import official_eval
            return official_eval
        except ImportError:
            raise RuntimeError("Set --longmemeval-root or LONGMEMEVAL_ROOT for --rq-metrics, or ensure official_eval.py is present.")
    path = Path(root) / "src" / "evaluation" / "evaluate_qa.py"
    if not path.exists():
        # Try root as file path
        if Path(root).is_file():
            path = Path(root)
    spec = importlib.util.spec_from_file_location("longmemeval_official_evaluate_qa", path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Cannot import official evaluator: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _rehydrate_result(result):
    from scripts.summarize_longmemeval_rq_metrics import _anchor, _audit, _decision

    result.decisions = [_decision(x) if isinstance(x, dict) else x for x in result.decisions]
    result.audits = [_audit(x) if isinstance(x, dict) else x for x in result.audits]
    result.anchor = _anchor(result.anchor) if isinstance(result.anchor, dict) else result.anchor
    return result


def _to_jsonable(obj: Any) -> Any:
    if hasattr(obj, "__dict__"):
        return {k: _to_jsonable(v) for k, v in obj.__dict__.items()}
    if isinstance(obj, dict):
        return {k: _to_jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_jsonable(v) for v in obj]
    return obj


def _summary(details: list[Dict[str, Any]]) -> Dict[str, Any]:
    if not details:
        return {"examples": 0, "write_failures": 0, "bits_embedded": 0, "audits_count": 0}
    return {
        "examples": len(details),
        "write_failures": sum(int(item.get("write_failures") or 0) for item in details),
        "bits_embedded": sum(int(item.get("bits_embedded") or 0) for item in details),
        "audits_count": sum(int(item.get("audits_count") or 0) for item in details),
        "memory_records_last": int(details[-1].get("memory_count") or len(details[-1].get("memory_snapshot_final") or [])),
    }


if __name__ == "__main__":
    main()
