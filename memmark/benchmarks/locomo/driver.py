"""LoCoMo driver — replays a conversation through MemMark.

Each backend has its own preferred ingestion granularity (matching
its upstream LoCoMo / LongMemEval official protocol):

  - "turn"    : per-turn episode with session date_time
                Graphiti  (graphiti/tests/evals/eval_e2e_graph_building.py)
                JsonStore (smoke default)
  - "session" : full session text as one document
                Cognee    (cognee/eval_framework benchmark adapters)
  - "fact"    : LoCoMo-official `CONVERSATION2FACTS_PROMPT` per
                session → N facts each with dia_id evidence
                A-MEM     (Mem0-style fact extraction; agentic_memory
                          paper protocol)

The driver reads `backend.preferred_ingestion_mode` and dispatches
automatically, so each backend gets the input format its upstream
benchmarks use.

After the conversation ends, run all `qa` questions through the
LoCoMo-official QA prompt + F1 judge against the final snapshot.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from memmark.benchmarks.locomo.loader import (
    LoCoMoConversation,
    LoCoMoQuestion,
    LoCoMoSession,
    LoCoMoTurn,
)
from memmark.benchmarks.locomo.qa_eval import (
    bleu1,
    make_locomo_qa_judge,
    make_locomo_qa_responder,
    rouge_l,
    score_one,
)
from memmark.core.types import AuditRecord, DecisionPoint, SessionHeader
from memmark.sdk.memory_watermarker import EvolveResult, MemoryWatermarker


TurnFilter = Callable[[LoCoMoTurn, str], bool]
QAJudge = Callable[[LoCoMoQuestion, str], bool]
# qa_responder takes the question + a pre-rendered memory context
# string (produced by `backend.qa_context(question)`).
QAResponder = Callable[[LoCoMoQuestion, str], str]


@dataclass
class LoCoMoDriverResult:
    sample_id: str
    decisions: List[DecisionPoint] = field(default_factory=list)
    audits: List[AuditRecord] = field(default_factory=list)
    anchor: Optional[SessionHeader] = None
    memory_snapshot_final: List[Dict[str, Any]] = field(default_factory=list)
    qa_predictions: List[Dict[str, Any]] = field(default_factory=list)
    capacity_stats: Dict[str, Any] = field(default_factory=dict)
    extracted_events: List[Dict[str, Any]] = field(default_factory=list)
    payload_bits: str = ""

    @property
    def bits_embedded_total(self) -> int:
        return sum(a.bits_embedded for a in self.audits)

    @property
    def qa_accuracy(self) -> float:
        if not self.qa_predictions:
            return 0.0
        correct = sum(1 for q in self.qa_predictions if q.get("correct"))
        return correct / len(self.qa_predictions)

    @property
    def qa_f1_mean(self) -> float:
        return self._mean_metric("f1")

    @property
    def qa_bleu1_mean(self) -> float:
        return self._mean_metric("bleu1")

    @property
    def qa_rougeL_mean(self) -> float:
        return self._mean_metric("rougeL")

    @property
    def qa_judge_accuracy(self) -> float:
        return self._mean_metric("judge_correct", boolean=True)

    @property
    def qa_metrics_by_category(self) -> Dict[int, Dict[str, float]]:
        """Per-category {f1, bleu1, rougeL, judge_acc, n} (LoCoMo Table 4 shape)."""

        out: Dict[int, Dict[str, float]] = {}
        groups: Dict[int, List[Dict[str, Any]]] = {}
        for q in self.qa_predictions:
            groups.setdefault(int(q.get("category", 0)), []).append(q)
        for cat, items in groups.items():
            n = len(items)
            out[cat] = {
                "n": float(n),
                "f1": sum(q.get("f1", 0.0) for q in items) / n,
                "bleu1": sum(q.get("bleu1", 0.0) for q in items) / n,
                "rougeL": sum(q.get("rougeL", 0.0) for q in items) / n,
                "judge_acc": sum(
                    1 for q in items if q.get("judge_correct")
                ) / n,
            }
        return out

    def _mean_metric(self, key: str, *, boolean: bool = False) -> float:
        if not self.qa_predictions:
            return 0.0
        if boolean:
            return sum(1 for q in self.qa_predictions if q.get(key)) / len(self.qa_predictions)
        return sum(q.get(key, 0.0) for q in self.qa_predictions) / len(self.qa_predictions)


class LoCoMoDriver:
    """Replay a single LoCoMo conversation through a MemoryWatermarker.

    `turn_filter` lets you drop chitchat / greetings; default keeps
    every turn (so the backend sees the full dialog and does its own
    native ingestion / extraction).
    """

    def __init__(
        self,
        *,
        watermarker: MemoryWatermarker,
        turn_filter: Optional[TurnFilter] = None,
        qa_responder: Optional[QAResponder] = None,
        qa_judge: Optional[QAJudge] = None,
        max_sessions: Optional[int] = None,
        max_qa: Optional[int] = None,
        max_turns_per_session: Optional[int] = None,
        fact_extractor_llm: Optional[Any] = None,
        # Backwards-compat: accept the deprecated `memory_extractor`
        # kwarg but ignore it.
        memory_extractor: Optional[Any] = None,
    ) -> None:
        self.wm = watermarker
        self.turn_filter = turn_filter or _keep_all_substantive_turns
        self.qa_responder = qa_responder or _default_qa_responder
        self.qa_judge = qa_judge or _default_qa_judge
        self.max_sessions = max_sessions
        self.max_qa = max_qa
        self.max_turns_per_session = max_turns_per_session
        self.fact_extractor_llm = fact_extractor_llm
        self._legacy_extractor_warned = bool(memory_extractor)

    def run(self, conversation: LoCoMoConversation) -> LoCoMoDriverResult:
        result = LoCoMoDriverResult(
            sample_id=conversation.sample_id,
            payload_bits=self.wm.payload_bits,
        )
        sessions = conversation.sessions
        if self.max_sessions is not None:
            sessions = sessions[: self.max_sessions]

        ingestion_mode = getattr(self.wm.backend, "preferred_ingestion_mode", "turn")
        recent_dialog_ids: List[str] = []
        for session in sessions:
            turns = session.turns
            if self.max_turns_per_session is not None:
                turns = turns[: self.max_turns_per_session]
            if ingestion_mode == "session":
                self._ingest_session_mode(
                    conversation, session, turns, result, recent_dialog_ids
                )
            elif ingestion_mode == "fact":
                self._ingest_fact_mode(
                    conversation, session, turns, result, recent_dialog_ids
                )
            else:  # "turn" default
                self._ingest_turn_mode(
                    conversation, session, turns, result, recent_dialog_ids
                )

        # Audits and decisions accumulated *inside* the SDK's LLM
        # calls during ingest. The sampler holds them; copy into the
        # result so downstream RQ runners see the same shape they used
        # to (per-LLM-call now, instead of per-event).
        result.audits = list(self.wm.audits)
        result.decisions = [
            DecisionPoint(
                decision_id=a.decision_id,
                tau=a.tau,
                candidates=a.candidates or [],
                probabilities=a.probabilities or {},
                context=a.context,
                round_num=a.round_num,
                nonce=a.nonce,
                watermark_version=a.watermark_version,
            )
            for a in result.audits
        ]
        result.anchor = self.wm.seal_session()
        result.memory_snapshot_final = self.wm.backend.snapshot()
        result.capacity_stats = _capacity_stats(result.audits, result.decisions)

        qa_list = conversation.qa
        if self.max_qa is not None:
            qa_list = qa_list[: self.max_qa]
        for q in qa_list:
            # Canonical alignment: each backend has a per-question
            # retrieve API. `qa_context` returns either:
            #   mode=context  → the backend gives back rendered memory
            #                   text; we wrap it in LoCoMo's QA prompt.
            #   mode=answer   → the backend already produced the answer
            #                   (Cognee GRAPH_COMPLETION); we use it.
            ctx = self.wm.backend.qa_context(q.question, k=10)
            if ctx.get("mode") == "answer":
                answer = (ctx.get("text") or "").strip()
            else:
                answer = self.qa_responder(q, ctx.get("text") or "")
            f1 = score_one(answer, q.answer, q.category)
            bleu = bleu1(answer, q.answer)
            rouge = rouge_l(answer, q.answer)
            correct = bool(self.qa_judge(q, answer))
            evidence_recall = _evidence_recall(q, result.memory_snapshot_final)
            result.qa_predictions.append(
                {
                    "question": q.question,
                    "answer_gold": q.answer,
                    "answer_pred": answer,
                    "category": q.category,
                    "evidence": q.evidence,
                    "f1": f1,
                    "bleu1": bleu,
                    "rougeL": rouge,
                    "judge_correct": correct,
                    "correct": correct,  # backwards-compat alias
                    "evidence_recall": evidence_recall,
                }
            )
        return result


    # ----------------------------------------------------------- #
    # Per-mode ingestion helpers
    # ----------------------------------------------------------- #

    def _ingest_turn_mode(
        self,
        conversation: LoCoMoConversation,
        session: LoCoMoSession,
        turns: List[LoCoMoTurn],
        result: "LoCoMoDriverResult",
        recent_dialog_ids: List[str],
    ) -> None:
        """Per-turn ingestion (Graphiti / JsonStore default).

        Each LoCoMo turn becomes one memory event; the operation
        carries the session's date_time so Graphiti uses it as
        `reference_time` (matching `eval_e2e_graph_building.py`).
        """

        for turn in turns:
            if not self.turn_filter(turn, session.summary):
                continue
            recent_dialog_ids[:] = (recent_dialog_ids + [turn.dia_id])[-8:]
            event_text = _format_turn(turn, session.date_time)
            self._evolve_one(
                event_text,
                dia_ids=[turn.dia_id],
                session_index=session.index,
                session_date_time=session.date_time,
                speaker=turn.speaker,
                recent_dialog_ids=recent_dialog_ids,
                result=result,
                source_label=f"{turn.dia_id}",
            )

    def _ingest_session_mode(
        self,
        conversation: LoCoMoConversation,
        session: LoCoMoSession,
        turns: List[LoCoMoTurn],
        result: "LoCoMoDriverResult",
        recent_dialog_ids: List[str],
    ) -> None:
        """Document-level ingestion (Cognee default).

        The whole filtered session is concatenated and pushed as one
        document; cognify() / its native pipeline does the entity /
        relation extraction internally.
        """

        kept = [t for t in turns if self.turn_filter(t, session.summary)]
        if not kept:
            return
        body = _format_session_text(session, kept)
        all_dia_ids = [t.dia_id for t in kept]
        recent_dialog_ids[:] = (recent_dialog_ids + all_dia_ids)[-8:]
        self._evolve_one(
            body,
            dia_ids=all_dia_ids,
            session_index=session.index,
            session_date_time=session.date_time,
            speaker="",
            recent_dialog_ids=recent_dialog_ids,
            result=result,
            source_label=f"session_{session.index}",
        )

    def _ingest_fact_mode(
        self,
        conversation: LoCoMoConversation,
        session: LoCoMoSession,
        turns: List[LoCoMoTurn],
        result: "LoCoMoDriverResult",
        recent_dialog_ids: List[str],
    ) -> None:
        """LoCoMo / Mem0 / A-MEM style fact extraction.

        Runs `CONVERSATION2FACTS_PROMPT` (LoCoMo official) on the
        session, producing N facts each with their dia_id evidence,
        then pushes each fact as a memory event.
        """

        kept = [t for t in turns if self.turn_filter(t, session.summary)]
        if not kept or self.fact_extractor_llm is None:
            # Fallback to turn-level if no LLM is configured (e.g.
            # stub mode). Backends that need facts will still get
            # something plausible.
            self._ingest_turn_mode(
                conversation, session, kept, result, recent_dialog_ids
            )
            return

        from memmark.extractors import extract_session_facts

        facts = extract_session_facts(
            llm_client=self.fact_extractor_llm,
            speaker_a=conversation.speaker_a,
            speaker_b=conversation.speaker_b,
            session_index=session.index,
            session_date_time=session.date_time,
            turns=kept,
        )

        if not facts:
            # LLM gave nothing — fall back so we still ingest something.
            self._ingest_turn_mode(
                conversation, session, kept, result, recent_dialog_ids
            )
            return

        for fact in facts:
            recent_dialog_ids[:] = (recent_dialog_ids + fact.dia_ids)[-8:]
            self._evolve_one(
                fact.as_event_text(),
                dia_ids=fact.dia_ids or [t.dia_id for t in kept[:1]],
                session_index=session.index,
                session_date_time=session.date_time,
                speaker=fact.speaker,
                recent_dialog_ids=recent_dialog_ids,
                result=result,
                source_label=f"fact_{session.index}",
            )

    def _evolve_one(
        self,
        event_text: str,
        *,
        dia_ids: List[str],
        session_index: int,
        session_date_time: str,
        speaker: str,
        recent_dialog_ids: List[str],
        result: "LoCoMoDriverResult",
        source_label: str,
    ) -> None:
        """Push one memory event into the backend.

        Watermark bits are embedded inside the backend's own internal
        LLM calls (intercepted by ``WatermarkedSampler``). The driver
        just hands the SDK the event text; per-LLM-call audit records
        accumulate in ``self.wm.audits`` automatically.

        We thread LoCoMo metadata into the sampler's event_context so
        each audit record can be linked back to the dia_id that
        triggered the LLM cascade.
        """

        self.wm.set_event_context(
            dia_ids=list(dia_ids),
            session_index=session_index,
            session_date_time=session_date_time,
            speaker=speaker,
            recent_dialog_ids=list(recent_dialog_ids),
            source_label=source_label,
        )
        before = len(self.wm.audits)
        operation = {
            "op": "add_memory",
            "text": event_text,
            "dia_ids": list(dia_ids),
            "session_index": session_index,
            "session_date_time": session_date_time,
            "speaker": speaker,
        }
        try:
            self.wm.backend.apply(operation)
        except Exception as exc:
            result.extracted_events.append(
                {
                    "session": session_index,
                    "source": source_label,
                    "speaker": speaker,
                    "text": event_text,
                    "applied": False,
                    "reason": f"apply_fail: {exc.__class__.__name__}",
                }
            )
            self.wm.clear_event_context()
            return
        finally:
            self.wm.clear_event_context()

        new_audits = self.wm.audits[before:]
        bits_for_event = sum(a.bits_embedded for a in new_audits)
        result.extracted_events.append(
            {
                "session": session_index,
                "source": source_label,
                "speaker": speaker,
                "text": event_text,
                "applied": True,
                "llm_calls": len(new_audits),
                "bits_embedded": bits_for_event,
            }
        )


# --------------------------------------------------------------- #
# Capacity stats — copied from before, identical contract
# --------------------------------------------------------------- #


def _capacity_stats(
    audits: List[AuditRecord], decisions: List[DecisionPoint]
) -> Dict[str, Any]:
    if not audits:
        return {
            "decisions": 0,
            "bits_embedded": 0,
            "bits_per_decision": 0.0,
            "avg_candidate_set_size": 0.0,
            "avg_entropy": 0.0,
            "acceptance_rate": 0.0,
            "by_carrier": {},
        }
    total_bits = sum(a.bits_embedded for a in audits)
    avg_size = sum(len(d.candidates) for d in decisions) / len(decisions)
    avg_entropy = sum(_entropy(d.probabilities) for d in decisions) / len(decisions)
    acceptance = sum(1 for d in decisions if len(d.candidates) >= 2) / len(decisions)
    by_carrier: Dict[str, Dict[str, Any]] = {}
    for d, a in zip(decisions, audits):
        bucket = by_carrier.setdefault(
            d.tau,
            {
                "decisions": 0,
                "bits_embedded": 0,
                "candidate_size_sum": 0,
                "entropy_sum": 0.0,
                "accepted": 0,
            },
        )
        bucket["decisions"] += 1
        bucket["bits_embedded"] += a.bits_embedded
        bucket["candidate_size_sum"] += len(d.candidates)
        bucket["entropy_sum"] += _entropy(d.probabilities)
        if len(d.candidates) >= 2:
            bucket["accepted"] += 1
    by_carrier_out = {
        tau: {
            "decisions": v["decisions"],
            "bits_embedded": v["bits_embedded"],
            "bits_per_decision": v["bits_embedded"] / v["decisions"],
            "avg_candidate_set_size": v["candidate_size_sum"] / v["decisions"],
            "avg_entropy": v["entropy_sum"] / v["decisions"],
            "acceptance_rate": v["accepted"] / v["decisions"],
        }
        for tau, v in by_carrier.items()
    }
    return {
        "decisions": len(audits),
        "bits_embedded": total_bits,
        "bits_per_decision": total_bits / len(audits),
        "avg_candidate_set_size": avg_size,
        "avg_entropy": avg_entropy,
        "acceptance_rate": acceptance,
        "by_carrier": by_carrier_out,
    }


def _entropy(probabilities: Dict[str, float]) -> float:
    h = 0.0
    for p in probabilities.values():
        if p > 0:
            h -= p * math.log2(p)
    return h


# --------------------------------------------------------------- #
# Defaults (offline, no LLM)
# --------------------------------------------------------------- #


def _format_turn(turn: LoCoMoTurn, session_date_time: str = "") -> str:
    """Canonical text the backend ingests.

    Includes speaker / dia_id / session date so any backend-internal
    extractor can attribute facts and time-anchor them. Backends that
    parse their own `reference_time` (Graphiti) still receive the
    structured date string in the operation.
    """

    text = (turn.text or "").strip()
    head = f"{turn.speaker} " if turn.speaker else ""
    date = f", {session_date_time}" if session_date_time else ""
    return f"{head}({turn.dia_id}{date}): {text}"


def _format_session_text(
    session: LoCoMoSession, turns: List[LoCoMoTurn]
) -> str:
    """Render a session as one document for Cognee's add()."""

    lines = []
    if session.date_time:
        lines.append(f"Session {session.index} — {session.date_time}")
    if session.summary:
        lines.append(f"Summary: {session.summary}")
    for t in turns:
        text = (t.text or "").strip()
        head = f"{t.speaker} " if t.speaker else ""
        lines.append(f"{head}({t.dia_id}): {text}")
    return "\n".join(lines)


def _keep_all_substantive_turns(turn: LoCoMoTurn, session_summary: str) -> bool:
    """Default filter: drop empty or 1-word chitchat ("Hey!", "ok")
    but keep everything else. The backend itself decides what's
    durable.
    """

    text = (turn.text or "").strip()
    if not text:
        return False
    if len(text.split()) < 3:
        return False
    return True


def _default_qa_responder(
    question: LoCoMoQuestion, context_text: str
) -> str:
    """Substring lookup; only used when LLM responder isn't wired.
    Real runs should use `make_locomo_qa_responder(llm_client)` from
    qa_eval.py.

    `context_text` is whatever the backend's `qa_context` returned
    (canonical retrieval rendering).
    """

    keywords = [w for w in question.question.lower().split() if len(w) > 3]
    if not keywords:
        return ""
    # Cheap match: pick the line in the rendered context with the
    # most keyword hits.
    best_line = ""
    best_score = 0
    for line in (context_text or "").splitlines():
        line_lower = line.lower()
        score = sum(1 for kw in keywords if kw in line_lower)
        if score > best_score:
            best_score = score
            best_line = line
    return best_line


def _default_qa_judge(question: LoCoMoQuestion, answer: str) -> bool:
    if not answer:
        return False
    gold = (question.answer or "").lower()
    return bool(gold) and gold in answer.lower()


def _evidence_recall(
    question: LoCoMoQuestion, snapshot: List[Dict[str, Any]]
) -> float:
    """Fraction of QA's `evidence` dia_ids that appear in *some*
    memory record's `dia_ids`. Used by RQ5 evidence-grounded
    integrity (README §10.7).
    """

    if not question.evidence:
        return 1.0  # no evidence required
    seen: set = set()
    for record in snapshot:
        for d in record.get("dia_ids") or []:
            seen.add(d)
    hit = sum(1 for d in question.evidence if d in seen)
    return hit / len(question.evidence)


# Backwards-compat alias used by older example scripts.
def keyword_memory_extractor(turn, session_summary):  # pragma: no cover
    """Legacy stub: callers should switch to backend-native ingestion.

    Kept for import compatibility with `examples/run_real_llm_agent.py`
    and any external scripts that still expect this function.
    """

    if not _keep_all_substantive_turns(turn, session_summary):
        return []
    return [_format_turn(turn)]
