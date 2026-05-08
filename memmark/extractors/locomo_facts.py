"""LoCoMo-official per-session fact extractor.

Uses `CONVERSATION2FACTS_PROMPT` verbatim from
`locomo/generative_agents/memory_utils.py` so the extracted
"observations" are directly comparable to the LoCoMo paper's
session-observation baseline. Each fact carries the source dia_ids
that produced it (LoCoMo's evidence ground truth).

This is the Mem0 / A-MEM style ingestion path: from a multi-turn
session, ask the LLM to enumerate "concise factual observations
about each speaker" with `[D1:3]`-style dialog id citations, then
parse them back into structured `ExtractedFact` records.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from typing import Any, List, Sequence


# Verbatim from locomo/generative_agents/memory_utils.py
CONVERSATION2FACTS_PROMPT = (
    "Write a concise and short list of all possible OBSERVATIONS about "
    "each speaker that can be gathered from the CONVERSATION. Each "
    "dialog in the conversation contains a dialogue id within square "
    "brackets. Each observation should contain a piece of information "
    "about the speaker, and also include the dialog id of the dialogs "
    "from which the information is taken. The OBSERVATIONS should be "
    "objective factual information about the speaker that can be used "
    "as a database about them. Avoid abstract observations about the "
    "dynamics between the two speakers such as 'speaker is supportive', "
    "'speaker appreciates' etc. Do not leave out any information from "
    "the CONVERSATION. "
    "Important: respond with a strict JSON object whose keys are speaker "
    "names and whose values are arrays of [observation_text, dia_id] "
    'pairs. Example: {"Alice": [["Alice lives in Berlin", "D1:3"], '
    '["Alice has a dog named Pepper", "D1:7"]], "Bob": [...]}'
)


_DIA_ID_RE = re.compile(r"D\d+:\d+")


@dataclass
class ExtractedFact:
    text: str
    dia_ids: List[str] = field(default_factory=list)
    speaker: str = ""

    def as_event_text(self) -> str:
        if self.speaker:
            return f"{self.speaker}: {self.text}"
        return self.text


def extract_session_facts(
    *,
    llm_client: Any,
    speaker_a: str,
    speaker_b: str,
    session_index: int,
    session_date_time: str,
    turns: Sequence[Any],
    max_facts: int = 30,
) -> List[ExtractedFact]:
    """Run LoCoMo's `CONVERSATION2FACTS_PROMPT` on one session.

    Returns up to `max_facts` ExtractedFact records.
    """

    if not turns:
        return []

    conversation = _format_conversation(session_date_time, turns)
    user_prompt = (
        "CONVERSATION:\n"
        f"{conversation}\n\n"
        f"Speakers: {speaker_a}, {speaker_b}.\n"
        f"Return a strict JSON object as described in the system prompt. "
        f"At most {max_facts} observations total."
    )
    messages = [
        {"role": "system", "content": CONVERSATION2FACTS_PROMPT},
        {"role": "user", "content": user_prompt},
    ]
    try:
        raw = llm_client.complete(messages, temperature=0.0)
    except Exception:
        return []
    return _parse_facts(raw, valid_speakers={speaker_a, speaker_b})


def _format_conversation(date_time: str, turns: Sequence[Any]) -> str:
    lines = []
    if date_time:
        lines.append(date_time)
    for t in turns:
        speaker = getattr(t, "speaker", "")
        dia_id = getattr(t, "dia_id", "")
        text = getattr(t, "text", "") or ""
        text = text.replace('"', '\\"')
        lines.append(f'[{dia_id}] {speaker} said, "{text}"')
    return "\n".join(lines)


def _parse_facts(raw: str, *, valid_speakers: set) -> List[ExtractedFact]:
    text = (raw or "").strip()
    if not text:
        return []
    # Find first `{` and matching `}` for the response object
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end < start:
        return []
    try:
        parsed = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return []
    facts: List[ExtractedFact] = []
    if isinstance(parsed, dict):
        for speaker, items in parsed.items():
            if not isinstance(items, list):
                continue
            for item in items:
                fact_text, dia_ids = _normalize_item(item)
                if not fact_text:
                    continue
                facts.append(
                    ExtractedFact(
                        text=fact_text,
                        dia_ids=dia_ids,
                        speaker=str(speaker),
                    )
                )
    return facts


def _normalize_item(item: Any) -> tuple[str, List[str]]:
    """Accept several LLM JSON shapes: [text, dia_id], {text, dia_ids}, etc."""

    if isinstance(item, str):
        return item.strip(), _scan_dia_ids(item)
    if isinstance(item, list):
        if not item:
            return "", []
        text = str(item[0]).strip()
        dia_ids: List[str] = []
        for x in item[1:]:
            if isinstance(x, str):
                dia_ids.extend(_scan_dia_ids(x))
            elif isinstance(x, list):
                for xx in x:
                    if isinstance(xx, str):
                        dia_ids.extend(_scan_dia_ids(xx))
        if not dia_ids:
            dia_ids = _scan_dia_ids(text)
        return text, list(dict.fromkeys(dia_ids))
    if isinstance(item, dict):
        text = (
            item.get("observation")
            or item.get("text")
            or item.get("fact")
            or ""
        )
        text = str(text).strip()
        raw_ids = item.get("dia_ids") or item.get("dia_id") or []
        if isinstance(raw_ids, str):
            raw_ids = _scan_dia_ids(raw_ids)
        dia_ids = [d for d in raw_ids if isinstance(d, str)]
        if not dia_ids:
            dia_ids = _scan_dia_ids(text)
        return text, list(dict.fromkeys(dia_ids))
    return "", []


def _scan_dia_ids(text: str) -> List[str]:
    return _DIA_ID_RE.findall(text or "")
