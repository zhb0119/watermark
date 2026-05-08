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

    Speed knobs:
      * `merge_gen_and_score=True` — emit candidates + probabilities in
        one LLM call instead of two (default ON; cuts ~2 calls /
        decision).
      * `async_assess=True` — fan out the 3 carrier-feasibility prompts
        in parallel via `llm_client.complete_many`. Requires the
        client to be an AsyncOpenAIChatClient or MultiProviderClient.

    Backend awareness:
      * If `backend` is provided and exposes `candidate_update_targets`
        / `candidate_link_targets`, the planner pulls the **real**
        candidate set from the backend's retrieval (A-MEM ChromaDB,
        Graphiti graph search, etc.) instead of asking the LLM to
        invent memory_ids. This is what makes the watermark capacity
        and per-carrier H(p_t) reflect the *backend's* intrinsic
        decision freedom (README §10.4 RQ2 + §10.7 simplicity).
    """

    def __init__(
        self,
        llm_client: Any,
        *,
        fallback_carrier: Any,
        merge_gen_and_score: bool = True,
        async_assess: bool = False,
        backend: Any = None,
        candidate_topk: int = 5,
    ) -> None:
        self.llm_client = llm_client
        self.fallback_carrier = fallback_carrier
        self.merge_gen_and_score = merge_gen_and_score
        self.async_assess = async_assess
        self.backend = backend
        self.candidate_topk = candidate_topk

    # -- top-level entry --------------------------------------------- #
    def plan(self, event: MemoryEvent, memory_snapshot: Any) -> CarrierPlan:
        assessments = self._dispatch_assess(event, memory_snapshot)
        selected = self.select_carrier(assessments, memory_snapshot)

        if self.merge_gen_and_score:
            candidates, probabilities = self.generate_and_score_candidates(
                selected, event, memory_snapshot
            )
        else:
            candidates = self.generate_candidates(selected, event, memory_snapshot)
            probabilities = (
                self.score_candidates(selected, event, memory_snapshot, candidates)
                if candidates
                else {}
            )

        if len(candidates) < 2:
            selected = self.fallback_carrier.carrier_type
            candidates = self.fallback_carrier.generate_candidates(event, memory_snapshot)
            probabilities = self.fallback_carrier.score_candidates(candidates)
        elif not probabilities:
            probabilities = self.fallback_carrier.score_candidates(candidates)
        return CarrierPlan(
            selected_carrier=selected,
            assessments=assessments,
            candidates=candidates,
            probabilities=probabilities,
        )

    # -- carrier assessment ------------------------------------------ #
    def _dispatch_assess(
        self, event: MemoryEvent, memory_snapshot: Any
    ) -> List[CarrierAssessment]:
        if self.async_assess and hasattr(self.llm_client, "complete_many"):
            import asyncio

            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    # Already in an event loop; fall back to sync to avoid
                    # nested-loop errors. Caller should use `aplan` instead.
                    return self.assess_carriers(event, memory_snapshot)
            except RuntimeError:
                pass
            return asyncio.run(
                self.assess_carriers_async(event, memory_snapshot)
            )
        return self.assess_carriers(event, memory_snapshot)

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
                    operation={
                        "op": "add_memory",
                        "text": text,
                        "dia_ids": list(event.dia_ids),
                        "session_index": event.session_index,
                        "speaker": event.speaker,
                    },
                    utility_score=1.0,
                )
            )
        return candidates

    def _generate_update_target(
        self, event: MemoryEvent, memory_snapshot: Any
    ) -> List[Candidate]:
        """Real backend candidates: pull top-k via backend's own
        retrieval (e.g., A-MEM ChromaDB) so the candidate set reflects
        the backend's intrinsic update freedom, not what the LLM
        invents.
        """

        candidate_records = self._backend_candidates(
            "candidate_update_targets", event, memory_snapshot
        )
        candidates: List[Candidate] = []
        for idx, rec in enumerate(candidate_records, start=1):
            mid = str(rec.get("id") or "")
            if not mid:
                continue
            candidates.append(
                Candidate(
                    candidate_id=_candidate_id("ut", event.event_id, idx, mid),
                    carrier_type="update_target",
                    payload={
                        "memory_id": mid,
                        "old_text": rec.get("text", ""),
                        "new_text": event.text,
                    },
                    operation={
                        "op": "update_memory",
                        "memory_id": mid,
                        "text": event.text,
                        "dia_ids": list(event.dia_ids),
                        "session_index": event.session_index,
                        "speaker": event.speaker,
                    },
                    utility_score=1.0,
                )
            )
        return candidates

    def _generate_link_target(
        self, event: MemoryEvent, memory_snapshot: Any
    ) -> List[Candidate]:
        candidate_records = self._backend_candidates(
            "candidate_link_targets", event, memory_snapshot
        )
        candidates: List[Candidate] = []
        for idx, rec in enumerate(candidate_records, start=1):
            mid = str(rec.get("id") or "")
            if not mid:
                continue
            candidates.append(
                Candidate(
                    candidate_id=_candidate_id("lt", event.event_id, idx, mid),
                    carrier_type="link_target",
                    payload={
                        "link_to": mid,
                        "linked_text": rec.get("text", ""),
                        "text": event.text,
                    },
                    operation={
                        "op": "add_memory",
                        "text": event.text,
                        "links": [mid],
                        "dia_ids": list(event.dia_ids),
                        "session_index": event.session_index,
                        "speaker": event.speaker,
                    },
                    utility_score=1.0,
                )
            )
        return candidates

    def _backend_candidates(
        self,
        method_name: str,
        event: MemoryEvent,
        memory_snapshot: Any,
    ) -> List[Dict[str, Any]]:
        """Try `backend.{method_name}(text, k)` first; fall back to
        keyword overlap over the snapshot if backend isn't present
        or didn't override.
        """

        if self.backend is not None and hasattr(self.backend, method_name):
            try:
                results = getattr(self.backend, method_name)(
                    event.text, k=self.candidate_topk
                )
                if results:
                    return list(results)
            except Exception:
                pass
        # Fallback: snapshot-only string overlap
        if not memory_snapshot:
            return []
        from memmark.backends.base import _string_topk

        return _string_topk(memory_snapshot, event.text, self.candidate_topk)

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

    # -- merged generate+score (saves one LLM call per decision) ---- #
    def generate_and_score_candidates(
        self, carrier_type: str, event: MemoryEvent, memory_snapshot: Any
    ) -> tuple[List[Candidate], Dict[str, float]]:
        """One-shot: get candidates *and* probabilities in a single LLM call.

        Cuts ~one LLM call per decision compared to separate
        generate_candidates + score_candidates. The prompt asks the
        LLM to emit a list of `{text, weight}` for semantic_realization
        or `{memory_id, weight, reason}` for update/link_target.
        """

        if carrier_type not in ("semantic_realization", "update_target", "link_target"):
            return [], {}
        if carrier_type in ("update_target", "link_target") and not memory_snapshot:
            return [], {}

        if carrier_type == "semantic_realization":
            prompt_payload = {
                "task": (
                    "Generate semantically-equivalent memory variants AND assign "
                    "an acceptability weight to each in a single response."
                ),
                "carrier_type": carrier_type,
                "event": event.text,
                "constraints": [
                    "Return 3 to 5 variants, each preserving the same durable fact.",
                    "Higher weight = more natural / preferred phrasing.",
                    "Weights must be > 0 and ideally sum near 1.0.",
                    "Return only a JSON array of {text, weight} objects.",
                ],
                "output_schema": [
                    {"text": "User prefers concise technical answers.", "weight": 0.40},
                    {"text": "User preference: concise technical answers.", "weight": 0.35},
                    {"text": "Remember: concise technical answers preferred.", "weight": 0.25},
                ],
            }
        else:
            prompt_payload = {
                "task": (
                    "Pick existing memory ids that are valid targets for this "
                    f"{carrier_type} operation, AND assign each a weight."
                ),
                "carrier_type": carrier_type,
                "event": event.text,
                "memory_snapshot": memory_snapshot,
                "constraints": [
                    "Pick 2 to 5 existing memory ids.",
                    "Weights must be > 0; higher = more plausible target.",
                    "Return JSON array of {memory_id, weight, reason} objects.",
                ],
            }
        raw = self.llm_client.complete(
            [
                {"role": "system", "content": "Return only strict JSON array."},
                {"role": "user", "content": json.dumps(prompt_payload, ensure_ascii=False)},
            ],
            temperature=0.7,
        )
        parsed = self._extract_json(raw)
        if not isinstance(parsed, list):
            return [], {}

        candidates: List[Candidate] = []
        weights: Dict[str, float] = {}
        if carrier_type == "semantic_realization":
            seen_texts = set()
            for idx, item in enumerate(parsed, start=1):
                if not isinstance(item, dict):
                    continue
                text = (item.get("text") or "").strip()
                weight = item.get("weight", item.get("score", 0.0))
                if not text or text in seen_texts:
                    continue
                seen_texts.add(text)
                cid = _candidate_id("sr", event.event_id, idx, text)
                candidates.append(
                    Candidate(
                        candidate_id=cid,
                        carrier_type=carrier_type,
                        payload={"text": text, "normalized_fact": event.text.strip()},
                        operation={"op": "add_memory", "text": text},
                        utility_score=1.0,
                    )
                )
                try:
                    weights[cid] = max(0.0, float(weight))
                except (TypeError, ValueError):
                    weights[cid] = 0.0
        else:
            valid_ids = {str(m.get("id")) for m in memory_snapshot if isinstance(m, dict)}
            seen_ids = set()
            for idx, item in enumerate(parsed, start=1):
                if not isinstance(item, dict):
                    continue
                mid = str(item.get("memory_id") or item.get("id") or "")
                if mid not in valid_ids or mid in seen_ids:
                    continue
                seen_ids.add(mid)
                weight = item.get("weight", item.get("score", 0.0))
                if carrier_type == "update_target":
                    payload = {"memory_id": mid, "new_text": event.text}
                    operation = {
                        "op": "update_memory",
                        "memory_id": mid,
                        "text": event.text,
                    }
                    prefix = "ut"
                else:  # link_target
                    payload = {"link_to": mid, "text": event.text}
                    operation = {
                        "op": "add_memory",
                        "text": event.text,
                        "links": [mid],
                    }
                    prefix = "lt"
                cid = _candidate_id(prefix, event.event_id, idx, mid)
                candidates.append(
                    Candidate(
                        candidate_id=cid,
                        carrier_type=carrier_type,
                        payload=payload,
                        operation=operation,
                        utility_score=1.0,
                    )
                )
                try:
                    weights[cid] = max(0.0, float(weight))
                except (TypeError, ValueError):
                    weights[cid] = 0.0

        # Normalize weights → probabilities. If LLM gave 0 / no weights,
        # fall back to a uniform prior.
        total = sum(weights.values())
        if total <= 0 and candidates:
            uniform = 1.0 / len(candidates)
            probabilities = {c.candidate_id: uniform for c in candidates}
        elif total > 0:
            probabilities = {k: v / total for k, v in weights.items()}
        else:
            probabilities = {}
        return candidates, probabilities

    # -- async assess (parallel fan-out) ---------------------------- #
    async def assess_carriers_async(
        self, event: MemoryEvent, memory_snapshot: Any
    ) -> List[CarrierAssessment]:
        """Parallel version of assess_carriers.

        Issues one prompt per carrier type and `gather`s. Requires the
        underlying client to expose `complete_async` (e.g.,
        AsyncOpenAIChatClient or MultiProviderClient(async_mode=True)).
        """

        if not hasattr(self.llm_client, "complete_async"):
            return self.assess_carriers(event, memory_snapshot)

        import asyncio

        prompts = []
        for carrier in CARRIER_TYPES:
            if carrier in {"update_target", "link_target"} and not memory_snapshot:
                # Skip fan-out for infeasible carriers; we'll mark them False below.
                continue
            prompts.append(
                (
                    carrier,
                    [
                        {
                            "role": "system",
                            "content": "Return only strict JSON.",
                        },
                        {
                            "role": "user",
                            "content": json.dumps(
                                {
                                    "task": "Is this carrier feasible for the incoming event?",
                                    "carrier_type": carrier,
                                    "event": event.text,
                                    "memory_snapshot": memory_snapshot,
                                    "output_schema": {
                                        "feasible": True,
                                        "score": 0.0,
                                        "reason": "...",
                                    },
                                },
                                ensure_ascii=False,
                            ),
                        },
                    ],
                )
            )

        responses = await self.llm_client.complete_many(
            [p[1] for p in prompts], temperature=0.0
        )
        assessments: List[CarrierAssessment] = []
        for (carrier, _), raw in zip(prompts, responses):
            parsed = self._extract_json(raw)
            if not isinstance(parsed, dict):
                continue
            assessments.append(
                CarrierAssessment(
                    carrier_type=carrier,
                    feasible=bool(parsed.get("feasible", False)),
                    score=self._clamp_score(parsed.get("score", 0.0)),
                    reason=str(parsed.get("reason", "")),
                )
            )
        # Carriers we skipped because they are structurally infeasible.
        for carrier in CARRIER_TYPES:
            if carrier in {"update_target", "link_target"} and not memory_snapshot:
                assessments.append(
                    CarrierAssessment(carrier, False, 0.0, "no existing memory")
                )
        if not assessments:
            assessments = [
                CarrierAssessment("semantic_realization", True, 1.0, "fallback")
            ]
        return assessments

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
