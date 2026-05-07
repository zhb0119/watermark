from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from memmark.backends.base import MemoryBackendAdapter
from memmark.carriers.semantic_variant import SemanticVariantCarrier
from memmark.core.commitment import make_commitment
from memmark.core.context import build_context
from memmark.core.sampler import sample_memory_transition
from memmark.core.types import AuditRecord, DecisionPoint, MemoryEvent


@dataclass(frozen=True)
class EvolveResult:
    decision: DecisionPoint
    audit: AuditRecord
    memory_record: dict


class MemoryWatermarker:
    def __init__(
        self,
        *,
        backend: MemoryBackendAdapter,
        payload_bits: str,
        agent_id: str = "memmark-agent",
        session_id: str = "default-session",
        carrier_planner: Optional[Any] = None,
    ) -> None:
        self.backend = backend
        self.payload_bits = self._validate_bits(payload_bits)
        self.agent_id = agent_id
        self.session_id = session_id
        self.carrier = SemanticVariantCarrier()
        self.carrier_planner = carrier_planner
        self.bit_index = 0
        self.round_num = 0
        self.previous_commitment = ""

    def evolve(self, text: str) -> EvolveResult:
        event = MemoryEvent(
            event_id=f"e{self.round_num + 1}",
            text=text,
            turn_id=self.round_num + 1,
        )
        memory_snapshot = self.backend.snapshot()
        if self.carrier_planner is not None:
            carrier_plan = self.carrier_planner.plan(event, memory_snapshot)
            tau = carrier_plan.selected_carrier
            candidates = carrier_plan.candidates
            probabilities = carrier_plan.probabilities
        else:
            tau = self.carrier.carrier_type
            candidates = self.carrier.generate_candidates(event, memory_snapshot)
            probabilities = self.carrier.score_candidates(candidates)
        if len(candidates) < 2:
            raise ValueError("At least two candidates are required for watermark embedding.")
        context = build_context(
            agent_id=self.agent_id,
            session_id=self.session_id,
            turn_id=event.turn_id,
            tau=tau,
            event_text=event.text,
            memory_snapshot=memory_snapshot,
            previous_commitment=self.previous_commitment,
        )
        decision = DecisionPoint(
            decision_id=f"d{self.round_num + 1}",
            tau=tau,
            candidates=candidates,
            probabilities=probabilities,
            context=context,
            round_num=self.round_num,
        )
        sample = sample_memory_transition(
            decision,
            payload_bits=self.payload_bits,
            bit_index=self.bit_index,
        )
        self.bit_index += sample.bits_embedded
        memory_record = self.backend.apply(sample.selected_candidate.operation)
        audit = make_commitment(
            decision,
            selected_candidate_id=sample.selected_candidate.candidate_id,
            bits_embedded=sample.bits_embedded,
            bit_index_after=self.bit_index,
        )
        self.previous_commitment = audit.commitment
        self.round_num += 1
        return EvolveResult(decision=decision, audit=audit, memory_record=memory_record)

    @staticmethod
    def _validate_bits(bits: str) -> str:
        cleaned = "".join(ch for ch in bits if ch in {"0", "1"})
        if not cleaned:
            raise ValueError("payload_bits must contain at least one bit.")
        return cleaned
