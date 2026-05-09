"""Native LLM-level watermark hook (AgentMark-style self-reported weights).

Each memory system (A-MEM / Graphiti) drives its own state-evolution
decisions through *its own* internal LLM calls. We intercept those
calls at the SDK's LLM-client boundary and use the AgentMark
``action_weights`` pattern: the wrapper modifies the prompt to ask
the LLM to emit *K candidate decisions plus self-reported weights*
in one response, then runs the keyed binning sampler over
``(candidates, weights)``. Bits are embedded directly in the LLM
output the SDK consumes; the SDK is unaware.

Two hooks, one shared core:

  * :class:`WatermarkedSampler` — keyed-sample + audit + Merkle log.
  * :class:`WatermarkedAMemController` — drop-in for A-mem's
    ``LLMController``; appends AgentMark instruction to the prompt,
    parses the wrapped response, returns the chosen ``decision``
    JSON string.
  * :func:`make_watermarked_graphiti_client` — subclasses Graphiti's
    ``LLMClient`` ABC; dynamically wraps the SDK's Pydantic
    ``response_model`` into ``Wrapped(candidates: List[Candidate],
    thought: str)`` and returns the chosen ``decision`` dict.
"""

from __future__ import annotations

import hashlib
import json
import re
from typing import Any, Dict, List, Tuple

from memmark.core.commitment import make_commitment
from memmark.core.context import derive_nonce
from memmark.core.merkle_log import SessionMerkleLog
from memmark.core.sampler import sample_memory_transition
from memmark.core.types import Candidate, DecisionPoint, SessionHeader


# --------------------------------------------------------------- #
# AgentMark-style prompt suffix + parser
# --------------------------------------------------------------- #


CARRIER_VOCAB = ("update_target", "link_target", "semantic_realization")


AGENTMARK_INSTRUCTION_TMPL = """

CRITICAL OVERRIDE: instead of returning a single answer in the schema
above, return JSON in EXACTLY this multi-candidate form:

{{
  "candidates": [
    {{"decision": <answer matching the original schema>, "weight": <float>}},
    {{"decision": <plausible alternative>, "weight": <float>}}
    // ... up to {target_k} entries
  ],
  "thought": "<brief rationale>",
  "carrier": "<one of: update_target | link_target | semantic_realization>"
}}

The "carrier" field describes what kind of decision the candidates above
represent — pick the single best fit:

- "update_target": you are picking which existing memory record / entity /
  edge this new information should update or attach to.
- "link_target":   you are picking which existing memory(s) to link the new
  fact to (without changing them).
- "semantic_realization": you are picking how to phrase / structure the same
  fact (different wording, different tag set, different relation label).

Other requirements:
- Provide {target_k} candidate alternatives (or as many distinct
  plausible alternatives as you can produce).
- Each "decision" object must independently match the original schema
  described above (same field names, same types).
- All "weight" values are positive floats; rank by your real
  preference. Use small values like 1e-3 for unlikely alternatives.
- Avoid uniform weights.
- Sum need not be exact; will be normalized.
- Return ONLY this JSON; no extra text or code fences.
"""


def _format_agentmark_instruction(target_k: int) -> str:
    return AGENTMARK_INSTRUCTION_TMPL.format(target_k=target_k)


def _strip_code_fence(text: str) -> str:
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL | re.IGNORECASE)
    if fence:
        return fence.group(1)
    return text


def _extract_json_payload(raw: str) -> Any:
    """Best-effort JSON extraction (handles code fences / loose text)."""

    s = (raw or "").strip()
    if not s:
        return None
    s = _strip_code_fence(s)
    try:
        return json.loads(s)
    except json.JSONDecodeError:
        pass
    # Locate outermost braces
    start = s.find("{")
    end = s.rfind("}")
    if start != -1 and end > start:
        try:
            return json.loads(s[start : end + 1])
        except json.JSONDecodeError:
            return None
    return None


def parse_agentmark_response(
    raw: str,
) -> Tuple[List[Any], List[float], List[str]]:
    """Parse ``{candidates: [{decision, weight}, ...], thought,
    carriers / carrier}`` → ``(decisions, weights, carriers)``.

    Returns ``([], [], ["llm_call"])`` when parsing fails.

    The LLM may report **multiple** carriers per call (mixed-decision
    SDK calls like Graphiti's ``extract_nodes_and_edges`` can both
    pick relation labels (semantic_realization) AND attach to existing
    entities (link_target) in the same call). We accept either:

      * ``"carriers": ["update_target", "semantic_realization"]``  (preferred)
      * ``"carrier":  "update_target"``                            (legacy single)
      * ``"carrier":  ["update_target", "..."]``                   (also accepted)

    Returned list is deduplicated, in LLM-reported order. The first
    entry is treated as the primary tau by the sampler; the rest go
    into ``AuditRecord.extra_carriers`` so RQ5 can count the audit in
    every relevant carrier bucket.
    """

    parsed = _extract_json_payload(raw)
    if not isinstance(parsed, dict):
        return [], [], ["llm_call"]
    candidates = parsed.get("candidates")
    if not isinstance(candidates, list):
        return [], [], ["llm_call"]
    decisions: List[Any] = []
    weights: List[float] = []
    for c in candidates:
        if not isinstance(c, dict) or "decision" not in c:
            continue
        try:
            w = float(c.get("weight", 0.0))
        except (TypeError, ValueError):
            w = 0.0
        decisions.append(c["decision"])
        weights.append(max(w, 1e-6))

    raw_carriers = parsed.get("carriers")
    if raw_carriers is None:
        raw_carriers = parsed.get("carrier", [])
    if isinstance(raw_carriers, str):
        raw_carriers = [raw_carriers]
    if not isinstance(raw_carriers, list):
        raw_carriers = []
    carriers: List[str] = []
    for c in raw_carriers:
        if not isinstance(c, str):
            continue
        cc = c.strip().lower()
        if cc in CARRIER_VOCAB and cc not in carriers:
            carriers.append(cc)
    if not carriers:
        carriers = ["llm_call"]
    return decisions, weights, carriers


# --------------------------------------------------------------- #
# Core: keyed sampler + audit log
# --------------------------------------------------------------- #


class WatermarkedSampler:
    """Shared core for both SDK adapters.

    Each LLM call routed through a wrapper does:

      1. Wrapper appends AgentMark instruction to the SDK's prompt.
      2. Wrapper makes ONE underlying LLM call; LLM returns
         ``{candidates: [{decision, weight}, ...], thought}``.
      3. Wrapper calls :meth:`intercept` with ``(decisions, weights,
         ctx_text)``.
      4. ``intercept`` builds a ``DecisionPoint`` whose probabilities
         are the LLM-self-reported (and renormalized) weights.
      5. Derives ``nonce_t = HMAC(K, ctx_t)`` and runs
         :func:`sample_memory_transition` for the keyed pick.
      6. Appends commitment to the Merkle log + AuditRecord to the
         in-memory audit list.
      7. Returns the chosen decision (JSON string) for the wrapper to
         hand back to the SDK.

    Single candidate (LLM didn't comply) ⇒ no watermarkable freedom;
    pass through verbatim, no audit emitted.
    """

    def __init__(
        self,
        *,
        secret_key: str,
        payload_bits: str,
        agent_id: str,
        user_id: str,
        session_id: str,
        sampler_mode: str = "watermark",
        watermark_version: str = "memmark-native-v0.1",
        target_k: int = 4,
    ) -> None:
        self.secret_key = secret_key
        self.payload_bits = payload_bits
        self.agent_id = agent_id
        self.user_id = user_id
        self.session_id = session_id
        self.sampler_mode = sampler_mode
        self.watermark_version = watermark_version
        # Number of candidates we ask the LLM to enumerate per call.
        self.target_k = max(2, int(target_k))
        self.bit_index = 0
        self.round_num = 0
        self.audit_log: List = []
        self.merkle_log = SessionMerkleLog(
            agent_id=agent_id,
            user_id=user_id,
            session_id=session_id,
            secret_key=secret_key,
            watermark_version=watermark_version,
        )
        self._event_context: Dict[str, Any] = {}

    # ----- entry point ----------------------------------------------- #
    def intercept(
        self,
        decisions: List[str],
        weights: List[float],
        ctx_text: str,
        *,
        prompt_name: str = "",
        tau: Any = "llm_call",
    ) -> str:
        """Keyed-pick over ``(decisions, weights)``; emit audit.

        ``decisions`` are the K candidate decision strings the LLM
        produced (each is the SDK's expected output for that call).
        ``weights`` are the LLM-self-reported per-candidate weights
        (will be renormalized).

        ``tau`` may be a single string (legacy) or a list of strings
        (multi-label per :func:`parse_agentmark_response`). The first
        item is recorded as the primary ``tau`` on
        :class:`DecisionPoint` / :class:`AuditRecord`; remaining items
        go into ``AuditRecord.extra_carriers`` for RQ5 multi-bucket
        counting.
        """

        if not decisions:
            return ""
        if len(decisions) == 1:
            return decisions[0]

        # Normalize tau into (primary, extras)
        if isinstance(tau, str):
            tau_list = [tau] if tau else ["llm_call"]
        elif isinstance(tau, (list, tuple)) and tau:
            tau_list = [str(t) for t in tau if isinstance(t, str)] or ["llm_call"]
        else:
            tau_list = ["llm_call"]
        primary_tau = tau_list[0]
        extra_taus = tuple(tau_list[1:])

        # Renormalize weights
        total = float(sum(weights))
        if total <= 0:
            normalized = [1.0 / len(decisions)] * len(decisions)
        else:
            normalized = [w / total for w in weights]

        ctx_payload = {
            "agent_id": self.agent_id,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "round": self.round_num,
            "event_context": self._event_context,
            "prompt": ctx_text,
            "prompt_name": prompt_name,
        }
        # IMPORTANT: store the *serialized* ctx string on the
        # DecisionPoint, not its hash. The R3 verifier re-derives nonce
        # via `derive_nonce(K, audit.context)`, which must match the
        # nonce we used here (`derive_nonce(K, ctx_serialized)`). If we
        # stored ctx_hash instead, the verifier would HMAC the hash and
        # produce a different nonce → R3 silently fails.
        ctx_serialized = json.dumps(ctx_payload, sort_keys=True, ensure_ascii=False)
        nonce = derive_nonce(self.secret_key, ctx_serialized)

        cands_obj: List[Candidate] = []
        probs: Dict[str, float] = {}
        for idx, dec in enumerate(decisions, start=1):
            cid = self._candidate_id(idx, dec)
            cands_obj.append(
                Candidate(
                    candidate_id=cid,
                    carrier_type=primary_tau,
                    payload={"text": dec, "prompt_name": prompt_name},
                    operation={},
                    utility_score=normalized[idx - 1],
                )
            )
            probs[cid] = normalized[idx - 1]

        decision = DecisionPoint(
            decision_id=f"d{self.round_num + 1}",
            tau=primary_tau,
            candidates=cands_obj,
            probabilities=probs,
            context=ctx_serialized,
            round_num=self.round_num,
            nonce=nonce,
            watermark_version=self.watermark_version,
        )

        sample = sample_memory_transition(
            decision,
            payload_bits=self.payload_bits,
            bit_index=self.bit_index,
            mode=self.sampler_mode,
        )
        self.bit_index += sample.bits_embedded

        audit = make_commitment(
            decision,
            selected_candidate_id=sample.selected_candidate.candidate_id,
            bits_embedded=sample.bits_embedded,
            bit_index_after=self.bit_index,
            keep_reveal=True,
            extra_carriers=extra_taus,
        )
        self.merkle_log.append(audit.commitment)
        self.audit_log.append(audit)
        self.round_num += 1
        return sample.selected_candidate.payload["text"]

    # ----- per-event metadata ---------------------------------------- #
    def set_event_context(self, **fields: Any) -> None:
        self._event_context = dict(fields)

    def clear_event_context(self) -> None:
        self._event_context = {}

    # ----- session sealing ------------------------------------------- #
    def seal_session(self) -> SessionHeader:
        return self.merkle_log.seal()

    # ----- internals ------------------------------------------------- #
    def _candidate_id(self, idx: int, payload_text: str) -> str:
        digest = hashlib.sha256(
            f"{self.round_num}|{idx}|{payload_text}".encode("utf-8")
        ).hexdigest()[:10]
        return f"llm_{idx}_{digest}"


# --------------------------------------------------------------- #
# A-MEM adapter — drop-in LLMController replacement
# --------------------------------------------------------------- #


class WatermarkedAMemController:
    """Drop-in replacement for A-mem's ``LLMController``.

    A-mem's ``AgenticMemorySystem`` calls
    ``self.llm_controller.llm.get_completion(prompt, response_format,
    temperature)`` for ``analyze_content`` / ``process_memory``. Our
    wrapper appends an AgentMark-style instruction to the prompt,
    relaxes ``response_format`` to permissive JSON, parses the
    wrapped response, runs keyed pick, returns the chosen
    ``decision`` JSON string.
    """

    def __init__(
        self,
        sampler: WatermarkedSampler,
        underlying: Any,
        *,
        prompt_name: str = "amem",
    ) -> None:
        self.sampler = sampler
        self.underlying = underlying
        self._prompt_name = prompt_name
        self.llm = _AMemInnerWrapper(sampler, underlying.llm, prompt_name)

    def get_completion(
        self,
        prompt: str,
        response_format: Any = None,
        temperature: float = 1.0,
    ) -> str:
        return self.llm.get_completion(prompt, response_format, temperature)


class _AMemInnerWrapper:
    """Wraps the inner controller object that A-mem accesses as
    ``llm_controller.llm`` (e.g. ``OpenAIController``).
    """

    def __init__(self, sampler: WatermarkedSampler, underlying: Any, prompt_name: str):
        self.sampler = sampler
        self.underlying = underlying
        self._prompt_name = prompt_name

    def get_completion(
        self,
        prompt: str,
        response_format: Any = None,
        temperature: float = 1.0,
    ) -> str:
        wrapped_prompt = prompt + _format_agentmark_instruction(self.sampler.target_k)
        # Relax response_format from strict json_schema to permissive
        # json_object — the original schema is now described in the
        # prompt body.
        permissive_format = {"type": "json_object"}
        try:
            raw = self.underlying.get_completion(
                wrapped_prompt, permissive_format, temperature
            )
        except Exception:
            return self._passthrough(prompt, response_format, temperature)
        if not isinstance(raw, str) or not raw.strip():
            return self._passthrough(prompt, response_format, temperature)

        decisions, weights, carriers = parse_agentmark_response(raw)
        if len(decisions) < 2:
            # LLM didn't comply; fall back to a clean SDK call (no
            # watermark embedded for this LLM call).
            return self._passthrough(prompt, response_format, temperature)

        # Convert each decision to a stable JSON string for the SDK.
        decision_strs = [
            json.dumps(d, sort_keys=True, ensure_ascii=False)
            if not isinstance(d, str)
            else d
            for d in decisions
        ]
        return self.sampler.intercept(
            decision_strs,
            weights,
            ctx_text=prompt,
            prompt_name=self._prompt_name,
            tau=carriers,
        )

    def _passthrough(self, prompt, response_format, temperature) -> str:
        try:
            return self.underlying.get_completion(prompt, response_format, temperature)
        except Exception:
            return ""

    def __getattr__(self, item: str) -> Any:
        return getattr(self.underlying, item)


# --------------------------------------------------------------- #
# Graphiti adapter — implements LLMClient ABC
# --------------------------------------------------------------- #


def make_watermarked_graphiti_client(sampler: WatermarkedSampler, underlying: Any):
    """Build a Graphiti ``LLMClient`` subclass that intercepts each
    ``_generate_response`` call with the AgentMark-style 1-call
    pattern.

    For each call with a Pydantic ``response_model``, we dynamically
    create a wrapper Pydantic model
    ``Wrapped(candidates: List[Candidate(decision: response_model,
    weight: float)], thought: str)``, ask the underlying client to
    fill it, parse, keyed-pick, and return the chosen ``decision``
    as a dict.
    """

    try:
        from graphiti_core.llm_client.client import LLMClient
        from pydantic import BaseModel, create_model
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "graphiti_core (and pydantic) are required for the Graphiti backend. "
            "`pip install graphiti-core` first."
        ) from exc

    class WatermarkedGraphitiClient(LLMClient):
        """Subclass of :class:`graphiti_core.llm_client.client.LLMClient`.

        AgentMark-style 1-call interception: dynamically wrap the
        SDK's Pydantic ``response_model`` to ask for K candidates +
        weights, then keyed-pick one.
        """

        def __init__(self, sampler_: WatermarkedSampler, underlying_: Any):
            super().__init__(config=getattr(underlying_, "config", None))
            self._sampler = sampler_
            self._underlying = underlying_

        async def _generate_response(  # type: ignore[override]
            self,
            messages,
            response_model=None,
            max_tokens: int = 8192,
            model_size=None,
        ) -> Dict[str, Any]:
            if response_model is None:
                # No structured output to wrap — pass through.
                return await self._underlying._generate_response(
                    messages, None, max_tokens, model_size
                )

            # Build wrapper Pydantic model on the fly.
            try:
                Candidate_M = create_model(
                    "AGMCandidate",
                    decision=(response_model, ...),
                    weight=(float, 1.0),
                )
                Wrapped_M = create_model(
                    "AGMWrapped",
                    candidates=(List[Candidate_M], ...),
                    thought=(str, ""),
                    carriers=(List[str], []),
                )
            except Exception:
                return await self._underlying._generate_response(
                    messages, response_model, max_tokens, model_size
                )

            # Inject AgentMark instruction onto the last message.
            instr = _format_agentmark_instruction(self._sampler.target_k)
            try:
                last_msg = messages[-1]
                cloned_last = type(last_msg)(
                    role=last_msg.role,
                    content=(last_msg.content or "") + instr,
                )
                new_messages = list(messages[:-1]) + [cloned_last]
            except Exception:
                new_messages = messages

            try:
                wrapped_resp = await self._underlying._generate_response(
                    new_messages, Wrapped_M, max_tokens, model_size
                )
            except Exception:
                return await self._underlying._generate_response(
                    messages, response_model, max_tokens, model_size
                )

            candidates = (
                wrapped_resp.get("candidates") if isinstance(wrapped_resp, dict) else None
            )
            if not isinstance(candidates, list) or len(candidates) < 2:
                # LLM didn't comply or only gave one. Fall back.
                if isinstance(candidates, list) and len(candidates) == 1:
                    cand = candidates[0]
                    if isinstance(cand, dict) and isinstance(cand.get("decision"), dict):
                        return cand["decision"]
                return await self._underlying._generate_response(
                    messages, response_model, max_tokens, model_size
                )

            decisions: List[Dict[str, Any]] = []
            weights: List[float] = []
            for c in candidates:
                if not isinstance(c, dict) or "decision" not in c:
                    continue
                dec = c["decision"]
                if not isinstance(dec, dict):
                    continue
                try:
                    w = float(c.get("weight", 0.0))
                except (TypeError, ValueError):
                    w = 0.0
                decisions.append(dec)
                weights.append(max(w, 1e-6))
            if len(decisions) < 2:
                return await self._underlying._generate_response(
                    messages, response_model, max_tokens, model_size
                )

            decision_strs = [
                json.dumps(d, sort_keys=True, ensure_ascii=False, default=str)
                for d in decisions
            ]
            ctx_text = "\n".join(getattr(m, "content", "") for m in messages)

            # Multi-label carriers — accept either ``carriers`` (list)
            # or ``carrier`` (single string for backward compat).
            carriers: List[str] = []
            if isinstance(wrapped_resp, dict):
                raw_cs = wrapped_resp.get("carriers")
                if raw_cs is None:
                    raw_cs = wrapped_resp.get("carrier", [])
                if isinstance(raw_cs, str):
                    raw_cs = [raw_cs]
                if isinstance(raw_cs, list):
                    for c in raw_cs:
                        if isinstance(c, str):
                            cc = c.strip().lower()
                            if cc in CARRIER_VOCAB and cc not in carriers:
                                carriers.append(cc)
            if not carriers:
                carriers = ["llm_call"]

            chosen_str = self._sampler.intercept(
                decision_strs,
                weights,
                ctx_text=ctx_text,
                prompt_name="graphiti",
                tau=carriers,
            )
            try:
                chosen = json.loads(chosen_str)
                if isinstance(chosen, dict):
                    return chosen
            except json.JSONDecodeError:
                pass
            # Fall back to first decision.
            return decisions[0]

    return WatermarkedGraphitiClient(sampler, underlying)


__all__ = [
    "WatermarkedSampler",
    "WatermarkedAMemController",
    "make_watermarked_graphiti_client",
    "parse_agentmark_response",
    "CARRIER_VOCAB",
]
