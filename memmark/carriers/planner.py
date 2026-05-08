from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from memmark.core.types import Candidate, MemoryEvent


# Three carriers per README §4.2.2. `merge_policy` was cut because
# supersede / merge / coexist are not strictly semantically equivalent
# and break the utility-preserving assumption.
CARRIER_TYPES = (
    "semantic_realization",
    "update_target",
    "link_target",
)


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
    """Plans which carrier to use, generates candidates, and scores them.

    Uses the LLM as a *scoring oracle* only; final selection is done by
    deterministic Python code so the protocol is auditable.
    """

    def __init__(
        self,
        llm_client: Any,
        *,
        fallback_carrier: Any,
    ) -> None:
        self.llm_client = llm_client
        self.fallback_carrier = fallback_carrier

    # -- top-level entry --------------------------------------------- #
    def plan(self, event: MemoryEvent, memory_snapshot: Any) -> CarrierPlan:
        assessments = self.assess_carriers(event, memory_snapshot)
        selected = self.select_carrier(assessments, memory_snapshot)
        candidates = self.generate_candidates(selected, event, memory_snapshot)
        if len(candidates) < 2:
            # Fall back to deterministic semantic_realization carrier.
            selected = self.fallback_carrier.carrier_type
            candidates = self.fallback_carrier.generate_candidates(event, memory_snapshot)
        probabilities = self.score_candidates(selected, event, memory_snapshot, candidates)
        if not probabilities:
            probabilities = self.fallback_carrier.score_candidates(candidates)
        return CarrierPlan(
            selected_carrier=selected,
            assessments=assessments,
            candidates=candidates,
            probabilities=probabilities,
        )

    # -- carrier assessment ------------------------------------------ #
    def assess_carriers(
        self, event: MemoryEvent, memory_snapshot: Any
    ) -> List[CarrierAssessment]:
        prompt = {
            "task": "Assess feasibility of fixed memory watermark carriers.",
            "allowed_carriers": list(CARRIER_TYPES),
            "event": event.text,
            "memory_snapshot": memory_snapshot,
            "output_schema": [
                {
                    "carrier_type": "semantic_realization",
                    "feasible": True,
                    "score": 0.0,
                    "reason": "...",
                }
            ],
        }
        raw = self.llm_client.complete(
            [
                {
                    "role": "system",
                    "content": "Return only strict JSON. Do not invent carrier types.",
                },
                {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
            ],
            temperature=0.0,
        )
        parsed = self._extract_json(raw)
        assessments: List[CarrierAssessment] = []
        if isinstance(parsed, dict):
            parsed = parsed.get("assessments", [])
        if isinstance(parsed, list):
            for item in parsed:
                if not isinstance(item, dict):
                    continue
                carrier_type = item.get("carrier_type") or item.get("carrier")
                # Backwards-compat: collapse old carrier names.
                if carrier_type == "semantic_variant":
                    carrier_type = "semantic_realization"
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
            assessments = [
                CarrierAssessment("semantic_realization", True, 1.0, "fallback")
            ]
        return assessments

    def select_carrier(
        self, assessments: List[CarrierAssessment], memory_snapshot: Any
    ) -> str:
        feasible = [a for a in assessments if a.feasible]
        if not feasible:
            return self.fallback_carrier.carrier_type
        feasible.sort(key=lambda a: (-a.score, a.carrier_type))
        for a in feasible:
            if a.carrier_type in {"update_target", "link_target"} and not memory_snapshot:
                continue
            return a.carrier_type
        return feasible[0].carrier_type

    # -- candidate generation per carrier ---------------------------- #
    def generate_candidates(
        self, carrier_type: str, event: MemoryEvent, memory_snapshot: Any
    ) -> List[Candidate]:
        if carrier_type == "semantic_realization":
            return self._generate_semantic(event, memory_snapshot)
        if carrier_type == "update_target":
            return self._generate_update_target(event, memory_snapshot)
        if carrier_type == "link_target":
            return self._generate_link_target(event, memory_snapshot)
        return []

    def _generate_semantic(
        self, event: MemoryEvent, memory_snapshot: Any
    ) -> List[Candidate]:
        prompt = {
            "task": "Generate semantic-equivalent memory variants for watermark candidate selection.",
            "carrier_type": "semantic_realization",
            "event": event.text,
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
            temperature=0.7,
        )
        parsed = self._extract_json(raw)
        variants: List[str] = []
        if isinstance(parsed, list):
            for item in parsed:
                if isinstance(item, str):
                    variants.append(item.strip())
                elif isinstance(item, dict) and isinstance(item.get("text"), str):
                    variants.append(item["text"].strip())
        variants = list(dict.fromkeys(v for v in variants if v))
        candidates: List[Candidate] = []
        for idx, text in enumerate(variants, start=1):
            candidates.append(
                Candidate(
                    candidate_id=_candidate_id("sr", event.event_id, idx, text),
                    carrier_type="semantic_realization",
                    payload={"text": text, "normalized_fact": event.text.strip()},
                    operation={"op": "add_memory", "text": text},
                    utility_score=1.0,
                )
            )
        return candidates

    def _generate_update_target(
        self, event: MemoryEvent, memory_snapshot: Any
    ) -> List[Candidate]:
        if not memory_snapshot:
            return []
        prompt = {
            "task": "Identify candidate existing memories to update with the incoming event.",
            "carrier_type": "update_target",
            "event": event.text,
            "memory_snapshot": memory_snapshot,
            "constraints": [
                "Pick 2 to 5 existing memories whose content is plausibly the same fact.",
                "Each candidate is identified by its memory id (the `id` field).",
                "Return JSON array of objects with `memory_id` and `reason` fields.",
            ],
        }
        raw = self.llm_client.complete(
            [
                {"role": "system", "content": "Return only strict JSON array."},
                {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
            ],
            temperature=0.7,
        )
        parsed = self._extract_json(raw)
        ids: List[str] = []
        if isinstance(parsed, list):
            valid_ids = {str(m.get("id")) for m in memory_snapshot if isinstance(m, dict)}
            for item in parsed:
                if isinstance(item, dict):
                    mid = item.get("memory_id") or item.get("id")
                    if mid is not None and str(mid) in valid_ids:
                        ids.append(str(mid))
        ids = list(dict.fromkeys(ids))
        candidates: List[Candidate] = []
        for idx, mid in enumerate(ids, start=1):
            candidates.append(
                Candidate(
                    candidate_id=_candidate_id("ut", event.event_id, idx, mid),
                    carrier_type="update_target",
                    payload={"memory_id": mid, "new_text": event.text},
                    operation={
                        "op": "update_memory",
                        "memory_id": mid,
                        "text": event.text,
                    },
                    utility_score=1.0,
                )
            )
        return candidates

    def _generate_link_target(
        self, event: MemoryEvent, memory_snapshot: Any
    ) -> List[Candidate]:
        if not memory_snapshot:
            return []
        prompt = {
            "task": "Identify candidate existing memories to which the new memory should be linked.",
            "carrier_type": "link_target",
            "event": event.text,
            "memory_snapshot": memory_snapshot,
            "constraints": [
                "Pick 2 to 5 existing memories that are topically related (not duplicates).",
                "Return JSON array of objects with `memory_id` and `reason` fields.",
            ],
        }
        raw = self.llm_client.complete(
            [
                {"role": "system", "content": "Return only strict JSON array."},
                {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
            ],
            temperature=0.7,
        )
        parsed = self._extract_json(raw)
        ids: List[str] = []
        if isinstance(parsed, list):
            valid_ids = {str(m.get("id")) for m in memory_snapshot if isinstance(m, dict)}
            for item in parsed:
                if isinstance(item, dict):
                    mid = item.get("memory_id") or item.get("id")
                    if mid is not None and str(mid) in valid_ids:
                        ids.append(str(mid))
        ids = list(dict.fromkeys(ids))
        candidates: List[Candidate] = []
        for idx, mid in enumerate(ids, start=1):
            candidates.append(
                Candidate(
                    candidate_id=_candidate_id("lt", event.event_id, idx, mid),
                    carrier_type="link_target",
                    payload={"link_to": mid, "text": event.text},
                    operation={
                        "op": "add_memory",
                        "text": event.text,
                        "links": [mid],
                    },
                    utility_score=1.0,
                )
            )
        return candidates

    # -- candidate scoring ------------------------------------------- #
    def score_candidates(
        self,
        carrier_type: str,
        event: MemoryEvent,
        memory_snapshot: Any,
        candidates: List[Candidate],
    ) -> Dict[str, float]:
        if not candidates:
            return {}
        prompt = {
            "task": "Score candidate acceptability for memory writing.",
            "carrier_type": carrier_type,
            "event": event.text,
            "memory_snapshot": memory_snapshot,
            "candidates": [
                {
                    "candidate_id": c.candidate_id,
                    "carrier_type": c.carrier_type,
                    "payload": c.payload,
                }
                for c in candidates
            ],
            "output_schema": {"candidate_id": 0.5},
        }
        raw = self.llm_client.complete(
            [
                {
                    "role": "system",
                    "content": "Return only strict JSON object mapping candidate_id to score.",
                },
                {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
            ],
            temperature=0.0,
        )
        parsed = self._extract_json(raw)
        if not isinstance(parsed, dict):
            return {}
        scores: Dict[str, float] = {}
        candidate_ids = {c.candidate_id for c in candidates}
        for key, value in parsed.items():
            if key in candidate_ids:
                try:
                    scores[key] = max(0.0, float(value))
                except (TypeError, ValueError):
                    continue
        total = sum(scores.values())
        if total <= 0:
            return {}
        return {key: value / total for key, value in scores.items()}

    # -- helpers ----------------------------------------------------- #
    @staticmethod
    def _extract_json(raw: str) -> Optional[Any]:
        text = raw.strip() if isinstance(raw, str) else ""
        if not text:
            return None
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


def _candidate_id(prefix: str, event_id: str, idx: int, payload_text: str) -> str:
    digest = hashlib.sha256(
        f"{event_id}|{idx}|{payload_text}".encode("utf-8")
    ).hexdigest()[:10]
    return f"{prefix}_{idx}_{digest}"
