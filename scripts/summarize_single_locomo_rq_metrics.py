from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from memmark.benchmarks.locomo.driver import LoCoMoDriverResult, _capacity_stats
from memmark.core.types import AuditRecord, Candidate, DecisionPoint, MerkleProof, SessionHeader
from memmark.experiments import run_rq1_utility, run_rq2_capacity, run_rq3_in_record, run_rq4_robustness, run_rq5_integrity

BASELINES = ("watermark", "no_watermark", "signed_metadata_only", "random_replace")
RQ1_FIELDS = ("qa_accuracy", "qa_f1", "qa_bleu1", "qa_rougeL", "qa_count", "memory_count", "write_failures", "bits_embedded", "capacity_bits_per_decision")
RQ1_DELTA_FIELDS = ("qa_accuracy_delta", "qa_f1_delta", "qa_bleu1_delta", "qa_rougeL_delta", "memory_count_delta", "write_failures_delta")
RQ2_FIELDS = ("decisions", "bits_embedded", "bits_per_decision", "avg_candidate_set_size", "avg_entropy", "acceptance_rate")
RQ3_GROUPS = {
    "r1": ("bit_recovery_rate", "commitment_pass_rate", "bits_total", "bits_recovered"),
    "r2": ("anchor_signature_valid", "bit_recovery_rate", "bits_recovered", "bits_total", "kept_leaves", "root_matches"),
    "r3": ("anchor_signature_valid", "bit_recovery_rate", "bits_recovered", "bits_total", "root_matches"),
    "r3_carrier_breakdown": ("bit_recovery_rate", "bits_recovered", "bits_total", "leaves"),
    "r3_wrong_key": ("anchor_signature_valid", "bit_recovery_rate"),
}
RQ4_FIELDS = ("bit_recovery_post", "bit_recovery_pre", "leaves_affected", "name", "strength", "tamper_detection_rate")
RQ5_FIELDS = ("contradiction_rate", "duplicate_count", "duplication_rate", "evidence_recall_mean", "evidence_required_qas", "link_target_total", "overall_records", "qa_with_full_evidence", "update_target_accuracy", "update_target_correct", "update_target_total")
RQ_ORDER = ("RQ1 Utility", "RQ2 Capacity", "RQ3 Verification", "RQ4 Robustness", "RQ5 Integrity")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--baseline", choices=BASELINES)
    args = parser.parse_args()
    data = json.loads(args.input.read_text(encoding="utf-8"))
    runs = _runs_from_json(data, args.baseline)
    secret_key = (data.get("config") or {}).get("secret_key", "memmark-default-dev-key")
    rows = _build_rows(runs, secret_key)
    output = args.output or args.input.with_name(args.input.stem + "_rq_metrics_summary.md")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(_markdown(rows, args.input), encoding="utf-8")
    print(output)


def _runs_from_json(data: dict[str, Any], only: str | None) -> dict[str, LoCoMoDriverResult]:
    details = data.get("details") or {}
    if only:
        labels = [only]
    elif data.get("baseline") in details:
        labels = [data["baseline"]]
    else:
        labels = [b for b in BASELINES if b in details]
    return {label: _result_from_detail(data, details[label]) for label in labels}


def _result_from_detail(data: dict[str, Any], detail: dict[str, Any]) -> LoCoMoDriverResult:
    decisions = [_decision(x) for x in detail.get("decisions") or []]
    audits = [_audit(x) for x in detail.get("audits") or []]
    return LoCoMoDriverResult(
        sample_id=str((data.get("conversation") or {}).get("sample_id") or ""),
        decisions=decisions,
        audits=audits,
        anchor=_anchor(detail.get("anchor")),
        memory_snapshot_final=detail.get("memory_snapshot_final") or [],
        qa_predictions=detail.get("qa_predictions") or [],
        capacity_stats=_capacity_stats(audits, decisions),
        extracted_events=detail.get("extracted_events") or [],
        payload_bits=str((data.get("config") or {}).get("payload_bits") or ""),
    )


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


def _build_rows(runs: dict[str, LoCoMoDriverResult], secret_key: str) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    rows.extend(_rq1(runs))
    rows.extend(_rq2(runs))
    rows.extend(_rq3(runs, secret_key))
    rows.extend(_rq4(runs, secret_key))
    rows.extend(_rq5(runs))
    return rows


def _rq1(runs: dict[str, LoCoMoDriverResult]) -> list[dict[str, Any]]:
    report = run_rq1_utility(runs=runs)
    rows = []
    for item in report.rows:
        values = item.__dict__
        for field in RQ1_FIELDS:
            rows.append(_row("RQ1 Utility", "overall", "", field, item.label, values.get(field)))
        for cat, metrics in item.qa_by_category.items():
            for metric, value in metrics.items():
                rows.append(_row("RQ1 Utility", "qa_by_category", f"category={cat}", metric, item.label, value))
    for label, values in report.deltas.items():
        for field in RQ1_DELTA_FIELDS:
            rows.append(_row("RQ1 Utility", "deltas_vs_no_watermark", "base=no_watermark", field, label, values.get(field)))
    return rows


def _rq2(runs: dict[str, LoCoMoDriverResult]) -> list[dict[str, Any]]:
    rows = []
    for label, result in runs.items():
        report = run_rq2_capacity(result)
        for field in RQ2_FIELDS:
            rows.append(_row("RQ2 Capacity", "overall", "", field, label, report.overall.get(field)))
        for carrier, metrics in report.by_carrier.items():
            for metric, value in metrics.items():
                rows.append(_row("RQ2 Capacity", "by_carrier", f"carrier={carrier}", metric, label, value))
    return rows


def _rq3(runs: dict[str, LoCoMoDriverResult], secret_key: str) -> list[dict[str, Any]]:
    rows = []
    for label, result in runs.items():
        report = _jsonable(run_rq3_in_record(driver_result=result, secret_key=secret_key))
        for group, fields in RQ3_GROUPS.items():
            if group == "r2":
                for item, values in (report.get("r2") or {}).items():
                    for field in fields:
                        rows.append(_row("RQ3 Verification", "r2", item, field, label, values.get(field)))
            elif group == "r3_carrier_breakdown":
                for carrier, values in (report.get(group) or {}).items():
                    for field in fields:
                        rows.append(_row("RQ3 Verification", group, f"carrier={carrier}", field, label, values.get(field)))
            else:
                values = report.get(group) or {}
                for field in fields:
                    rows.append(_row("RQ3 Verification", group, "", field, label, values.get(field)))
    return rows


def _rq4(runs: dict[str, LoCoMoDriverResult], secret_key: str) -> list[dict[str, Any]]:
    rows = []
    for label, result in runs.items():
        report = run_rq4_robustness(driver_result=result, secret_key=secret_key)
        rows.append(_row("RQ4 Robustness", "overall", "", "pre_recovery", label, report.pre_recovery))
        for outcome in report.outcomes:
            values = outcome.__dict__.copy()
            values["tamper_detection_rate"] = max(values.get("commitment_fail_rate", 0.0), values.get("merkle_proof_fail_rate", 0.0))
            item = f"attack={outcome.name};strength={outcome.strength}"
            for field in RQ4_FIELDS:
                rows.append(_row("RQ4 Robustness", "outcomes", item, field, label, values.get(field)))
    return rows


def _rq5(runs: dict[str, LoCoMoDriverResult]) -> list[dict[str, Any]]:
    rows = []
    for label, result in runs.items():
        report = run_rq5_integrity(result)
        values = report.__dict__
        for carrier, count in report.by_carrier_counts.items():
            rows.append(_row("RQ5 Integrity", "by_carrier_counts", f"carrier={carrier}", "count", label, count))
        for field in RQ5_FIELDS:
            rows.append(_row("RQ5 Integrity", "overall", "", field, label, values.get(field)))
    return rows


def _row(rq: str, group: str, item: str, metric: str, baseline: str, value: Any) -> dict[str, Any]:
    return {"rq": rq, "group": group, "item": item, "metric": metric, "baseline": baseline, "value": value}


def _markdown(rows: list[dict[str, Any]], source: Path) -> str:
    lines = ["# LoCoMo RQ Metrics Summary", "", f"- **File**: `{source}`", "- **Cell value**: numeric values are from this JSON file; empty means baseline has no metric.", ""]
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


"""
python scripts\summarize_single_locomo_rq_metrics.py `
  results\deepseek_v4_flash\conv1_watermark.json `
  --output results\deepseek_v4_flash\conv1_watermark_rq_metrics_summary.md
"""