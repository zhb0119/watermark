from __future__ import annotations

import argparse
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


_SESSION_RE = re.compile(r"session_(\d+)$")


def _table(headers: list[str], rows: list[list[Any]]) -> str:
    out = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for row in rows:
        out.append("| " + " | ".join(_cell(x) for x in row) + " |")
    return "\n".join(out)


def _cell(x: Any) -> str:
    text = "" if x is None else str(x)
    return text.replace("|", "/").replace("\n", " ")


def _short(text: str, n: int = 140) -> str:
    text = " ".join((text or "").split())
    return text if len(text) <= n else text[: n - 1] + "…"


def _load_sample(locomo_path: Path, conversation_index: int) -> dict[str, Any]:
    data = json.loads(locomo_path.read_text(encoding="utf-8"))
    return data[conversation_index]


def _turn_index(sample: dict[str, Any]) -> dict[str, dict[str, Any]]:
    conv = sample.get("conversation", {})
    out = {}
    for key, turns in conv.items():
        m = _SESSION_RE.fullmatch(key)
        if not m or not isinstance(turns, list):
            continue
        session = int(m.group(1))
        date_time = conv.get(f"session_{session}_date_time", "")
        for turn in turns:
            dia_id = turn.get("dia_id")
            if not dia_id:
                continue
            out[dia_id] = {
                "session": session,
                "date_time": date_time,
                "speaker": turn.get("speaker", ""),
                "text": turn.get("text", ""),
            }
    return out


def _event_dia_ids(event: dict[str, Any]) -> list[str]:
    record = event.get("memory_record") if isinstance(event.get("memory_record"), dict) else {}
    ids = record.get("dia_ids") or event.get("dia_ids") or []
    return [x for x in ids if isinstance(x, str)]


def _source_kind(source: str) -> str:
    if source.startswith("turn"):
        return "turn"
    if source.startswith("fact"):
        return "fact"
    return source or "unknown"


def summarize(result_path: Path, locomo_path: Path, baseline: str, conversation: int | None, detail_limit: int) -> str:
    result = json.loads(result_path.read_text(encoding="utf-8"))
    if conversation is None:
        conversation = int(result.get("config", {}).get("conversation", 0))
    sample = _load_sample(locomo_path, conversation)
    turns = _turn_index(sample)
    detail = result.get("details", {}).get(baseline, {})
    events = detail.get("extracted_events", []) or []
    applied = [e for e in events if e.get("applied")]

    dia_to_events: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for event in applied:
        for dia_id in _event_dia_ids(event):
            dia_to_events[dia_id].append(event)

    written_ids = set(dia_to_events)
    qa_items = sample.get("qa", []) or []
    qa_gold_ids = {x for q in qa_items for x in (q.get("evidence") or []) if isinstance(x, str)}
    covered_gold_ids = qa_gold_ids & written_ids
    missing_gold_ids = qa_gold_ids - written_ids

    lines = []
    lines.append(f"# LoCoMo Memory Write Analysis: `{result_path}`")
    lines.append("")
    lines.append("## Overview")
    lines.append(_table(
        ["field", "value"],
        [
            ["baseline", baseline],
            ["conversation", conversation],
            ["sample_id", sample.get("sample_id")],
            ["events_applied", len(applied)],
            ["unique_written_dia_ids", len(written_ids)],
            ["dataset_turns", len(turns)],
            ["qa_count", len(qa_items)],
            ["unique_qa_gold_dia_ids", len(qa_gold_ids)],
            ["qa_gold_written", len(covered_gold_ids)],
            ["qa_gold_missing", len(missing_gold_ids)],
            ["write_coverage_all_turns", f"{len(written_ids) / len(turns):.3f}" if turns else "-"],
            ["write_coverage_qa_gold", f"{len(covered_gold_ids) / len(qa_gold_ids):.3f}" if qa_gold_ids else "-"],
        ],
    ))
    lines.append("")

    by_session_total = Counter(v["session"] for v in turns.values())
    by_session_written = Counter(turns[d]["session"] for d in written_ids if d in turns)
    by_session_gold = Counter(turns[d]["session"] for d in qa_gold_ids if d in turns)
    by_session_gold_written = Counter(turns[d]["session"] for d in covered_gold_ids if d in turns)
    session_rows = []
    for session in sorted(by_session_total):
        gold = by_session_gold[session]
        gold_written = by_session_gold_written[session]
        session_rows.append([
            session,
            by_session_total[session],
            by_session_written[session],
            f"{by_session_written[session] / by_session_total[session]:.3f}" if by_session_total[session] else "-",
            gold,
            gold_written,
            f"{gold_written / gold:.3f}" if gold else "-",
        ])
    lines.append("## Session Coverage")
    lines.append(_table(["session", "turns", "written", "written/turns", "qa_gold", "qa_gold_written", "gold_cov"], session_rows))
    lines.append("")

    source_rows = []
    by_source = Counter()
    by_kind = Counter()
    for event in applied:
        source = str(event.get("source", ""))
        ids = _event_dia_ids(event)
        by_source[source] += len(ids)
        by_kind[_source_kind(source)] += len(ids)
    for kind, n in by_kind.most_common():
        source_rows.append([kind, n])
    lines.append("## Write Source Type")
    lines.append(_table(["source_kind", "dia_id_mentions"], source_rows) if source_rows else "-")
    lines.append("")

    missing_rows = []
    for dia_id in sorted(missing_gold_ids, key=lambda x: (turns.get(x, {}).get("session", 999), x)):
        t = turns.get(dia_id, {})
        qs = [q.get("question", "") for q in qa_items if dia_id in (q.get("evidence") or [])]
        missing_rows.append([dia_id, t.get("session", ""), t.get("speaker", ""), _short(t.get("text", "")), _short(" ; ".join(qs), 180)])
    lines.append("## QA Gold Evidence NOT Written")
    lines.append(_table(["dia_id", "session", "speaker", "turn_text", "questions"], missing_rows[:detail_limit]) if missing_rows else "All QA gold evidence dia_ids were written.")
    if len(missing_rows) > detail_limit:
        lines.append(f"\nShowing {detail_limit}/{len(missing_rows)} missing gold dia_ids.")
    lines.append("")

    written_rows = []
    for dia_id in sorted(written_ids, key=lambda x: (turns.get(x, {}).get("session", 999), x)):
        t = turns.get(dia_id, {})
        evs = dia_to_events[dia_id]
        sources = ",".join(sorted({str(e.get("source", "")) for e in evs}))
        mem_text = " ; ".join(_short(str(e.get("text", "")), 90) for e in evs[:2])
        is_gold = "Y" if dia_id in qa_gold_ids else ""
        written_rows.append([dia_id, t.get("session", ""), t.get("speaker", ""), is_gold, sources, _short(t.get("text", ""), 110), mem_text])
    lines.append("## Written Turns")
    lines.append(_table(["dia_id", "session", "speaker", "qa_gold", "source", "original_turn", "memory_text"], written_rows[:detail_limit]))
    if len(written_rows) > detail_limit:
        lines.append(f"\nShowing {detail_limit}/{len(written_rows)} written dia_ids.")
    lines.append("")

    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Analyze which LoCoMo turns were written into memory.")
    parser.add_argument("result", type=Path)
    parser.add_argument("--locomo", type=Path, default=Path("locomo/data/locomo10.json"))
    parser.add_argument("--baseline", default="watermark")
    parser.add_argument("--conversation", type=int, default=None)
    parser.add_argument("--limit", type=int, default=80)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    text = summarize(args.result, args.locomo, args.baseline, args.conversation, args.limit)
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        args.out.write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
