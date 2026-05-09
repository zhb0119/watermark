from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean
from typing import Any


def _num(x: Any, default: float = 0.0) -> float:
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def _fmt(x: Any, digits: int = 3) -> str:
    if x is None:
        return "-"
    if isinstance(x, int):
        return str(x)
    if isinstance(x, float):
        return f"{x:.{digits}f}"
    return str(x)


def _get(d: dict, path: str, default: Any = None) -> Any:
    cur: Any = d
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return default
        cur = cur[part]
    return cur


def _table(headers: list[str], rows: list[list[Any]]) -> str:
    out = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for row in rows:
        out.append("| " + " | ".join(str(x) for x in row) + " |")
    return "\n".join(out)


def _summarize_qa(preds: list[dict[str, Any]], limit: int) -> tuple[list[list[Any]], dict[str, Any]]:
    rows = []
    by_cat: dict[str, list[dict[str, Any]]] = defaultdict(list)
    recalls = []
    for p in preds:
        cat = str(p.get("category", ""))
        by_cat[cat].append(p)
        if "evidence_recall" in p:
            recalls.append(_num(p.get("evidence_recall")))
    cat_rows = []
    for cat, items in sorted(by_cat.items()):
        cat_rows.append([
            cat,
            len(items),
            _fmt(mean(_num(x.get("f1")) for x in items)),
            _fmt(mean(_num(x.get("bleu1")) for x in items)),
            _fmt(mean(_num(x.get("rougeL")) for x in items)),
            _fmt(mean(1.0 if x.get("judge_correct") else 0.0 for x in items)),
            _fmt(mean(_num(x.get("evidence_recall")) for x in items if "evidence_recall" in x)) if any("evidence_recall" in x for x in items) else "-",
        ])
    mistakes = sorted(
        preds,
        key=lambda x: (_num(x.get("judge_correct")), _num(x.get("f1"))),
    )[:limit]
    for p in mistakes:
        rows.append([
            p.get("category", ""),
            _fmt(_num(p.get("f1"))),
            _fmt(_num(p.get("evidence_recall"))) if "evidence_recall" in p else "-",
            str(p.get("question", "")).replace("|", "/")[:90],
            str(p.get("gold", p.get("answer", ""))).replace("|", "/")[:60],
            str(p.get("answer_pred", p.get("prediction", ""))).replace("|", "/")[:60],
        ])
    stats = {
        "qa_count": len(preds),
        "evidence_recall_mean": mean(recalls) if recalls else None,
        "cat_rows": cat_rows,
    }
    return rows, stats


def _summarize_events(events: list[dict[str, Any]]) -> dict[str, Any]:
    applied = [e for e in events if e.get("applied")]
    by_session = Counter(str(e.get("session", "")) for e in applied)
    by_source = Counter(str(e.get("source", "")) for e in applied)
    by_speaker = Counter(str(e.get("speaker", "")) for e in applied)
    bits = sum(int(_num(e.get("bits_embedded"))) for e in applied)
    zero_bits = sum(1 for e in applied if int(_num(e.get("bits_embedded"))) == 0)
    return {
        "events": len(events),
        "applied": len(applied),
        "failed": len(events) - len(applied),
        "bits_from_events": bits,
        "zero_bit_events": zero_bits,
        "by_session": by_session,
        "by_source": by_source,
        "by_speaker": by_speaker,
    }


def _top_counter(counter: Counter, n: int = 10) -> str:
    if not counter:
        return "-"
    return ", ".join(f"{k}:{v}" for k, v in counter.most_common(n))


def summarize_file(path: Path, qa_error_limit: int) -> str:
    data = json.loads(path.read_text(encoding="utf-8"))
    cfg = data.get("config", {})
    conv = data.get("conversation", {})
    details = data.get("details", {})
    rq1_rows = {r.get("label"): r for r in _get(data, "rq1_utility.rows", [])}
    rq2 = data.get("rq2_capacity", {})
    rq3 = data.get("rq3_in_record", {})
    rq5 = data.get("rq5_integrity", {})

    lines = []
    lines.append(f"# LoCoMo Result Summary: `{path}`")
    lines.append("")
    lines.append("## Config")
    lines.append(_table(
        ["field", "value"],
        [
            ["conversation", cfg.get("conversation")],
            ["sample_id", conv.get("sample_id")],
            ["max_sessions", cfg.get("max_sessions")],
            ["max_qa", cfg.get("max_qa")],
            ["backend", cfg.get("backend")],
            ["llm_mode", cfg.get("llm_mode")],
            ["baselines", ", ".join(cfg.get("baselines", []))],
            ["dataset_sessions", conv.get("session_count")],
            ["dataset_qa", conv.get("qa_count")],
        ],
    ))
    lines.append("")

    lines.append("## RQ1 Utility / Memory / Capacity")
    rows = []
    for label, row in rq1_rows.items():
        r3_base = rq3.get(label, {}) if isinstance(rq3, dict) else {}
        rows.append([
            label,
            _fmt(row.get("qa_accuracy")),
            _fmt(row.get("qa_f1")),
            _fmt(row.get("qa_bleu1")),
            _fmt(row.get("qa_rougeL")),
            row.get("qa_count"),
            row.get("memory_count"),
            row.get("write_failures"),
            row.get("bits_embedded"),
            _fmt(row.get("capacity_bits_per_decision")),
            _fmt(_get(r3_base, "r3.bit_recovery_rate")),
        ])
    lines.append(_table(["baseline", "acc", "f1", "bleu1", "rougeL", "qa", "mem", "fail", "bits", "bits/decision", "R3 recover"], rows))
    lines.append("")

    if _get(data, "rq1_utility.deltas"):
        lines.append("## RQ1 Deltas")
        delta_rows = []
        for k, v in data["rq1_utility"]["deltas"].items():
            if isinstance(v, dict):
                delta_rows.append([k, _fmt(v.get("qa_f1_delta")), _fmt(v.get("qa_accuracy_delta")), _fmt(v.get("memory_count_delta"))])
        if delta_rows:
            lines.append(_table(["comparison", "f1_delta", "acc_delta", "memory_delta"], delta_rows))
            lines.append("")

    lines.append("## RQ2 Carrier Capacity")
    cap_rows = []
    for label, cap in rq2.items():
        overall = cap.get("overall", {})
        cap_rows.append([label, "ALL", overall.get("decisions"), overall.get("bits_embedded"), _fmt(overall.get("bits_per_decision")), _fmt(overall.get("avg_candidate_set_size")), _fmt(overall.get("avg_entropy")), _fmt(overall.get("acceptance_rate"))])
        for carrier, c in cap.get("by_carrier", {}).items():
            cap_rows.append([label, carrier, c.get("decisions"), c.get("bits_embedded"), _fmt(c.get("bits_per_decision")), _fmt(c.get("avg_candidate_set_size")), _fmt(c.get("avg_entropy")), _fmt(c.get("acceptance_rate"))])
    lines.append(_table(["baseline", "carrier", "decisions", "bits", "bits/decision", "cand", "entropy", "accept"], cap_rows) if cap_rows else "-")
    lines.append("")

    lines.append("## RQ3 In-Record Attribution")
    r3_rows = []
    for label, x in rq3.items():
        r3_rows.append([
            label,
            _fmt(_get(x, "r1.bit_recovery_rate")),
            _fmt(_get(x, "r1.commitment_pass_rate")),
            _fmt(_get(x, "r3.bit_recovery_rate")),
            _fmt(_get(x, "r3.bits_total")),
            _fmt(_get(x, "r3_wrong_key.bit_recovery_rate")),
            _fmt(_get(x, "r3_wrong_key.anchor_signature_valid")),
        ])
    lines.append(_table(["baseline", "R1 recover", "commit", "R3 recover", "R3 bits", "wrong-key recover", "wrong-key sig"], r3_rows) if r3_rows else "-")
    lines.append("")

    lines.append("## RQ4 Robustness")
    robust_rows = []
    for label, x in data.get("rq4_robustness", {}).items():
        if not isinstance(x, dict):
            continue
        for outcome in x.get("outcomes", []) or []:
            if not isinstance(outcome, dict):
                continue
            robust_rows.append([
                label,
                outcome.get("name"),
                _fmt(outcome.get("strength")),
                outcome.get("leaves_affected"),
                _fmt(outcome.get("bit_recovery_pre")),
                _fmt(outcome.get("bit_recovery_post")),
                _fmt(outcome.get("tamper_detection_rate")),
            ])
    lines.append(_table(["baseline", "attack", "strength", "leaves", "pre", "post", "tamper"], robust_rows) if robust_rows else "-")
    lines.append("")

    lines.append("## RQ5 Integrity / Evidence")
    rq5_rows = []
    for label, x in rq5.items():
        if isinstance(x, dict):
            rq5_rows.append([label, _fmt(x.get("evidence_recall_mean")), _fmt(x.get("answerable_rate")), _fmt(x.get("context_dia_id_recall")), _fmt(x.get("qa_count"))])
    lines.append(_table(["baseline", "evidence_recall", "answerable", "context_dia_recall", "qa"], rq5_rows) if rq5_rows else "- see per-QA evidence recall below")
    lines.append("")

    for label, detail in details.items():
        lines.append(f"## Detail: `{label}`")
        events = detail.get("extracted_events", []) or []
        qa_preds = detail.get("qa_predictions", []) or []
        event_stats = _summarize_events(events)
        mistake_rows, qa_stats = _summarize_qa(qa_preds, qa_error_limit)
        lines.append(_table(
            ["metric", "value"],
            [
                ["events/applied/failed", f"{event_stats['events']}/{event_stats['applied']}/{event_stats['failed']}"],
                ["zero_bit_events", event_stats["zero_bit_events"]],
                ["bits_from_events", event_stats["bits_from_events"]],
                ["events_by_session", _top_counter(event_stats["by_session"], 20)],
                ["events_by_speaker", _top_counter(event_stats["by_speaker"])],
                ["qa_predictions", qa_stats["qa_count"]],
                ["evidence_recall_mean", _fmt(qa_stats["evidence_recall_mean"])],
            ],
        ))
        if qa_stats["cat_rows"]:
            lines.append("")
            lines.append("### QA by category")
            lines.append(_table(["cat", "n", "f1", "bleu1", "rougeL", "judge_acc", "evidence_recall"], qa_stats["cat_rows"]))
        if mistake_rows:
            lines.append("")
            lines.append(f"### Worst {len(mistake_rows)} QA examples")
            lines.append(_table(["cat", "f1", "evidence", "question", "gold", "pred"], mistake_rows))
        lines.append("")

    lines.append("## Automatic Reading")
    wm = rq1_rows.get("watermark", {})
    no = rq1_rows.get("no_watermark", {})
    if wm:
        lines.append(f"- **Watermark utility**: F1={_fmt(wm.get('qa_f1'))}, accuracy={_fmt(wm.get('qa_accuracy'))}, memory_count={wm.get('memory_count')}, bits={wm.get('bits_embedded')}.")
    if wm and no:
        lines.append(f"- **Watermark vs no_watermark**: F1 delta={_fmt(_num(wm.get('qa_f1')) - _num(no.get('qa_f1')))}, memory delta={_fmt(_num(wm.get('memory_count')) - _num(no.get('memory_count')))}.")
    wm_r3 = rq3.get("watermark", {}) if isinstance(rq3, dict) else {}
    if wm_r3:
        lines.append(f"- **Attribution**: R3 recovery={_fmt(_get(wm_r3, 'r3.bit_recovery_rate'))}, wrong-key recovery={_fmt(_get(wm_r3, 'r3_wrong_key.bit_recovery_rate'))}.")
    if cfg.get("max_sessions") and conv.get("session_count") and int(cfg.get("max_sessions")) < int(conv.get("session_count")):
        lines.append("- **Coverage warning**: max_sessions < dataset_sessions; QA may ask about unseen sessions.")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Summarize MemMark LoCoMo JSON results.")
    parser.add_argument("path", help="Result JSON file or directory containing .json files.")
    parser.add_argument("--out", help="Write Markdown summary to this file.")
    parser.add_argument("--qa-error-limit", type=int, default=8)
    args = parser.parse_args()

    path = Path(args.path)
    files = sorted(path.glob("*.json")) if path.is_dir() else [path]
    summaries = [summarize_file(f, args.qa_error_limit) for f in files]
    text = "\n\n---\n\n".join(summaries)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
