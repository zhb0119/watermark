from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from memmark.core.types import Candidate, MemoryEvent

CARRIER_TYPES = ("semantic_variant", "update_target", "link_target", "merge_strategy")


@dataclass(frozen=True)
class CarrierAssessment:
    carrier_type: str
    feasible: bool
    score: float
    reason: str = ""


@dataclass(frozen=True)
class CarrierPlan:
    selected_carrier: str
    assessments: List[CarrierAssessment]
    candidates: List[Candidate]
    probabilities: Dict[str, float]


class LLMCarrierPlanner:
    def __init__(self, llm_client: Any, *, fallback_carrier: Any) -> None:
        self.llm_client = llm_client
        self.fallback_carrier = fallback_carrier

    def plan(self, event: MemoryEvent, memory_snapshot: Any) -> CarrierPlan:
        assessments = self.assess_carriers(event, memory_snapshot)
        selected_carrier = self.select_carrier(assessments)
        if selected_carrier != "semantic_variant":
            selected_carrier = self.fallback_carrier.carrier_type
        candidates = self.generate_candidates(selected_carrier, event, memory_snapshot)
        if len(candidates) < 2:
            candidates = self.fallback_carrier.generate_candidates(event, memory_snapshot)
        probabilities = self.score_candidates(selected_carrier, event, memory_snapshot, candidates)
        if not probabilities:
            probabilities = self.fallback_carrier.score_candidates(candidates)
        return CarrierPlan(
            selected_carrier=selected_carrier,
            assessments=assessments,
            candidates=candidates,
            probabilities=probabilities,
        )

    def assess_carriers(self, event: MemoryEvent, memory_snapshot: Any) -> List[CarrierAssessment]:
        prompt = {
            "task": "Assess feasibility of fixed memory watermark carriers.",
            "allowed_carriers": list(CARRIER_TYPES),
            "event": event.text,
            "memory_snapshot": memory_snapshot,
            "output_schema": [
                {"carrier_type": "semantic_variant", "feasible": True, "score": 0.0, "reason": "..."}
            ],
        }
        raw = self.llm_client.complete(
            [
                {"role": "system", "content": "Return only strict JSON. Do not invent carrier types."},
                {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
            ],
            temperature=0.0,
        )
        parsed = self._extract_json(raw)
        assessments = []
        if isinstance(parsed, dict):
            parsed = parsed.get("assessments", [])
        if isinstance(parsed, list):
            for item in parsed:
                if not isinstance(item, dict):
                    continue
                carrier_type = item.get("carrier_type") or item.get("carrier")
                if carrier_type not in CARRIER_TYPES:
                    continue
                assessments.append(
                    CarrierAssessment(
                        carrier_type=carrier_type,
                        feasible=bool(item.get("feasible", False)),
                        score=self._clamp_score(item.get("score", 0.0)),
                        reason=str(item.get("reason", "")),
                    )
                )
        if not assessments:
            assessments = [CarrierAssessment("semantic_variant", True, 1.0, "fallback")]
        return assessments

    def select_carrier(self, assessments: List[CarrierAssessment]) -> str:
        feasible = [item for item in assessments if item.feasible]
        if not feasible:
            return self.fallback_carrier.carrier_type
        selected = max(feasible, key=lambda item: item.score)
        return selected.carrier_type

    def generate_candidates(self, carrier_type: str, event: MemoryEvent, memory_snapshot: Any) -> List[Candidate]:
        if carrier_type != "semantic_variant":
            return []
        prompt = {
            "task": "Generate semantic-equivalent memory variants for watermark candidate selection.",
            "carrier_type": carrier_type,
            "event": event.text,
            "memory_snapshot": memory_snapshot,
            "constraints": [
                "Return 3 to 5 variants.",
                "All variants must preserve the same durable fact.",
                "Return only JSON array of objects with text fields.",
            ],
            "output_schema": [{"text": "User prefers concise technical answers."}],
        }
        raw = self.llm_client.complete(
            [
                {"role": "system", "content": "Return only strict JSON."},
                {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
            ],
            temperature=0.2,
        )
        parsed = self._extract_json(raw)
        variants = []
        if isinstance(parsed, list):
            for item in parsed:
                if isinstance(item, str):
                    variants.append(item.strip())
                elif isinstance(item, dict) and isinstance(item.get("text"), str):
                    variants.append(item["text"].strip())
        variants = list(dict.fromkeys(item for item in variants if item))
        candidates = []
        for idx, text in enumerate(variants, start=1):
            candidate_id = self.fallback_carrier._candidate_id(event.event_id, idx, text)
            candidates.append(
                Candidate(
                    candidate_id=candidate_id,
                    carrier_type=carrier_type,
                    payload={"text": text, "normalized_fact": event.text.strip()},
                    operation={"op": "add_memory", "text": text},
                    utility_score=1.0,
                )
            )
        return candidates

    def score_candidates(
        self,
        carrier_type: str,
        event: MemoryEvent,
        memory_snapshot: Any,
        candidates: List[Candidate],
    ) -> Dict[str, float]:
        prompt = {
            "task": "Score candidate acceptability for memory writing.",
            "carrier_type": carrier_type,
            "event": event.text,
            "memory_snapshot": memory_snapshot,
            "candidates": [
                {"candidate_id": candidate.candidate_id, "text": candidate.payload.get("text", "")}
                for candidate in candidates
            ],
            "output_schema": {"candidate_id": 0.5},
        }
        raw = self.llm_client.complete(
            [
                {"role": "system", "content": "Return only strict JSON object mapping candidate_id to score."},
                {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
            ],
            temperature=0.0,
        )
        parsed = self._extract_json(raw)
        if not isinstance(parsed, dict):
            return {}
        scores = {}
        candidate_ids = {candidate.candidate_id for candidate in candidates}
        for key, value in parsed.items():
            if key in candidate_ids:
                scores[key] = max(0.0, float(value))
        total = sum(scores.values())
        if total <= 0:
            return {}
        return {key: value / total for key, value in scores.items()}

    @staticmethod
    def _extract_json(raw: str) -> Optional[Any]:
        text = raw.strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
        starts = [idx for idx in (text.find("["), text.find("{")) if idx >= 0]
        if not starts:
            return None
        start = min(starts)
        end = max(text.rfind("]"), text.rfind("}"))
        if end < start:
            return None
        try:
            return json.loads(text[start : end + 1])
        except json.JSONDecodeError:
            return None

    @staticmethod
    def _clamp_score(value: Any) -> float:
        try:
            score = float(value)
        except (TypeError, ValueError):
            score = 0.0
        return min(1.0, max(0.0, score))
