from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass

from memmark.core.types import Candidate, DecisionPoint

try:
    from agentmark.core.watermark_sampler import sample_behavior_differential
except ModuleNotFoundError:
    sample_behavior_differential = None


@dataclass(frozen=True)
class MemorySampleResult:
    selected_candidate: Candidate
    target_candidate_ids: list[str]
    bits_embedded: int
    context_used: str


def sample_memory_transition(
    decision: DecisionPoint,
    *,
    payload_bits: str,
    bit_index: int,
) -> MemorySampleResult:
    candidate_by_id = {c.candidate_id: c for c in decision.candidates}
    if sample_behavior_differential is not None:
        selected_id, target_ids, bits_embedded, context_used = sample_behavior_differential(
            probabilities=decision.probabilities,
            bit_stream=payload_bits,
            bit_index=bit_index,
            context_for_key=decision.context,
            round_num=decision.round_num,
        )
    else:
        selected_id, target_ids, bits_embedded, context_used = _sample_fallback(
            decision,
            payload_bits=payload_bits,
            bit_index=bit_index,
        )
    return MemorySampleResult(
        selected_candidate=candidate_by_id[selected_id],
        target_candidate_ids=target_ids,
        bits_embedded=bits_embedded,
        context_used=context_used,
    )


def _sample_fallback(
    decision: DecisionPoint,
    *,
    payload_bits: str,
    bit_index: int,
) -> tuple[str, list[str], int, str]:
    candidate_ids = sorted(decision.probabilities)
    n = len(candidate_ids)
    if n < 2:
        return candidate_ids[0], candidate_ids, 0, decision.context
    k = int(math.floor(math.log2(n)))
    available = max(0, len(payload_bits) - bit_index)
    bits_embedded = min(k, available)
    if bits_embedded == 0:
        idx_value = 0
    else:
        idx_value = int(payload_bits[bit_index : bit_index + bits_embedded], 2)
    shift = _context_shift(decision.context, decision.round_num, n)
    selected_idx = (idx_value + shift) % n
    return candidate_ids[selected_idx], candidate_ids, bits_embedded, decision.context


def _context_shift(context: str, round_num: int, n: int) -> int:
    digest = hashlib.sha256(f"{context}|{round_num}".encode("utf-8")).hexdigest()
    return int(digest, 16) % n
