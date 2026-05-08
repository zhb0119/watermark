"""LoCoMo driver.

Replays a LoCoMo conversation through MemMark:

  1. for each session, walk turns in chronological order
  2. extract memory events (LLM-based or rule-based)
  3. push each event through MemoryWatermarker.evolve() — the carrier
     planner picks `update / link / semantic` and the AgentMark sampler
     embeds the next payload bit slice
  4. at the end, run all QA questions against the final memory snapshot

The driver returns a `LoCoMoDriverResult` with:
  - audit log (full per-decision AuditRecord list)
  - the signed Merkle anchor (SessionHeader)
  - QA predictions + correctness for §10.3 RQ1 utility
  - aggregated capacity stats for §10.4 RQ2
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

from memmark.backends.base import MemoryBackendAdapter
from memmark.benchmarks.locomo.loader import (
    LoCoMoConversation,
    LoCoMoQuestion,
    LoCoMoTurn,
)
from memmark.core.types import AuditRecord, DecisionPoint, SessionHeader
from memmark.sdk.memory_watermarker import EvolveResult, MemoryWatermarker


MemoryExtractor = Callable[[LoCoMoTurn, str], List[str]]
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


class LoCoMoDriver:
    """Replay a single LoCoMo conversation through a MemoryWatermarker.

    The extractor + responder are pluggable so we can swap LLM / rule
    implementations in tests vs real runs.
    """

    def __init__(
        self,
        *,
        watermarker: MemoryWatermarker,
        memory_extractor: MemoryExtractor,
        qa_responder: Optional[QAResponder] = None,
        qa_judge: Optional[QAJudge] = None,
        max_sessions: Optional[int] = None,
        max_qa: Optional[int] = None,
    ) -> None:
        self.wm = watermarker
        self.memory_extractor = memory_extractor
        self.qa_responder = qa_responder or _default_qa_responder
        self.qa_judge = qa_judge or _default_qa_judge
        self.max_sessions = max_sessions
        self.max_qa = max_qa

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
            for turn in session.turns:
                recent_dialog_ids = (recent_dialog_ids + [turn.dia_id])[-8:]
                events = self.memory_extractor(turn, session.summary)
                for ev in events:
                    if not ev:
                        continue
                    try:
                        evolve_result = self.wm.evolve(
                            ev,
                            recent_dialog_ids=recent_dialog_ids,
                            retrieved_memory_ids=None,
                        )
                    except ValueError:
                        # Acceptance failure: <2 candidates this turn,
                        # skip silently (acceptance rate stat below).
                        result.extracted_events.append(
                            {
                                "session": session.index,
                                "dia_id": turn.dia_id,
                                "event": ev,
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
                            "event": ev,
                            "applied": True,
                            "selected": evolve_result.audit.selected_candidate_id,
                            "tau": evolve_result.audit.tau,
                            "bits_embedded": evolve_result.audit.bits_embedded,
                        }
                    )

        result.anchor = self.wm.seal_session()
        result.memory_snapshot_final = self.wm.backend.snapshot()
        result.capacity_stats = _capacity_stats(result.audits, result.decisions)

        # QA
        qa = conversation.qa
        if self.max_qa is not None:
            qa = qa[: self.max_qa]
        for q in qa:
            answer = self.qa_responder(q, result.memory_snapshot_final)
            correct = bool(self.qa_judge(q, answer))
            result.qa_predictions.append(
                {
                    "question": q.question,
                    "answer_gold": q.answer,
                    "answer_pred": answer,
                    "category": q.category,
                    "evidence": q.evidence,
                    "correct": correct,
                }
            )
        return result


def _capacity_stats(
    audits: List[AuditRecord], decisions: List[DecisionPoint]
) -> Dict[str, Any]:
    """Capacity / acceptance metrics for §10.4 RQ2."""

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
# Default extractors / responders for offline / smoke runs
# --------------------------------------------------------------- #


def keyword_memory_extractor(turn: LoCoMoTurn, session_summary: str) -> List[str]:
    """Rule-based extractor for offline smoke tests (no LLM cost).

    Picks turns containing first-person assertions about preferences,
    activities, identity, or temporal events. The LLM extractor in
    `memory_agent.LLMMemoryAgent` should be used for real runs.
    """

    text = (turn.text or "").strip()
    if not text:
        return []
    lowered = text.lower()
    triggers = (
        "i ",
        "i'm ",
        "i am ",
        "my ",
        "we went",
        "we are",
        "we have",
        "we 're",
    )
    if not any(lowered.startswith(t) or f" {t}" in f" {lowered}" for t in triggers):
        return []
    if len(text) > 240:
        return []
    return [f"{turn.speaker}: {text}"]


def _default_qa_responder(
    question: LoCoMoQuestion, memory_snapshot: List[Dict[str, Any]]
) -> str:
    """Naive substring lookup over the memory snapshot.

    For real eval, plug in the LLM with the snapshot as context.
    """

    q = (question.question or "").lower()
    keywords = [w for w in q.split() if len(w) > 3]
    best = ""
    for record in memory_snapshot:
        text = record.get("text", "")
        if not text:
            continue
        score = sum(1 for kw in keywords if kw in text.lower())
        if score and (not best or score > sum(1 for kw in keywords if kw in best.lower())):
            best = text
    return best


def _default_qa_judge(question: LoCoMoQuestion, answer: str) -> bool:
    if not answer:
        return False
    gold = (question.answer or "").lower()
    return gold and gold in answer.lower()
