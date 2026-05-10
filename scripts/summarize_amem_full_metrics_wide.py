from __future__ import annotations

import argparse
import csv
import json
import re
from collections import defaultdict
from pathlib import Path
from statistics import mean
from typing import Any


BASELINES = ("watermark", "no_watermark", "signed_metadata_only", "random_replace")

RQ1_FIELDS = (
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
RQ2_FIELDS = (
    "decisions",
    "bits_embedded",
    "bits_per_decision",
    "avg_candidate_set_size",
    "avg_entropy",
    "acceptance_rate",
)
RQ3_GROUPS = {
    "r1": ("bit_recovery_rate", "commitment_pass_rate", "bits_total", "bits_recovered"),
    "r3": ("anchor_signature_valid", "root_matches", "bit_recovery_rate", "bits_total", "bits_recovered"),
    "r3_wrong_key": ("anchor_signature_valid", "bit_recovery_rate"),
}
RQ4_FIELDS = ("leaves_affected", "bit_recovery_pre", "bit_recovery_post", "tamper_detection_rate")
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


def main() -> None:
    parser = argparse.ArgumentParser(description="Create concise four-baseline wide tables for A-MEM full results.")
    parser.add_argument("--input-dir", default="results/amem_full")
    parser.add_argument("--out-md", default="results/amem_full_metrics_summary.md")
    parser.add_argument("--out-wide-csv", default="results/amem_full_metrics_wide.csv")
    parser.add_argument("--out-aggregate-csv", default="results/amem_full_metrics_aggregate.csv")
    args = parser.parse_args()

    files = sorted(Path(args.input_dir).glob("*.json"), key=_path_sort_key)
    rows: list[dict[str, Any]] = []
    for path in files:
        data = json.loads(path.read_text(encoding="utf-8"))
        rows.extend(_extract_rows(path, data))

    wide_rows = _wide_rows(rows)
    aggregate_rows = _aggregate_rows(wide_rows)
    _write_csv(Path(args.out_wide_csv), wide_rows)
    _write_csv(Path(args.out_aggregate_csv), aggregate_rows)
    Path(args.out_md).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out_md).write_text(_markdown(aggregate_rows, files), encoding="utf-8")
    print(f"wide_rows={len(wide_rows)} aggregate_rows={len(aggregate_rows)} md={args.out_md} wide_csv={args.out_wide_csv} aggregate_csv={args.out_aggregate_csv}")


def _extract_rows(path: Path, data: dict[str, Any]) -> list[dict[str, Any]]:
    cfg = data.get("config") or {}
    conv = data.get("conversation") or {}
    base = {
        "file": path.name,
        "conversation": cfg.get("conversation"),
        "sample_id": conv.get("sample_id"),
        "rq": "",
        "group": "",
        "item": "",
        "metric": "",
        "baseline": "",
        "value": "",
    }
    rows: list[dict[str, Any]] = []
    rows.extend(_rq1(base, data.get("rq1_utility") or {}))
    rows.extend(_rq2(base, data.get("rq2_capacity") or {}))
    rows.extend(_rq3(base, data.get("rq3_in_record") or {}))
    rows.extend(_rq4(base, data.get("rq4_robustness") or {}))
    rows.extend(_rq5(base, data.get("rq5_integrity") or {}))
    return rows


def _rq1(base: dict[str, Any], rq1: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for item in rq1.get("rows") or []:
        label = item.get("label", "")
        for field in RQ1_FIELDS:
            rows.append(_row(base, "RQ1 Utility", "overall", "", field, label, item.get(field)))
        for cat, values in (item.get("qa_by_category") or {}).items():
            for metric, value in values.items():
                rows.append(_row(base, "RQ1 Utility", "qa_by_category", f"category={cat}", metric, label, value))
    for label, values in (rq1.get("deltas") or {}).items():
        for field in RQ1_DELTA_FIELDS:
            rows.append(_row(base, "RQ1 Utility", "deltas_vs_no_watermark", "base=no_watermark", field, label, values.get(field)))
    return rows


def _rq2(base: dict[str, Any], rq2: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for label, report in rq2.items():
        for field in RQ2_FIELDS:
            rows.append(_row(base, "RQ2 Capacity", "overall", "", field, label, (report.get("overall") or {}).get(field)))
        for carrier, values in (report.get("by_carrier") or {}).items():
            for metric, value in values.items():
                rows.append(_row(base, "RQ2 Capacity", "by_carrier", f"carrier={carrier}", metric, label, value))
    return rows


def _rq3(base: dict[str, Any], rq3: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for label, report in rq3.items():
        for group, fields in RQ3_GROUPS.items():
            values = report.get(group) or {}
            for field in fields:
                rows.append(_row(base, "RQ3 Verification", group, "", field, label, values.get(field)))
        for rate, values in (report.get("r2") or {}).items():
            for metric, value in values.items():
                rows.append(_row(base, "RQ3 Verification", "r2", rate, metric, label, value))
        for carrier, values in (report.get("r3_carrier_breakdown") or {}).items():
            for metric, value in values.items():
                rows.append(_row(base, "RQ3 Verification", "r3_carrier_breakdown", f"carrier={carrier}", metric, label, value))
    return rows


def _rq4(base: dict[str, Any], rq4: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for label, report in rq4.items():
        rows.append(_row(base, "RQ4 Robustness", "overall", "", "pre_recovery", label, report.get("pre_recovery")))
        for outcome in report.get("outcomes") or []:
            item = f"attack={outcome.get('name')};strength={outcome.get('strength')}"
            rows.append(_row(base, "RQ4 Robustness", "outcomes", item, "name", label, outcome.get("name")))
            rows.append(_row(base, "RQ4 Robustness", "outcomes", item, "strength", label, outcome.get("strength")))
            for field in RQ4_FIELDS:
                rows.append(_row(base, "RQ4 Robustness", "outcomes", item, field, label, outcome.get(field)))
    return rows


def _rq5(base: dict[str, Any], rq5: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for label, report in rq5.items():
        for field in RQ5_FIELDS:
            rows.append(_row(base, "RQ5 Integrity", "overall", "", field, label, report.get(field)))
        for carrier, count in (report.get("by_carrier_counts") or {}).items():
            rows.append(_row(base, "RQ5 Integrity", "by_carrier_counts", f"carrier={carrier}", "count", label, count))
    return rows


def _row(base: dict[str, Any], rq: str, group: str, item: str, metric: str, baseline: str, value: Any) -> dict[str, Any]:
    out = dict(base)
    out.update({"rq": rq, "group": group, "item": item, "metric": metric, "baseline": baseline, "value": _scalar(value)})
    return out


def _wide_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[Any, ...], dict[str, Any]] = {}
    for row in rows:
        key = (row["file"], row["conversation"], row["sample_id"], row["rq"], row["group"], row["item"], row["metric"])
        out = grouped.setdefault(
            key,
            {
                "file": row["file"],
                "conversation": row["conversation"],
                "sample_id": row["sample_id"],
                "rq": row["rq"],
                "group": row["group"],
                "item": row["item"],
                "metric": row["metric"],
                **{b: "" for b in BASELINES},
            },
        )
        if row["baseline"] in BASELINES:
            out[row["baseline"]] = row["value"]
    return sorted(grouped.values(), key=lambda r: (_safe_int(r["conversation"]), r["rq"], r["group"], r["item"], r["metric"]))


def _aggregate_rows(wide_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    buckets: dict[tuple[str, str, str, str], dict[str, list[Any]]] = defaultdict(lambda: {b: [] for b in BASELINES})
    for row in wide_rows:
        key = (row["rq"], row["group"], row["item"], row["metric"])
        for baseline in BASELINES:
            buckets[key][baseline].append(row.get(baseline, ""))
    out = []
    for (rq, group, item, metric), values in buckets.items():
        record = {"rq": rq, "group": group, "item": item, "metric": metric}
        for baseline in BASELINES:
            record[baseline] = _aggregate_value(values[baseline])
        out.append(record)
    return sorted(out, key=lambda r: (r["rq"], r["group"], r["item"], r["metric"]))


def _aggregate_value(values: list[Any]) -> Any:
    nums = [_float_or_none(v) for v in values if v not in ("", None)]
    nums = [v for v in nums if v is not None]
    if nums and len(nums) == len([v for v in values if v not in ("", None)]):
        return round(mean(nums), 6)
    uniq = sorted({str(v) for v in values if v not in ("", None)})
    if not uniq:
        return ""
    return uniq[0] if len(uniq) == 1 else "; ".join(uniq[:4])


def _markdown(rows: list[dict[str, Any]], files: list[Path]) -> str:
    lines = ["# A-MEM Full Metrics Summary", "", f"- **Files**: {len(files)}", "- **Cell value**: numeric values are mean across JSON files; empty means baseline has no metric.", ""]
    for rq in ("RQ1 Utility", "RQ2 Capacity", "RQ3 Verification", "RQ4 Robustness", "RQ5 Integrity"):
        subset = [r for r in rows if r["rq"] == rq]
        if not subset:
            continue
        lines.append(f"## {rq}")
        groups = []
        for row in subset:
            if row["group"] not in groups:
                groups.append(row["group"])
        for group in groups:
            group_rows = [r for r in subset if r["group"] == group]
            lines.append("")
            lines.append(f"### {group}")
            lines.append(_table(["item", "metric", *BASELINES], [[r["item"], r["metric"], *[_fmt(r[b]) for b in BASELINES]] for r in group_rows]))
            lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _table(headers: list[str], rows: list[list[Any]]) -> str:
    out = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for row in rows:
        out.append("| " + " | ".join(_cell(x) for x in row) + " |")
    return "\n".join(out)


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0].keys()) if rows else []
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def _scalar(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _fmt(value: Any) -> str:
    if value in (None, ""):
        return ""
    number = _float_or_none(value)
    if number is None:
        return str(value)
    if abs(number - round(number)) < 1e-9:
        return str(int(round(number)))
    return f"{number:.4f}"


def _cell(value: Any) -> str:
    return str(value if value is not None else "").replace("|", "/").replace("\n", " ")


def _float_or_none(value: Any) -> float | None:
    if isinstance(value, bool):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _path_sort_key(path: Path) -> tuple[int, str]:
    match = re.search(r"conv(\d+)", path.stem)
    return (int(match.group(1)) if match else 10**9, path.name)


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except Exception:
        return 10**9


if __name__ == "__main__":
    main()
