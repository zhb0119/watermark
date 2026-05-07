from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class MemoryEvent:
    event_id: str
    text: str
    turn_id: int


@dataclass(frozen=True)
class Candidate:
    candidate_id: str
    carrier_type: str
    payload: Dict[str, Any]
    operation: Dict[str, Any]
    utility_score: float = 1.0


@dataclass(frozen=True)
class DecisionPoint:
    decision_id: str
    tau: str
    candidates: List[Candidate]
    probabilities: Dict[str, float]
    context: str
    round_num: int


@dataclass(frozen=True)
class AuditRecord:
    decision_id: str
    tau: str
    candidate_hash: str
    probability_hash: str
    context: str
    context_hash: str
    selected_candidate_id: str
    bits_embedded: int
    bit_index_after: int
    round_num: int
    commitment: str
    decoded_bits: Optional[str] = None
