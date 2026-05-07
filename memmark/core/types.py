from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


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
    nonce: str = ""
    watermark_version: str = ""


@dataclass(frozen=True)
class AuditRecord:
    """Per-decision audit record. README §9.1 + §9.3.

    The reveal record `reveal_t` (full candidates / probabilities / nonce) is
    stored in this object. The hash of those reveal fields is folded into the
    `commitment` so that any tampering is detectable. Together with the
    Merkle log header (§9.2) this implements In-Record Attribution
    Verification (R3, README §10.5).
    """

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
    nonce: str = ""
    watermark_version: str = ""
    decoded_bits: Optional[str] = None
    # Reveal record fields (kept by value so a single AuditRecord is enough
    # for in-record verification per README §9.3 / §10.5 R3).
    candidates: Optional[List[Candidate]] = None
    probabilities: Optional[Dict[str, float]] = None


@dataclass(frozen=True)
class MerkleProof:
    leaf: str
    siblings: List[Tuple[str, str]]  # (sibling_hash, "L"|"R") path bottom-up
    root: str

    def verify(self) -> bool:
        from memmark.core.context import sha256_text

        cur = self.leaf
        for sibling_hash, side in self.siblings:
            if side == "L":
                cur = sha256_text(sibling_hash + cur)
            else:
                cur = sha256_text(cur + sibling_hash)
        return cur == self.root


@dataclass(frozen=True)
class SessionHeader:
    """Signed Merkle root of a session's commitments. README §9.2."""

    agent_id: str
    user_id: str
    session_id: str
    leaf_count: int
    root: str
    signature: str  # HMAC(K, root) — placeholder for ed25519 signing
    watermark_version: str = ""
