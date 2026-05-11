from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from memmark.benchmarks.locomo.driver import LoCoMoDriverResult, _capacity_stats
from memmark.core.types import AuditRecord, Candidate, DecisionPoint, MerkleProof, SessionHeader
from memmark.experiments import run_rq2_capacity, run_rq3_in_record, run_rq4_robustness, run_rq5_integrity

BASELINES = ("watermark", "no_watermark", "signed_metadata_only", "random_replace")
RQ_ORDER = ("RQ1 Utility", "RQ2 Capacity", "RQ3 Verification", "RQ4 Robustness", "RQ5 Integrity")
RQ1_FIELDS = ("qa_accuracy", "qa_count", "memory_count", "write_failures", "bits_embedded", "capacity_bits_per_decision")
RQ1_DELTA_FIELDS = ("qa_accuracy_delta", "memory_count_delta", "write_failures_delta")
RQ2_FIELDS = ("decisions", "bits_embedded", "bits_per_decision", "avg_candidate_set_size", "avg_entropy", "acceptance_rate")
RQ3_GROUPS = {
    "r1": ("bit_recovery_rate", "commitment_pass_rate", "bits_total", "bits_recovered"),
    "r2": ("anchor_signature_valid", "bit_recovery_rate", "bits_recovered", "bits_total", "kept_leaves", "root_matches"),
    "r3": ("anchor_signature_valid", "bit_recovery_rate", "bits_recovered", "bits_total", "root_matches"),
    "r3_carrier_breakdown": ("bit_recovery_rate", "bits_recovered", "bits_total", "leaves"),
    "r3_wrong_key": ("anchor_signature_valid", "bit_recovery_rate"),
}
RQ4_FIELDS = ("bit_recovery_post", "bit_recovery_pre", "leaves_affected", "name", "strength", "tamper_detection_rate")
RQ5_FIELDS = ("contradiction_rate", "duplicate_count", "duplication_rate", "link_target_accuracy", "link_target_correct", "link_target_total", "overall_records", "update_target_accuracy", "update_target_correct", "update_target_total")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--secret-key")
    args = parser.parse_args()

    rows: list[dict[str, Any]] = []
    loaded = []
    for path in args.inputs:
        data = json.loads(path.read_text(encoding="utf-8"))
        
        # 如果已经是算好的 rq_metrics.json
        if "rq2_capacity" in data and "rq3_in_record" in data:
            label = data.get("baseline") or _label_from_path(path)
            rows.extend(_build_rows_from_precomputed(data, label))
            continue

        # 否则按旧逻辑尝试从 detail 重建
        label = str(data.get("baseline") or _label_from_path(path))
        secret_key = args.secret_key or (data.get("config") or {}).get("secret_key", "memmark-default-dev-key")
        details = data.get("details") or []
        eval_labels = _load_eval_labels(path)
        result = _aggregate_result(data, details, eval_labels)
        loaded.append((label, result, details, eval_labels, secret_key))

    # 处理需要重算的行
    if loaded:
        rows.extend(_rq1_rows(loaded))
        for label, result, _details, _eval_labels, secret_key in loaded:
            rows.extend(_rq2_rows(label, result))
            rows.extend(_rq3_rows(label, result, secret_key))
            rows.extend(_rq4_rows(label, result, secret_key))
            rows.extend(_rq5_rows(label, result))

    output = args.output or args.inputs[0].with_name("longmemeval_rq_metrics_summary.md")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(_markdown(rows, args.inputs), encoding="utf-8")
    print(output)


def _build_rows_from_precomputed(data: dict[str, Any], label: str) -> list[dict[str, Any]]:
    rows = []
    
    # RQ1
    rq1 = data.get("rq1_utility") or {}
    for field in RQ1_FIELDS:
        rows.append(_row("RQ1 Utility", "overall", "", field, label, rq1.get(field)))
    eval_info = rq1.get("official_eval") or {}
    for qtype, metrics in (eval_info.get("by_question_type") or {}).items():
        rows.append(_row("RQ1 Utility", "qa_by_question_type", f"type={qtype}", "judge_acc", label, metrics.get("accuracy")))
        rows.append(_row("RQ1 Utility", "qa_by_question_type", f"type={qtype}", "n", label, metrics.get("count")))
    
    # RQ2
    rq2 = data.get("rq2_capacity") or {}
    for field in RQ2_FIELDS:
        rows.append(_row("RQ2 Capacity", "overall", "", field, label, (rq2.get("overall") or {}).get(field)))
    for carrier, metrics in (rq2.get("by_carrier") or {}).items():
        for metric, value in metrics.items():
            rows.append(_row("RQ2 Capacity", "by_carrier", f"carrier={carrier}", metric, label, value))
            
    # RQ3
    rq3 = data.get("rq3_in_record") or {}
    for group, fields in RQ3_GROUPS.items():
        if group == "r2":
            for item, metrics in (rq3.get("r2") or {}).items():
                for field in fields:
                    rows.append(_row("RQ3 Verification", "r2", item, field, label, metrics.get(field)))
        elif group == "r3_carrier_breakdown":
            for carrier, metrics in (rq3.get(group) or {}).items():
                for field in fields:
                    rows.append(_row("RQ3 Verification", group, f"carrier={carrier}", field, label, metrics.get(field)))
        else:
            metrics = rq3.get(group) or {}
            for field in fields:
                rows.append(_row("RQ3 Verification", group, "", field, label, metrics.get(field)))

    # RQ4
    rq4 = data.get("rq4_robustness") or {}
    rows.append(_row("RQ4 Robustness", "overall", "", "pre_recovery", label, rq4.get("pre_recovery")))
    for outcome in rq4.get("outcomes") or []:
        metrics = dict(outcome)
        item = f"attack={metrics.get('name')};strength={metrics.get('strength')}"
        for field in RQ4_FIELDS:
            rows.append(_row("RQ4 Robustness", "outcomes", item, field, label, metrics.get(field)))

    # RQ5
    rq5 = data.get("rq5_integrity") or {}
    for carrier, count in (rq5.get("by_carrier_counts") or {}).items():
        rows.append(_row("RQ5 Integrity", "by_carrier_counts", f"carrier={carrier}", "count", label, count))
    for field in RQ5_FIELDS:
        rows.append(_row("RQ5 Integrity", "overall", "", field, label, rq5.get(field)))
        
    return rows


def _aggregate_result(data: dict[str, Any], details: list[dict[str, Any]], eval_labels: dict[str, bool]) -> LoCoMoDriverResult:
    audits: list[AuditRecord] = []
    decisions: list[DecisionPoint] = []
    extracted_events: list[dict[str, Any]] = []
    memory_snapshot_final: list[dict[str, Any]] = []
    qa_predictions: list[dict[str, Any]] = []
    payload_bits = str((data.get("config") or {}).get("payload_bits") or "")
    anchor = None
    final_detail = details[-1] if details else {}
    audits = [_audit(x) for x in final_detail.get("audits") or []]
    decisions = [_decision(x) for x in final_detail.get("decisions") or []]
    if final_detail.get("anchor"):
        anchor = _anchor(final_detail.get("anchor"))

    for item in details:
        extracted_events.extend(item.get("extracted_events") or [])
        memory_snapshot_final = item.get("memory_snapshot_final") or memory_snapshot_final
        qid = str(item.get("question_id") or "")
        qa_predictions.append(
            {
                "question_id": qid,
                "question_type": item.get("question_type"),
                "correct": bool(eval_labels.get(qid, False)),
                "judge_correct": bool(eval_labels.get(qid, False)),
            }
        )

    return LoCoMoDriverResult(
        sample_id=str((data.get("dataset") or {}).get("name") or "longmemeval"),
        decisions=decisions,
        audits=audits,
        anchor=anchor,
        memory_snapshot_final=memory_snapshot_final,
        qa_predictions=qa_predictions,
        capacity_stats=_capacity_stats(audits, decisions),
        extracted_events=extracted_events,
        payload_bits=payload_bits,
    )


def _load_eval_labels(detail_path: Path) -> dict[str, bool]:
    candidates = [
        Path(str(detail_path.with_suffix(".jsonl")) + ".eval-results-gpt-4o"),
        detail_path.with_name(detail_path.stem + ".jsonl.eval-results-gpt-4o"),
        detail_path.with_name(detail_path.stem + "_eval.json"),
    ]
    for path in candidates:
        if not path.exists():
            continue
        labels: dict[str, bool] = {}
        for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
            line = line.strip()
            if not line.startswith("{"):
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            qid = item.get("question_id")
            label = ((item.get("autoeval_label") or {}).get("label"))
            if qid is not None:
                labels[str(qid)] = bool(label)
        if labels:
            return labels
    return {}


def _rq1_rows(items: list[tuple[str, LoCoMoDriverResult, list[dict[str, Any]], dict[str, bool], str]]) -> list[dict[str, Any]]:
    rows = []
    metrics_by_label = {}
    for label, result, details, _eval_labels, _secret_key in items:
        qa_count = len(result.qa_predictions)
        qa_accuracy = sum(1 for q in result.qa_predictions if q.get("judge_correct")) / qa_count if qa_count else 0.0
        metrics = {
            "qa_accuracy": qa_accuracy,
            "qa_count": qa_count,
            "memory_count": len(result.memory_snapshot_final),
            "write_failures": sum(1 for ev in result.extracted_events if not ev.get("applied")),
            "bits_embedded": sum(a.bits_embedded for a in result.audits),
            "capacity_bits_per_decision": result.capacity_stats.get("bits_per_decision", 0.0),
        }
        metrics_by_label[label] = metrics
        for field in RQ1_FIELDS:
            rows.append(_row("RQ1 Utility", "overall", "", field, label, metrics.get(field)))
        by_type: dict[str, list[bool]] = {}
        for detail in details:
            qid = str(detail.get("question_id") or "")
            qtype = str(detail.get("question_type") or "unknown")
            pred = next((q for q in result.qa_predictions if q.get("question_id") == qid), {})
            by_type.setdefault(qtype, []).append(bool(pred.get("judge_correct")))
        for qtype, labels in by_type.items():
            rows.append(_row("RQ1 Utility", "qa_by_question_type", f"type={qtype}", "judge_acc", label, sum(labels) / len(labels) if labels else 0.0))
            rows.append(_row("RQ1 Utility", "qa_by_question_type", f"type={qtype}", "n", label, len(labels)))
    base = metrics_by_label.get("no_watermark")
    if base:
        for label, metrics in metrics_by_label.items():
            if label == "no_watermark":
                continue
            deltas = {
                "qa_accuracy_delta": metrics.get("qa_accuracy", 0.0) - base.get("qa_accuracy", 0.0),
                "memory_count_delta": metrics.get("memory_count", 0) - base.get("memory_count", 0),
                "write_failures_delta": metrics.get("write_failures", 0) - base.get("write_failures", 0),
            }
            for field in RQ1_DELTA_FIELDS:
                rows.append(_row("RQ1 Utility", "deltas_vs_no_watermark", "base=no_watermark", field, label, deltas.get(field)))
    return rows


def _rq2_rows(label: str, result: LoCoMoDriverResult) -> list[dict[str, Any]]:
    report = run_rq2_capacity(result)
    rows = [_row("RQ2 Capacity", "overall", "", field, label, report.overall.get(field)) for field in RQ2_FIELDS]
    for carrier, metrics in report.by_carrier.items():
        for metric, value in metrics.items():
            rows.append(_row("RQ2 Capacity", "by_carrier", f"carrier={carrier}", metric, label, value))
    return rows


def _rq3_rows(label: str, result: LoCoMoDriverResult, secret_key: str) -> list[dict[str, Any]]:
    report = _jsonable(run_rq3_in_record(driver_result=result, secret_key=secret_key))
    rows = []
    for group, fields in RQ3_GROUPS.items():
        if group == "r2":
            for item, metrics in (report.get("r2") or {}).items():
                for field in fields:
                    rows.append(_row("RQ3 Verification", "r2", item, field, label, metrics.get(field)))
        elif group == "r3_carrier_breakdown":
            for carrier, metrics in (report.get(group) or {}).items():
                for field in fields:
                    rows.append(_row("RQ3 Verification", group, f"carrier={carrier}", field, label, metrics.get(field)))
        else:
            metrics = report.get(group) or {}
            for field in fields:
                rows.append(_row("RQ3 Verification", group, "", field, label, metrics.get(field)))
    return rows


def _rq4_rows(label: str, result: LoCoMoDriverResult, secret_key: str) -> list[dict[str, Any]]:
    report = _jsonable(run_rq4_robustness(driver_result=result, secret_key=secret_key))
    rows = [_row("RQ4 Robustness", "overall", "", "pre_recovery", label, report.get("pre_recovery"))]
    for outcome in report.get("outcomes") or []:
        metrics = dict(outcome)
        metrics["tamper_detection_rate"] = max(metrics.get("commitment_fail_rate", 0.0), metrics.get("merkle_proof_fail_rate", 0.0))
        item = f"attack={metrics.get('name')};strength={metrics.get('strength')}"
        for field in RQ4_FIELDS:
            rows.append(_row("RQ4 Robustness", "outcomes", item, field, label, metrics.get(field)))
    return rows


def _rq5_rows(label: str, result: LoCoMoDriverResult) -> list[dict[str, Any]]:
    report = _jsonable(run_rq5_integrity(result))
    rows = []
    for carrier, count in (report.get("by_carrier_counts") or {}).items():
        rows.append(_row("RQ5 Integrity", "by_carrier_counts", f"carrier={carrier}", "count", label, count))
    for field in RQ5_FIELDS:
        rows.append(_row("RQ5 Integrity", "overall", "", field, label, report.get(field)))
    return rows


def _label_from_path(path: Path) -> str:
    stem = path.stem
    for label in BASELINES:
        if stem.endswith("_" + label):
            return label
    return stem


def _candidate(raw: dict[str, Any]) -> Candidate:
    return Candidate(str(raw.get("candidate_id") or ""), str(raw.get("carrier_type") or ""), raw.get("payload") or {}, raw.get("operation") or {}, float(raw.get("utility_score", 1.0)))


def _decision(raw: dict[str, Any]) -> DecisionPoint:
    return DecisionPoint(
        decision_id=str(raw.get("decision_id") or ""),
        tau=str(raw.get("tau") or ""),
        candidates=[_candidate(x) for x in raw.get("candidates") or []],
        probabilities={str(k): float(v) for k, v in (raw.get("probabilities") or {}).items()},
        context=str(raw.get("context") or ""),
        round_num=int(raw.get("round_num") or 0),
        nonce=str(raw.get("nonce") or ""),
        watermark_version=str(raw.get("watermark_version") or ""),
    )


def _audit(raw: dict[str, Any]) -> AuditRecord:
    proof = raw.get("merkle_inclusion_proof")
    return AuditRecord(
        decision_id=str(raw.get("decision_id") or ""),
        tau=str(raw.get("tau") or ""),
        candidate_hash=str(raw.get("candidate_hash") or ""),
        probability_hash=str(raw.get("probability_hash") or ""),
        context=str(raw.get("context") or ""),
        context_hash=str(raw.get("context_hash") or ""),
        selected_candidate_id=str(raw.get("selected_candidate_id") or ""),
        bits_embedded=int(raw.get("bits_embedded") or 0),
        bit_index_after=int(raw.get("bit_index_after") or 0),
        round_num=int(raw.get("round_num") or 0),
        commitment=str(raw.get("commitment") or ""),
        nonce=str(raw.get("nonce") or ""),
        watermark_version=str(raw.get("watermark_version") or ""),
        decoded_bits=raw.get("decoded_bits"),
        candidates=[_candidate(x) for x in raw.get("candidates") or []],
        probabilities={str(k): float(v) for k, v in (raw.get("probabilities") or {}).items()},
        extra_carriers=tuple(raw.get("extra_carriers") or ()),
        merkle_inclusion_proof=_proof(proof) if isinstance(proof, dict) else None,
    )


def _proof(raw: dict[str, Any]) -> MerkleProof:
    return MerkleProof(str(raw.get("leaf") or ""), [tuple(x) for x in raw.get("siblings") or []], str(raw.get("root") or ""))


def _anchor(raw: Any) -> SessionHeader | None:
    if not isinstance(raw, dict):
        return None
    return SessionHeader(str(raw.get("agent_id") or ""), str(raw.get("user_id") or ""), str(raw.get("session_id") or ""), int(raw.get("leaf_count") or 0), str(raw.get("root") or ""), str(raw.get("signature") or ""), str(raw.get("watermark_version") or ""))


def _row(rq: str, group: str, item: str, metric: str, baseline: str, value: Any) -> dict[str, Any]:
    return {"rq": rq, "group": group, "item": item, "metric": metric, "baseline": baseline, "value": value}


def _markdown(rows: list[dict[str, Any]], source: list[Path]) -> str:
    source_line = ", ".join(f"`{path}`" for path in source)
    lines = ["# LongMemEval RQ Metrics Summary", "", f"- **File**: {source_line}", "- **Cell value**: empty means baseline has no metric or no official eval labels were found.", ""]
    for rq in RQ_ORDER:
        subset = [r for r in rows if r["rq"] == rq]
        if not subset:
            continue
        lines.append(f"## {rq}")
        for group in _ordered_unique(r["group"] for r in subset):
            group_rows = [r for r in subset if r["group"] == group]
            lines.append("")
            lines.append(f"### {group}")
            lines.append(_table(["item", "metric", *BASELINES], [_wide_row(key, group_rows) for key in _row_keys(group_rows)]))
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _row_keys(rows: list[dict[str, Any]]) -> list[tuple[str, str]]:
    return sorted({(str(r["item"]), str(r["metric"])) for r in rows}, key=lambda x: (x[0], x[1]))


def _wide_row(key: tuple[str, str], rows: list[dict[str, Any]]) -> list[Any]:
    item, metric = key
    values = {b: "" for b in BASELINES}
    for row in rows:
        if str(row["item"]) == item and str(row["metric"]) == metric and row["baseline"] in values:
            values[row["baseline"]] = row["value"]
    return [item, metric, *[values[b] for b in BASELINES]]


def _table(headers: list[str], rows: list[list[Any]]) -> str:
    out = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    out.extend("| " + " | ".join(_cell(_fmt(x)) for x in row) + " |" for row in rows)
    return "\n".join(out)


def _fmt(value: Any) -> str:
    if value in (None, ""):
        return ""
    if isinstance(value, bool):
        return "1" if value else "0"
    if isinstance(value, (int, float)):
        return str(int(round(value))) if abs(float(value) - round(float(value))) < 1e-9 else f"{float(value):.4f}"
    return str(value)


def _cell(value: Any) -> str:
    return str(value).replace("|", "/").replace("\n", " ")


def _ordered_unique(values) -> list[str]:
    out = []
    for value in values:
        if value not in out:
            out.append(value)
    return out


def _jsonable(obj: Any) -> Any:
    if hasattr(obj, "__dict__"):
        return {k: _jsonable(v) for k, v in obj.__dict__.items()}
    if isinstance(obj, dict):
        return {k: _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(v) for v in obj]
    return obj


if __name__ == "__main__":
    main()
