from __future__ import annotations

from typing import Dict, List

from memmark.core.context import sha256_text, stable_json
from memmark.core.types import AuditRecord, Candidate, DecisionPoint


def hash_candidates(candidates: List[Candidate]) -> str:
    payload = [
        {
            "candidate_id": c.candidate_id,
            "carrier_type": c.carrier_type,
            "payload": c.payload,
            "operation": c.operation,
            "utility_score": c.utility_score,
        }
        for c in candidates
    ]
    return sha256_text(stable_json(payload))


def hash_probabilities(probabilities: Dict[str, float]) -> str:
    return sha256_text(stable_json({k: round(float(v), 12) for k, v in probabilities.items()}))


def make_commitment(
    decision: DecisionPoint,
    *,
    selected_candidate_id: str,
    bits_embedded: int,
    bit_index_after: int,
) -> AuditRecord:
    candidate_hash = hash_candidates(decision.candidates)
    probability_hash = hash_probabilities(decision.probabilities)
    context_hash = sha256_text(decision.context)
    body = {
        "decision_id": decision.decision_id,
        "tau": decision.tau,
        "candidate_hash": candidate_hash,
        "probability_hash": probability_hash,
        "context_hash": context_hash,
        "selected_candidate_id": selected_candidate_id,
        "bits_embedded": bits_embedded,
        "bit_index_after": bit_index_after,
        "round_num": decision.round_num,
    }
    commitment = sha256_text(stable_json(body))
    return AuditRecord(
        decision_id=decision.decision_id,
        tau=decision.tau,
        candidate_hash=candidate_hash,
        probability_hash=probability_hash,
        context=decision.context,
        context_hash=context_hash,
        selected_candidate_id=selected_candidate_id,
        bits_embedded=bits_embedded,
        bit_index_after=bit_index_after,
        round_num=decision.round_num,
        commitment=commitment,
    )
