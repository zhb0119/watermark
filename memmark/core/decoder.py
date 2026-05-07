from __future__ import annotations

from agentmark.core.watermark_sampler import differential_based_decoder
from memmark.core.types import DecisionPoint


def decode_memory_transition(
    decision: DecisionPoint,
    *,
    selected_candidate_id: str,
) -> str:
    return differential_based_decoder(
        probabilities=decision.probabilities,
        selected_behavior=selected_candidate_id,
        context_for_key=decision.context,
        round_num=decision.round_num,
    )
