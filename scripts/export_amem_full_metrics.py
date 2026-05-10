from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
from typing import Any


METRIC_KEYWORDS = {
    "acceptance_rate",
    "anchor_signature_valid",
    "avg_candidate_set_size",
    "avg_entropy",
    "bit_recovery_post",
    "bit_recovery_pre",
    "bit_recovery_rate",
    "bits_embedded",
    "bits_per_decision",
    "bits_recovered",
    "bits_total",
    "bleu1",
    "capacity_bits_per_decision",
    "commitment_pass_rate",
    "context_dia_id_recall",
    "contradiction_rate",
    "decisions",
    "duplicate_count",
    "duplication_rate",
    "evidence_recall_mean",
    "evidence_required_qas",
    "f1",
    "judge_acc",
    "leaves_affected",
    "kept_leaves",
    "link_target_total",
    "memory_count",
    "memory_count_delta",
    "n",
    "overall_records",
    "pre_recovery",
    "qa_accuracy",
    "qa_accuracy_delta",
    "qa_bleu1_delta",
    "qa_count",
    "qa_f1_delta",
    "qa_judge_accuracy",
    "qa_rougeL_delta",
    "qa_with_full_evidence",
    "root_matches",
    "rougel",
    "rougeL",
    "strength",
    "tamper_detection_rate",
    "update_target_accuracy",
    "update_target_correct",
    "update_target_total",
    "write_failures",
    "write_failures_delta",
}

METRIC_SECTIONS = {
    "rq1_utility",
    "rq2_capacity",
    "rq3_in_record",
    "rq4_robustness",
    "rq5_integrity",
    "summary",
}


def _is_scalar(value: Any) -> bool:
    return value is None or isinstance(value, (str, int, float, bool))


def _key_matches(key: str) -> bool:
    normalized = key.replace("-", "_")
    lower = normalized.lower()
    return lower in {k.lower() for k in METRIC_KEYWORDS}


def _path_text(path: list[str]) -> str:
    return ".".join(path)


def _path_has_metric_section(path: list[str]) -> bool:
    return any(part in METRIC_SECTIONS for part in path)


def _section(path: list[str]) -> str:
    for part in path:
        if part in {"rq1_utility", "rq2_capacity", "rq3_in_record", "rq4_robustness", "rq5_integrity"}:
            return part
    if "details" in path and "summary" in path:
        return "details.summary"
    return ""


def _baseline(path: list[str]) -> str:
    labels = {"watermark", "no_watermark", "signed_metadata_only", "random_replace"}
    for part in path:
        if part in labels:
            return part
    if "label" in path:
        return ""
    return ""


def _scope(path: list[str]) -> str:
    markers = {"overall", "by_carrier", "r1", "r2", "r3", "r3_wrong_key", "r3_carrier_breakdown", "outcomes", "qa_by_category", "deltas", "summary"}
    return "/".join(part for part in path if part in markers or part.startswith("r=") or part.startswith("[") is False and part not in {"rq1_utility", "rq2_capacity", "rq3_in_record", "rq4_robustness", "rq5_integrity", "details"})


def _walk_metrics(value: Any, path: list[str], rows: list[dict[str, Any]]) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            _walk_metrics(child, path + [str(key)], rows)
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            item_path = path + [f"[{index}]"]
            if isinstance(child, dict) and "label" in child:
                item_path.append(str(child.get("label")))
            elif isinstance(child, dict) and "name" in child:
                item_path.append(str(child.get("name")))
            _walk_metrics(child, item_path, rows)
        return
    if not _is_scalar(value) or not path:
        return
    key = path[-1]
    if not _key_matches(key) or not _path_has_metric_section(path):
        return
    rows.append(
        {
            "section": _section(path),
            "baseline": _baseline(path),
            "scope": _scope(path),
            "metric": key,
            "value": value,
            "path": _path_text(path),
        }
    )


def _load_metrics(path: Path) -> list[dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    cfg = data.get("config", {}) if isinstance(data, dict) else {}
    conv = data.get("conversation", {}) if isinstance(data, dict) else {}
    rows: list[dict[str, Any]] = []
    _walk_metrics(data, [], rows)
    for row in rows:
        row.update(
            {
                "file": path.name,
                "conversation": cfg.get("conversation"),
                "sample_id": conv.get("sample_id"),
                "backend": cfg.get("backend"),
                "llm_mode": cfg.get("llm_mode"),
            }
        )
    return rows


def _write_csv(rows: list[dict[str, Any]], out_path: Path) -> None:
    fieldnames = [
        "file",
        "conversation",
        "sample_id",
        "backend",
        "llm_mode",
        "section",
        "baseline",
        "scope",
        "metric",
        "value",
        "path",
    ]
    with out_path.open("w", newline="", encoding="utf-8-sig") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description="Export MemMark LoCoMo experiment metrics from JSON files by metric-key matching.")
    parser.add_argument("--input", default="results/amem_full", help="Directory containing result JSON files.")
    parser.add_argument("--out-csv", default="results/amem_full_metrics.csv")
    parser.add_argument("--out-json", default="results/amem_full_metrics.json")
    args = parser.parse_args()

    input_dir = Path(args.input)
    files = sorted(input_dir.glob("*.json")) if input_dir.is_dir() else [input_dir]
    rows: list[dict[str, Any]] = []
    for file in files:
        rows.extend(_load_metrics(file))
    rows.sort(key=lambda r: (str(r.get("file")), str(r.get("section")), str(r.get("baseline")), str(r.get("path"))))

    csv_path = Path(args.out_csv)
    json_path = Path(args.out_json)
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    json_path.parent.mkdir(parents=True, exist_ok=True)
    _write_csv(rows, csv_path)
    json_path.write_text(json.dumps(rows, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"exported rows={len(rows)} csv={csv_path} json={json_path}")


if __name__ == "__main__":
    main()
