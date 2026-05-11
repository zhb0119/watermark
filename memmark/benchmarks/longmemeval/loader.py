from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List


@dataclass
class LongMemEvalExample:
    question_id: str
    question_type: str
    question: str
    answer: str
    question_date: str
    haystack_session_ids: List[str] = field(default_factory=list)
    haystack_dates: List[str] = field(default_factory=list)
    haystack_sessions: List[List[Dict[str, Any]]] = field(default_factory=list)
    answer_session_ids: List[str] = field(default_factory=list)


def load_longmemeval(path: str | Path) -> List[LongMemEvalExample]:
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    return [_example(item) for item in raw]


def _example(item: Dict[str, Any]) -> LongMemEvalExample:
    return LongMemEvalExample(
        question_id=str(item.get("question_id") or ""),
        question_type=str(item.get("question_type") or ""),
        question=str(item.get("question") or ""),
        answer=str(item.get("answer") or ""),
        question_date=str(item.get("question_date") or ""),
        haystack_session_ids=[str(x) for x in item.get("haystack_session_ids") or []],
        haystack_dates=[str(x) for x in item.get("haystack_dates") or []],
        haystack_sessions=list(item.get("haystack_sessions") or []),
        answer_session_ids=[str(x) for x in item.get("answer_session_ids") or []],
    )
