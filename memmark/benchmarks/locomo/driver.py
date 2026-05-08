"""LoCoMo driver — replays a conversation through MemMark.

Per-turn pipeline (matching the user's diagram):

  1. take a LoCoMo turn (speaker / dia_id / text)
  2. push it as a memory event to the watermarker, which:
       a. calls planner -> picks carrier τ
       b. planner pulls candidate set from the BACKEND'S native
          retrieval (not LLM-fabricated) for update_target /
          link_target; LLM paraphrase for semantic_realization
       c. AgentMark sampler embeds payload bits via keyed selection
       d. backend.apply() writes the memory record (carrying dia_ids
          for evidence-grounded RQ5 audits later)
       e. commitment + Merkle log are appended
  3. optionally drop turns the user's `turn_filter` rejects (e.g.,
     skip greetings) — but we DON'T do LLM extraction; backends are
     the source of truth for what becomes memory

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
    make_locomo_qa_judge,
    make_locomo_qa_responder,
    score_one,
)
from memmark.core.types import AuditRecord, DecisionPoint, SessionHeader
from memmark.sdk.memory_watermarker import EvolveResult, MemoryWatermarker


TurnFilter = Callable[[LoCoMoTurn, str], bool]
QAJudge = Callable[[LoCoMoQuestion, str], bool]
QAResponder = Callable[[LoCoMoQuestion, List[Dict[str, Any]]], str]


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
        if not self.qa_predictions:
            return 0.0
        return sum(q.get("f1", 0.0) for q in self.qa_predictions) / len(self.qa_predictions)


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
        # Backwards-compat: accept the deprecated `memory_extractor`
        # kwarg but ignore it (we no longer extract; backends do).
        memory_extractor: Optional[Any] = None,
    ) -> None:
        self.wm = watermarker
        self.turn_filter = turn_filter or _keep_all_substantive_turns
        self.qa_responder = qa_responder or _default_qa_responder
        self.qa_judge = qa_judge or _default_qa_judge
        self.max_sessions = max_sessions
        self.max_qa = max_qa
        self.max_turns_per_session = max_turns_per_session
        # We intentionally ignore memory_extractor — backend is the
        # source of truth for what becomes a memory record.
        self._legacy_extractor_warned = bool(memory_extractor)

    def run(self, conversation: LoCoMoConversation) -> LoCoMoDriverResult:
        result = LoCoMoDriverResult(
            sample_id=conversation.sample_id,
            payload_bits=self.wm.payload_bits,
        )
        sessions = conversation.sessions
        if self.max_sessions is not None:
            sessions = sessions[: self.max_sessions]

        recent_dialog_ids: List[str] = []
        for session in sessions:
            turns = session.turns
            if self.max_turns_per_session is not None:
                turns = turns[: self.max_turns_per_session]
            for turn in turns:
                if not self.turn_filter(turn, session.summary):
                    continue
                recent_dialog_ids = (recent_dialog_ids + [turn.dia_id])[-8:]
                event_text = _format_turn(turn)
                try:
                    evolve_result = self.wm.evolve(
                        event_text,
                        recent_dialog_ids=recent_dialog_ids,
                        retrieved_memory_ids=None,
                        dia_ids=[turn.dia_id],
                        session_index=session.index,
                        speaker=turn.speaker,
                    )
                except ValueError:
                    result.extracted_events.append(
                        {
                            "session": session.index,
                            "dia_id": turn.dia_id,
                            "speaker": turn.speaker,
                            "text": event_text,
                            "applied": False,
                            "reason": "acceptance_fail",
                        }
                    )
                    continue
                result.decisions.append(evolve_result.decision)
                result.audits.append(evolve_result.audit)
                result.extracted_events.append(
                    {
                        "session": session.index,
                        "dia_id": turn.dia_id,
                        "speaker": turn.speaker,
                        "text": event_text,
                        "applied": True,
                        "selected": evolve_result.audit.selected_candidate_id,
                        "tau": evolve_result.audit.tau,
                        "bits_embedded": evolve_result.audit.bits_embedded,
                    }
                )

        result.anchor = self.wm.seal_session()
        result.memory_snapshot_final = self.wm.backend.snapshot()
        result.capacity_stats = _capacity_stats(result.audits, result.decisions)

        qa_list = conversation.qa
        if self.max_qa is not None:
            qa_list = qa_list[: self.max_qa]
        for q in qa_list:
            answer = self.qa_responder(q, result.memory_snapshot_final)
            f1 = score_one(answer, q.answer, q.category)
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
                    "correct": correct,
                    "evidence_recall": evidence_recall,
                }
            )
        return result


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


def _format_turn(turn: LoCoMoTurn) -> str:
    """Canonical text the backend ingests. Includes speaker so the
    backend's own extractor can attribute facts correctly."""

    text = (turn.text or "").strip()
    if turn.speaker:
        return f"{turn.speaker} ({turn.dia_id}): {text}"
    return f"({turn.dia_id}) {text}"


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
    question: LoCoMoQuestion, memory_snapshot: List[Dict[str, Any]]
) -> str:
    """Substring lookup; only used when LLM responder isn't wired.
    Real runs should use `make_locomo_qa_responder(llm_client)` from
    qa_eval.py.
    """

    keywords = [w for w in question.question.lower().split() if len(w) > 3]
    best = ""
    for record in memory_snapshot:
        text = record.get("text", "") or ""
        if not text:
            continue
        score = sum(1 for kw in keywords if kw in text.lower())
        if score and (
            not best
            or score > sum(1 for kw in keywords if kw in best.lower())
        ):
            best = text
    return best


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
    and any external scripts that still expect this function. It now
    returns the formatted turn text (or [] for chitchat) so the
    behaviour is roughly preserved.
    """

    if not _keep_all_substantive_turns(turn, session_summary):
        return []
    return [_format_turn(turn)]
