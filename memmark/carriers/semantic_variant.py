from __future__ import annotations

import hashlib
from typing import Any, Dict, List

from memmark.core.types import Candidate, MemoryEvent


class SemanticVariantCarrier:
    carrier_type = "semantic_variant"

    def generate_candidates(self, event: MemoryEvent, memory_snapshot: Any) -> List[Candidate]:
        base = event.text.strip()
        variants = [
            base,
            f"User preference: {base}",
            f"Remember that the user wants: {base}",
        ]
        unique_variants = list(dict.fromkeys(v for v in variants if v))
        candidates = []
        for idx, text in enumerate(unique_variants, start=1):
            candidate_id = self._candidate_id(event.event_id, idx, text)
            candidates.append(
                Candidate(
                    candidate_id=candidate_id,
                    carrier_type=self.carrier_type,
                    payload={"text": text, "normalized_fact": base},
                    operation={"op": "add_memory", "text": text},
                    utility_score=1.0,
                )
            )
        return candidates

    def score_candidates(self, candidates: List[Candidate]) -> Dict[str, float]:
        weights = [0.40, 0.35, 0.25]
        scores = {}
        for idx, candidate in enumerate(candidates):
            scores[candidate.candidate_id] = weights[idx] if idx < len(weights) else 0.10
        total = sum(scores.values())
        return {key: value / total for key, value in scores.items()}

    @staticmethod
    def _candidate_id(event_id: str, idx: int, text: str) -> str:
        digest = hashlib.sha256(f"{event_id}|{idx}|{text}".encode("utf-8")).hexdigest()[:10]
        return f"sv_{idx}_{digest}"
