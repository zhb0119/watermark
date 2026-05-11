from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from memmark.benchmarks.longmemeval.loader import LongMemEvalExample
from memmark.benchmarks.locomo.driver import _capacity_stats
from memmark.core.types import AuditRecord, DecisionPoint, SessionHeader
from memmark.sdk.memory_watermarker import MemoryWatermarker


@dataclass
class LongMemEvalDriverResult:
    question_id: str
    question_type: str
    question: str
    answer_gold: str
    hypothesis: str = ""
    answer_session_ids: List[str] = field(default_factory=list)
    extracted_events: List[Dict[str, Any]] = field(default_factory=list)
    memory_snapshot_final: List[Dict[str, Any]] = field(default_factory=list)
    qa_trace: Dict[str, Any] = field(default_factory=dict)
    decisions: List[DecisionPoint] = field(default_factory=list)
    audits: List[AuditRecord] = field(default_factory=list)
    anchor: Optional[SessionHeader] = None
    capacity_stats: Dict[str, Any] = field(default_factory=dict)
    payload_bits: str = ""
    audits_count: int = 0
    bits_embedded: int = 0
    write_failures: int = 0


class LongMemEvalDriver:
    def __init__(
        self,
        *,
        watermarker: MemoryWatermarker,
        llm_client: Any,
        topk_context: int = 10,
        ingestion_level: str = "session",
        max_sessions: Optional[int] = None,
        max_turns_per_session: Optional[int] = None,
        max_context_chars: int = 12000,
        progress: bool = False,
        progress_context: Optional[Dict[str, Any]] = None,
    ) -> None:
        self.wm = watermarker
        self.llm_client = llm_client
        self.topk_context = topk_context
        if ingestion_level not in {"turn", "session"}:
            raise ValueError("ingestion_level must be one of: turn, session")
        self.ingestion_level = ingestion_level
        self.max_sessions = max_sessions
        self.max_turns_per_session = max_turns_per_session
        self.max_context_chars = max_context_chars
        self.progress = progress
        self.progress_context = progress_context or {}

    def run(self, example: LongMemEvalExample) -> LongMemEvalDriverResult:
        result = LongMemEvalDriverResult(
            question_id=example.question_id,
            question_type=example.question_type,
            question=example.question,
            answer_gold=example.answer,
            answer_session_ids=list(example.answer_session_ids),
        )
        sessions = list(zip(example.haystack_session_ids, example.haystack_dates, example.haystack_sessions))
        if self.max_sessions is not None:
            sessions = sessions[: self.max_sessions]
        self._line(f"[start] qid={example.question_id} sessions={len(sessions)} baseline={self.progress_context.get('baseline', '')}")
        for session_i, (session_id, session_date, turns) in enumerate(sessions, start=1):
            if self.max_turns_per_session is not None:
                turns = turns[: self.max_turns_per_session]
            self._line(f"[session] qid={example.question_id} {session_i}/{len(sessions)} session_id={session_id} turns={len(turns)}")
            if self.ingestion_level == "session":
                text, roles, dia_ids = _render_session_event(session_id, session_date, turns)
                if text:
                    self._apply_event(
                        text,
                        dia_ids=dia_ids,
                        session_index=session_i,
                        session_date_time=session_date,
                        speaker=roles,
                        source_label=f"session:{session_id}",
                        result=result,
                    )
                continue
            for turn_i, turn in enumerate(turns, start=1):
                if not isinstance(turn, dict):
                    continue
                role = str(turn.get("role") or "")
                content = str(turn.get("content") or "").strip()
                if not content:
                    continue
                source_label = f"session:{session_id}:turn:{turn_i}"
                text = f"[{session_date}] {role}: {content}"
                self._apply_event(
                    text,
                    dia_ids=[session_id, f"{session_id}_{turn_i}"],
                    session_index=session_i,
                    session_date_time=session_date,
                    speaker=role,
                    source_label=source_label,
                    result=result,
                )
        result.anchor = self.wm.seal_session()
        result.audits = list(self.wm.audits)
        result.decisions = [
            DecisionPoint(
                decision_id=a.decision_id,
                tau=a.tau,
                candidates=a.candidates,
                probabilities=a.probabilities,
                context=a.context,
                round_num=a.round_num,
                nonce=a.nonce,
                watermark_version=a.watermark_version,
            )
            for a in result.audits
            if a.candidates and a.probabilities
        ]
        result.capacity_stats = _capacity_stats(result.audits, result.decisions)
        result.payload_bits = self.wm.payload_bits
        result.memory_snapshot_final = self.wm.backend.snapshot()
        result.audits_count = len(result.audits)
        result.bits_embedded = sum(a.bits_embedded for a in result.audits)
        result.hypothesis, result.qa_trace = self._answer(example)
        result.write_failures = sum(1 for item in result.extracted_events if not item.get("applied"))
        self._line(f"[done] qid={example.question_id} memories={len(result.memory_snapshot_final)} llm={result.audits_count} bits={result.bits_embedded}")
        return result

    def _apply_event(
        self,
        text: str,
        *,
        dia_ids: List[str],
        session_index: int,
        session_date_time: str,
        speaker: str,
        source_label: str,
        result: LongMemEvalDriverResult,
    ) -> None:
        self.wm.set_event_context(
            dia_ids=list(dia_ids),
            session_index=session_index,
            session_date_time=session_date_time,
            speaker=speaker,
            source_label=source_label,
        )
        before = len(self.wm.audits)
        try:
            record = self.wm.backend.apply(
                {
                    "op": "add_memory",
                    "text": text,
                    "dia_ids": list(dia_ids),
                    "session_index": session_index,
                    "session_date_time": session_date_time,
                    "speaker": speaker,
                }
            )
        except Exception as exc:
            result.extracted_events.append(
                {
                    "source": source_label,
                    "speaker": speaker,
                    "text": text,
                    "applied": False,
                    "reason": f"apply_fail: {type(exc).__name__}",
                }
            )
            self._line(f"[apply failed] source={source_label} reason={type(exc).__name__}")
            return
        finally:
            self.wm.clear_event_context()
        new_audits = self.wm.audits[before:]
        result.extracted_events.append(
            {
                "source": source_label,
                "speaker": speaker,
                "text": text,
                "applied": True,
                "llm_calls": len(new_audits),
                "bits_embedded": sum(a.bits_embedded for a in new_audits),
                "memory_record": record,
            }
        )

    def _answer(self, example: LongMemEvalExample) -> tuple[str, Dict[str, Any]]:
        try:
            ctx = self.wm.backend.qa_context(
                example.question,
                k=self.topk_context,
                llm_client=self.llm_client,
            )
        except Exception as exc:
            ctx = {"mode": "context", "text": "", "error": f"{type(exc).__name__}: {exc}"}
        context_text = str(ctx.get("context") or ctx.get("retrieved_context") or ctx.get("text") or "")[: self.max_context_chars]
        prompt = _build_answer_prompt(example, context_text)
        try:
            answer = (self.llm_client.complete([{"role": "user", "content": prompt}], temperature=0.0) or "").strip()
        except Exception as exc:
            answer = ""
            ctx["answer_error"] = f"{type(exc).__name__}: {exc}"
        trace = {
            "mode": ctx.get("mode", "context"),
            "context": context_text,
            "context_chars": len(context_text),
            "user_prompt": prompt,
            "retrieval_error": ctx.get("retrieval_error") or ctx.get("error") or "",
        }
        return answer, trace

    def _line(self, text: str) -> None:
        if self.progress:
            print(text, file=sys.stderr, flush=True)


def _build_answer_prompt(example: LongMemEvalExample, context_text: str) -> str:
    return (
        "I will give you memory records from previous conversations between you and a user. "
        "Please answer the question based only on the relevant memory records.\n\n"
        f"Memory Records:\n{context_text or '(no relevant memories found)'}\n\n"
        f"Current Date: {example.question_date}\n"
        f"Question: {example.question}\n"
        "Answer:"
    )


def _render_session_event(session_id: str, session_date: str, turns: List[Dict[str, Any]]) -> tuple[str, str, List[str]]:
    lines = [f"[{session_date}] Session {session_id}"]
    dia_ids = [session_id]
    roles = []
    for turn_i, turn in enumerate(turns, start=1):
        if not isinstance(turn, dict):
            continue
        role = str(turn.get("role") or "")
        content = str(turn.get("content") or "").strip()
        if not content:
            continue
        roles.append(role)
        dia_ids.append(f"{session_id}_{turn_i}")
        lines.append(f"{role}: {content}")
    if len(lines) == 1:
        return "", "", [session_id]
    return "\n".join(lines), ",".join(dict.fromkeys(roles)), dia_ids


def result_to_jsonable(result: LongMemEvalDriverResult) -> Dict[str, Any]:
    return json.loads(json.dumps(result, default=_default_json, ensure_ascii=False))


def _default_json(obj: Any) -> Any:
    if hasattr(obj, "__dict__"):
        return obj.__dict__
    return str(obj)
