from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path
from typing import Any, Iterable


RQ1_ROW_FIELDS = (
    "qa_accuracy",
    "qa_f1",
    "qa_bleu1",
    "qa_rougeL",
    "qa_count",
    "memory_count",
    "write_failures",
    "bits_embedded",
    "capacity_bits_per_decision",
)

RQ1_DELTA_FIELDS = (
    "qa_accuracy_delta",
    "qa_f1_delta",
    "qa_bleu1_delta",
    "qa_rougeL_delta",
    "memory_count_delta",
    "write_failures_delta",
)

RQ2_OVERALL_FIELDS = (
    "decisions",
    "bits_embedded",
    "bits_per_decision",
    "avg_candidate_set_size",
    "avg_entropy",
    "acceptance_rate",
)

RQ3_FLAT_GROUPS = {
    "r1": ("bit_recovery_rate", "commitment_pass_rate", "bits_total", "bits_recovered"),
    "r3": ("anchor_signature_valid", "root_matches", "bit_recovery_rate", "bits_recovered", "bits_total"),
    "r3_wrong_key": ("anchor_signature_valid", "bit_recovery_rate"),
}

RQ4_OUTCOME_FIELDS = (
    "leaves_affected",
    "bit_recovery_pre",
    "bit_recovery_post",
    "tamper_detection_rate",
)

RQ5_FIELDS = (
    "duplication_rate",
    "duplicate_count",
    "update_target_accuracy",
    "update_target_total",
    "update_target_correct",
    "link_target_total",
    "contradiction_rate",
    "overall_records",
    "evidence_recall_mean",
    "evidence_required_qas",
    "qa_with_full_evidence",
)

DETAIL_SUMMARY_FIELDS = (
    "decisions",
    "bits_embedded",
    "qa_count",
    "qa_accuracy",
    "qa_f1_mean",
    "qa_bleu1_mean",
    "qa_rougeL_mean",
    "qa_judge_accuracy",
    "memory_count",
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", default="results/amem_full")
    parser.add_argument("--output-csv", default="results/amem_full_metrics.csv")
    parser.add_argument("--output-jsonl", default="results/amem_full_metrics.jsonl")
    args = parser.parse_args()

    input_dir = Path(args.input_dir)
    rows: list[dict[str, Any]] = []
    for path in sorted(input_dir.glob("*.json"), key=_path_sort_key):
        if path.name.endswith(".partial"):
            continue
        data = _load_json(path)
        if not data:
            continue
        rows.extend(_extract_file_rows(path, data))

    rows = sorted(rows, key=lambda r: (_safe_int(r.get("conversation", 10**9)), r.get("baseline", ""), r.get("metric", "")))
    _write_csv(Path(args.output_csv), rows)
    _write_jsonl(Path(args.output_jsonl), rows)
    print(f"rows={len(rows)} csv={args.output_csv} jsonl={args.output_jsonl}")


def _extract_file_rows(path: Path, data: dict[str, Any]) -> list[dict[str, Any]]:
    config = data.get("config") or {}
    conversation_meta = data.get("conversation") or {}
    base = {
        "source_file": str(path),
        "conversation": config.get("conversation"),
        "sample_id": conversation_meta.get("sample_id"),
        "backend": config.get("backend"),
        "llm_mode": config.get("llm_mode"),
        "metric_scope": "",
        "baseline": "",
        "metric": "",
        "value": "",
        "extra": "",
    }
    rows: list[dict[str, Any]] = []
    rows.extend(_extract_rq1(base, data.get("rq1_utility") or {}))
    rows.extend(_extract_rq2(base, data.get("rq2_capacity") or {}))
    rows.extend(_extract_rq3(base, data.get("rq3_in_record") or {}))
    rows.extend(_extract_rq4(base, data.get("rq4_robustness") or {}))
    rows.extend(_extract_rq5(base, data.get("rq5_integrity") or {}))
    rows.extend(_extract_details(base, data.get("details") or {}))
    return rows


def _extract_rq1(base: dict[str, Any], rq1: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for item in rq1.get("rows") or []:
        label = item.get("label", "")
        for field in RQ1_ROW_FIELDS:
            rows.append(_row(base, "rq1_utility", label, field, item.get(field)))
        for cat, metrics in (item.get("qa_by_category") or {}).items():
            for key, value in metrics.items():
                rows.append(_row(base, "rq1_utility.qa_by_category", label, key, value, f"category={cat}"))
    for label, deltas in (rq1.get("deltas") or {}).items():
        for field in RQ1_DELTA_FIELDS:
            rows.append(_row(base, "rq1_utility.deltas", label, field, deltas.get(field), "base=no_watermark"))
    return rows


def _extract_rq2(base: dict[str, Any], rq2: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for label, report in rq2.items():
        overall = report.get("overall") or {}
        for field in RQ2_OVERALL_FIELDS:
            rows.append(_row(base, "rq2_capacity.overall", label, field, overall.get(field)))
        for carrier, metrics in (report.get("by_carrier") or {}).items():
            for key, value in metrics.items():
                rows.append(_row(base, "rq2_capacity.by_carrier", label, key, value, f"carrier={carrier}"))
    return rows


def _extract_rq3(base: dict[str, Any], rq3: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for label, report in rq3.items():
        for group, fields in RQ3_FLAT_GROUPS.items():
            values = report.get(group) or {}
            for field in fields:
                rows.append(_row(base, f"rq3_in_record.{group}", label, field, values.get(field)))
        for rate, values in (report.get("r2") or {}).items():
            for key, value in values.items():
                rows.append(_row(base, "rq3_in_record.r2", label, key, value, rate))
        for carrier, values in (report.get("r3_carrier_breakdown") or {}).items():
            for key, value in values.items():
                rows.append(_row(base, "rq3_in_record.r3_carrier_breakdown", label, key, value, f"carrier={carrier}"))
    return rows


def _extract_rq4(base: dict[str, Any], rq4: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for label, report in rq4.items():
        rows.append(_row(base, "rq4_robustness", label, "pre_recovery", report.get("pre_recovery")))
        for outcome in report.get("outcomes") or []:
            extra = f"attack={outcome.get('name')};strength={outcome.get('strength')}"
            for field in RQ4_OUTCOME_FIELDS:
                rows.append(_row(base, "rq4_robustness.outcomes", label, field, outcome.get(field), extra))
    return rows


def _extract_rq5(base: dict[str, Any], rq5: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for label, report in rq5.items():
        for field in RQ5_FIELDS:
            rows.append(_row(base, "rq5_integrity", label, field, report.get(field)))
        for carrier, count in (report.get("by_carrier_counts") or {}).items():
            rows.append(_row(base, "rq5_integrity.by_carrier_counts", label, "count", count, f"carrier={carrier}"))
    return rows


def _extract_details(base: dict[str, Any], details: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for label, detail in details.items():
        summary = detail.get("summary") or {}
        for field in DETAIL_SUMMARY_FIELDS:
            rows.append(_row(base, "details.summary", label, field, summary.get(field)))
    return rows


def _row(base: dict[str, Any], scope: str, baseline: str, metric: str, value: Any, extra: str = "") -> dict[str, Any]:
    out = dict(base)
    out.update({"metric_scope": scope, "baseline": baseline, "metric": metric, "value": _scalar(value), "extra": extra})
    return out


def _load_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"skip {path}: {type(exc).__name__}: {exc}")
        return None


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["source_file", "conversation", "sample_id", "backend", "llm_mode", "metric_scope", "baseline", "metric", "value", "extra"]
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def _scalar(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _path_sort_key(path: Path) -> tuple[int, str]:
    m = re.search(r"conv(\d+)", path.stem)
    return (int(m.group(1)) if m else 10**9, path.name)


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except Exception:
        return 10**9


if __name__ == "__main__":
    main()
