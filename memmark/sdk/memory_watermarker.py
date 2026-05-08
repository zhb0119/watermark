from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Iterable, List, Optional

from memmark.backends.base import MemoryBackendAdapter
from memmark.carriers.semantic_realization import SemanticRealizationCarrier
from memmark.core.commitment import make_commitment
from memmark.core.context import (
    build_context,
    derive_nonce,
    make_watermark_version,
    resolve_secret_key,
)
from memmark.core.merkle_log import SessionMerkleLog
from memmark.core.sampler import sample_memory_transition
from memmark.core.types import AuditRecord, DecisionPoint, MemoryEvent, SessionHeader


SAMPLER_MODES = ("watermark", "signed_metadata_only", "random_replace", "no_watermark")


@dataclass(frozen=True)
class EvolveResult:
    decision: DecisionPoint
    audit: AuditRecord
    memory_record: dict


class MemoryWatermarker:
    """Public SDK entrypoint.

    Drops in for HaoBo's MVP: same `evolve(text)` signature, but now plumbs
    nonce + watermark_version + per-session Merkle log through every
    decision (README §9.1–§9.4). Supports baseline modes for §10.3 RQ1
    setup so we can ablate watermark vs signed-metadata-only.
    """

    def __init__(
        self,
        *,
        backend: MemoryBackendAdapter,
        payload_bits: str,
        agent_id: str = "memmark-agent",
        user_id: str = "memmark-user",
        session_id: str = "default-session",
        carrier_planner: Optional[Any] = None,
        secret_key: Optional[str] = None,
        watermark_version: Optional[str] = None,
        sampler_mode: str = "watermark",
        random_seed: Optional[int] = None,
    ) -> None:
        if sampler_mode not in SAMPLER_MODES:
            raise ValueError(
                f"sampler_mode must be one of {SAMPLER_MODES}, got {sampler_mode}"
            )
        self.backend = backend
        self.payload_bits = self._validate_bits(payload_bits)
        self.agent_id = agent_id
        self.user_id = user_id
        self.session_id = session_id
        self.carrier = SemanticRealizationCarrier()
        self.carrier_planner = carrier_planner
        self.bit_index = 0
        self.round_num = 0
        self.previous_commitment = ""
        self.secret_key = resolve_secret_key(
            secret_key or os.getenv("MEMMARK_KEY") or "memmark-default-dev-key"
        )
        self.watermark_version = watermark_version or make_watermark_version(
            sdk_version="memmark-mvp-v0.2",
            model=os.getenv("MEMMARK_MODEL") or "unknown",
        )
        self.sampler_mode = sampler_mode
        self.random_seed = random_seed
        self.merkle_log = SessionMerkleLog(
            agent_id=agent_id,
            user_id=user_id,
            session_id=session_id,
            secret_key=self.secret_key,
            watermark_version=self.watermark_version,
        )

    # -- main entry point -------------------------------------------- #
    def evolve(
        self,
        text: str,
        *,
        recent_dialog_ids: Optional[Iterable[str]] = None,
        retrieved_memory_ids: Optional[Iterable[str]] = None,
        dia_ids: Optional[Iterable[str]] = None,
        session_index: Optional[int] = None,
        speaker: str = "",
    ) -> EvolveResult:
        event = MemoryEvent(
            event_id=f"e{self.round_num + 1}",
            text=text,
            turn_id=self.round_num + 1,
            dia_ids=tuple(dia_ids or ()),
            session_index=session_index,
            speaker=speaker,
        )
        memory_snapshot = self.backend.snapshot()
        tau, candidates, probabilities = self._plan_carrier(event, memory_snapshot)
        if len(candidates) < 2:
            raise ValueError(
                "At least two candidates are required for watermark embedding."
            )

        context = build_context(
            agent_id=self.agent_id,
            user_id=self.user_id,
            session_id=self.session_id,
            turn_id=event.turn_id,
            tau=tau,
            event_text=event.text,
            memory_snapshot=memory_snapshot,
            recent_dialog_ids=recent_dialog_ids,
            retrieved_memory_ids=retrieved_memory_ids,
            previous_commitment=self.previous_commitment,
        )
        nonce = derive_nonce(self.secret_key, context)

        decision = DecisionPoint(
            decision_id=f"d{self.round_num + 1}",
            tau=tau,
            candidates=candidates,
            probabilities=probabilities,
            context=context,
            round_num=self.round_num,
            nonce=nonce,
            watermark_version=self.watermark_version,
        )

        sample = sample_memory_transition(
            decision,
            payload_bits=self.payload_bits,
            bit_index=self.bit_index,
            mode=self.sampler_mode,
            random_seed=self.random_seed,
        )
        self.bit_index += sample.bits_embedded

        memory_record = self.backend.apply(sample.selected_candidate.operation)

        audit = make_commitment(
            decision,
            selected_candidate_id=sample.selected_candidate.candidate_id,
            bits_embedded=sample.bits_embedded,
            bit_index_after=self.bit_index,
            keep_reveal=True,
        )

        self.merkle_log.append(audit.commitment)
        self.previous_commitment = audit.commitment
        self.round_num += 1
        return EvolveResult(
            decision=decision, audit=audit, memory_record=memory_record
        )

    def seal_session(self) -> SessionHeader:
        """Produce the signed Merkle root anchor for §9.2 / §10.5 R3."""

        return self.merkle_log.seal()

    # -- private helpers --------------------------------------------- #
    def _plan_carrier(
        self, event: MemoryEvent, memory_snapshot: Any
    ) -> tuple[str, List[Any], dict]:
        if self.carrier_planner is not None:
            plan = self.carrier_planner.plan(event, memory_snapshot)
            return plan.selected_carrier, plan.candidates, plan.probabilities
        # Default: deterministic semantic_realization carrier
        candidates = self.carrier.generate_candidates(event, memory_snapshot)
        probabilities = self.carrier.score_candidates(candidates)
        return self.carrier.carrier_type, candidates, probabilities

    @staticmethod
    def _validate_bits(bits: str) -> str:
        cleaned = "".join(ch for ch in bits if ch in {"0", "1"})
        if not cleaned:
            raise ValueError("payload_bits must contain at least one bit.")
        return cleaned
