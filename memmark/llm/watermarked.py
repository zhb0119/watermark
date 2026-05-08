"""Native LLM-level watermark hook.

Each memory system (A-MEM / Graphiti) drives its own
state-evolution decisions through *its own* internal LLM calls.
Instead of synthesizing parallel candidates outside the system, we
intercept those internal calls: sample n alternatives and keyed-pick
one. Bits are embedded directly in the LLM outputs the SDK consumes,
so the watermark lives in the system's actual evolution decisions.

Two hooks, one shared core:

  * :class:`WatermarkedSampler`     — keyed-sample + audit + Merkle log.
  * :class:`WatermarkedAMemController` — drop-in for A-mem's
                                          ``LLMController`` (sync,
                                          ``get_completion`` interface).
  * :func:`make_watermarked_graphiti_client` — subclasses Graphiti's
                                                ``LLMClient`` ABC (async,
                                                ``_generate_response``
                                                returns ``dict``).

There is no ``MemMark`` LLM running outside the system; the watermark
runs *as* the system's LLM.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, List

from memmark.core.commitment import make_commitment
from memmark.core.context import derive_nonce, sha256_text
from memmark.core.merkle_log import SessionMerkleLog
from memmark.core.sampler import sample_memory_transition
from memmark.core.types import Candidate, DecisionPoint, SessionHeader


# --------------------------------------------------------------- #
# Core: keyed sampler + audit log
# --------------------------------------------------------------- #


class WatermarkedSampler:
    """Shared core for all three SDK adapters.

    Each LLM call routed through a wrapper does:

      1. Sample ``n_candidates`` completions from the underlying LLM
         (high temperature so they differ).
      2. Cluster by exact-string equality (after light normalization).
      3. Build a :class:`DecisionPoint` whose candidates are the
         cluster representatives and whose probabilities are the
         empirical cluster mass.
      4. Derive ``nonce_t = HMAC(K, ctx_t)`` where ``ctx_t`` is a
         hash over the SDK's prompt + agent / user / session ids.
      5. Run :func:`sample_memory_transition` with the active sampler
         mode → keyed pick.
      6. Append commitment to the Merkle log + AuditRecord to the
         in-memory audit list.
      7. Return the selected completion to the SDK.

    Single cluster (all completions identical) ⇒ no watermarkable
    freedom; pass through verbatim, no audit emitted.
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
        n_candidates: int = 4,
        sampling_temperature: float = 0.7,
    ) -> None:
        self.secret_key = secret_key
        self.payload_bits = payload_bits
        self.agent_id = agent_id
        self.user_id = user_id
        self.session_id = session_id
        self.sampler_mode = sampler_mode
        self.watermark_version = watermark_version
        self.n_candidates = max(2, int(n_candidates))
        self.sampling_temperature = float(sampling_temperature)
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
        # Optional per-event metadata set by the driver before the
        # backend call begins (lets the audit record link back to the
        # LoCoMo dia_ids that triggered this LLM cascade).
        self._event_context: Dict[str, Any] = {}

    # ----- entry point ----------------------------------------------- #
    def intercept(
        self,
        candidates: List[str],
        ctx_text: str,
        *,
        prompt_name: str = "",
    ) -> str:
        """Cluster + keyed-sample + audit. Returns the selected string.

        ``candidates`` are raw LLM completions (already the SDK's exact
        output type — string for sync interfaces, JSON-stringified
        dict for structured-output interfaces). ``ctx_text`` is the
        SDK's prompt (system + user concatenated).
        """

        if not candidates:
            return ""
        if len(candidates) == 1:
            return candidates[0]

        clusters = self._cluster(candidates)
        if len(clusters) < 2:
            # No watermarkable freedom — single equivalence class.
            return clusters[0][0]

        cluster_reps = [c[0] for c in clusters]
        cluster_sizes = [len(c) for c in clusters]
        total = float(sum(cluster_sizes))

        ctx_payload = {
            "agent_id": self.agent_id,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "round": self.round_num,
            "event_context": self._event_context,
            "prompt": ctx_text,
            "prompt_name": prompt_name,
        }
        ctx_serialized = json.dumps(ctx_payload, sort_keys=True, ensure_ascii=False)
        ctx_hash = sha256_text(ctx_serialized)
        nonce = derive_nonce(self.secret_key, ctx_serialized)

        cands_obj: List[Candidate] = []
        probs: Dict[str, float] = {}
        for idx, rep in enumerate(cluster_reps, start=1):
            cid = self._candidate_id(idx, rep)
            cands_obj.append(
                Candidate(
                    candidate_id=cid,
                    carrier_type="llm_call",
                    payload={"text": rep, "prompt_name": prompt_name},
                    operation={},
                    utility_score=cluster_sizes[idx - 1] / total,
                )
            )
            probs[cid] = cluster_sizes[idx - 1] / total

        decision = DecisionPoint(
            decision_id=f"d{self.round_num + 1}",
            tau="llm_call",
            candidates=cands_obj,
            probabilities=probs,
            context=ctx_hash,
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
        )
        self.merkle_log.append(audit.commitment)
        self.audit_log.append(audit)
        self.round_num += 1
        return sample.selected_candidate.payload["text"]

    # ----- per-event metadata ---------------------------------------- #
    def set_event_context(self, **fields: Any) -> None:
        """Driver calls this before each backend.apply() so audits can
        be linked back to LoCoMo turn / fact / session metadata.
        """

        self._event_context = dict(fields)

    def clear_event_context(self) -> None:
        self._event_context = {}

    # ----- session sealing ------------------------------------------- #
    def seal_session(self) -> SessionHeader:
        return self.merkle_log.seal()

    # ----- internals ------------------------------------------------- #
    @staticmethod
    def _cluster(candidates: List[str]) -> List[List[str]]:
        """Cluster by exact-string equality after JSON normalization
        (so identically-shaped JSON outputs collapse even if key order
        differs).
        """

        clusters: List[List[str]] = []
        normalized_keys: List[str] = []
        for c in candidates:
            key = _normalize_for_cluster(c)
            placed = False
            for i, existing in enumerate(normalized_keys):
                if existing == key:
                    clusters[i].append(c)
                    placed = True
                    break
            if not placed:
                clusters.append([c])
                normalized_keys.append(key)
        return clusters

    def _candidate_id(self, idx: int, payload_text: str) -> str:
        digest = hashlib.sha256(
            f"{self.round_num}|{idx}|{payload_text}".encode("utf-8")
        ).hexdigest()[:10]
        return f"llm_{idx}_{digest}"


def _normalize_for_cluster(text: str) -> str:
    """Best-effort JSON-stable canonicalization. Falls back to raw
    string when the text isn't valid JSON.
    """

    s = (text or "").strip()
    try:
        obj = json.loads(s)
    except json.JSONDecodeError:
        return s
    return json.dumps(obj, sort_keys=True, ensure_ascii=False)


# --------------------------------------------------------------- #
# A-MEM adapter — drop-in LLMController replacement
# --------------------------------------------------------------- #


class WatermarkedAMemController:
    """Drop-in replacement for A-mem's ``LLMController``.

    A-mem's ``AgenticMemorySystem`` calls
    ``self.llm_controller.llm.get_completion(prompt, response_format,
    temperature)`` and ``self.llm_controller.llm.get_completion(...)``
    in evolution / metadata extraction. We wrap that call: take
    ``n_candidates`` samples, keyed-pick one, return.

    To install: build the system normally, then replace its
    ``llm_controller`` with this wrapper around the original.
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
        # A-mem's evolution code touches `.llm` directly; expose a
        # wrapped inner so behaviour stays identical when callers
        # hold a reference to it.
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
        candidates: List[str] = []
        for _ in range(self.sampler.n_candidates):
            try:
                out = self.underlying.get_completion(
                    prompt, response_format, self.sampler.sampling_temperature
                )
            except Exception:
                continue
            if isinstance(out, str) and out.strip():
                candidates.append(out)
        if not candidates:
            # Fall back to a single deterministic call so the SDK
            # doesn't crash; no watermark bits embedded.
            try:
                return self.underlying.get_completion(
                    prompt, response_format, temperature
                )
            except Exception:
                return ""
        return self.sampler.intercept(
            candidates, ctx_text=prompt, prompt_name=self._prompt_name
        )

    def __getattr__(self, item: str) -> Any:
        # Pass-through for attributes A-mem occasionally inspects on
        # the inner LLM object (model name, api_key, etc.).
        return getattr(self.underlying, item)


# --------------------------------------------------------------- #
# Graphiti adapter — implements LLMClient ABC
# --------------------------------------------------------------- #


def make_watermarked_graphiti_client(sampler: WatermarkedSampler, underlying: Any):
    """Lazy-construct a wrapper that subclasses Graphiti's LLMClient.

    Graphiti imports are heavy and only needed at backend init time;
    deferring the import keeps the SDK optional.
    """

    try:
        from graphiti_core.llm_client.client import LLMClient
        from graphiti_core.prompts.models import Message
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "graphiti_core is required for the Graphiti backend. "
            "`pip install graphiti-core` first."
        ) from exc

    class WatermarkedGraphitiClient(LLMClient):
        """Subclass of :class:`graphiti_core.llm_client.client.LLMClient`.

        Graphiti's contract: ``_generate_response(messages, response_model,
        max_tokens, model_size) -> dict``. We sample ``n_candidates`` such
        dicts, JSON-canonicalize them, keyed-pick one, return it.
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
            candidates: List[str] = []
            raw_dicts: List[Dict[str, Any]] = []
            for _ in range(self._sampler.n_candidates):
                try:
                    out = await self._underlying._generate_response(
                        messages, response_model, max_tokens, model_size
                    )
                except Exception:
                    continue
                if isinstance(out, dict):
                    raw_dicts.append(out)
                    candidates.append(json.dumps(out, sort_keys=True, ensure_ascii=False))
                else:
                    raw_dicts.append({"_raw": str(out)})
                    candidates.append(str(out))

            if not candidates:
                return await self._underlying._generate_response(
                    messages, response_model, max_tokens, model_size
                )

            ctx_text = "\n".join(getattr(m, "content", "") for m in messages)
            selected = self._sampler.intercept(
                candidates, ctx_text=ctx_text, prompt_name="graphiti"
            )
            try:
                parsed = json.loads(selected)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                pass
            # Fall back to the first raw dict so the SDK gets a usable shape.
            return raw_dicts[0] if raw_dicts else {}

    return WatermarkedGraphitiClient(sampler, underlying)


__all__ = [
    "WatermarkedSampler",
    "WatermarkedAMemController",
    "make_watermarked_graphiti_client",
]
