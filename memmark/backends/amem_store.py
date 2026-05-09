"""A-MEM backend adapter (https://github.com/agiresearch/A-mem).

Wraps `agentic_memory.memory_system.AgenticMemorySystem` so it satisfies
the MemMark MemoryBackendAdapter contract: snapshot() + apply().

A-MEM organizes memory as agentic notes with keywords / tags / context /
links + ChromaDB retrieval. Each note has an id and an evolution history.
We expose:

  * `add_memory`  → AgenticMemorySystem.add_note()
  * `update_memory` → AgenticMemorySystem.delete() + add_note()
  * `delete_memory` → AgenticMemorySystem.delete()
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from memmark.backends.base import MemoryBackendAdapter

try:  # real A-MEM SDK
    from agentic_memory.memory_system import AgenticMemorySystem  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    AgenticMemorySystem = None  # type: ignore


def _strip_code_fence(text: str) -> str:
    s = (text or "").strip()
    m = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", s, re.DOTALL | re.IGNORECASE)
    return m.group(1) if m else s


class AMemBackend(MemoryBackendAdapter):
    """Backend adapter for the A-MEM (agentic memory) SDK.

    Per A-MEM official LoCoMo eval (`A-mem/test_advanced.py:301-305`):
    A-MEM ingests **turn-by-turn**, not via a separate fact-extraction
    step. Each LoCoMo turn becomes one ``add_note(text, time)``; A-mem's
    own internal ``analyze_content`` + ``process_memory`` decide what to
    keep, link, and evolve. Aligning to this protocol keeps our RQ1
    utility numbers directly comparable to the A-MEM paper.
    """

    preferred_ingestion_mode = "turn"

    def __init__(
        self,
        *,
        model_name: str = "all-MiniLM-L6-v2",
        llm_backend: str = "openai",
        llm_model: str = "gpt-4o-mini",
        evo_threshold: int = 100,
        api_key: Optional[str] = None,
        system: Optional[Any] = None,
    ) -> None:
        if system is not None:
            self.system = system
        else:
            if AgenticMemorySystem is None:
                raise RuntimeError(
                    "agentic_memory not installed. `pip install -e A-mem` "
                    "or pass `system=` explicitly."
                )
            self.system = AgenticMemorySystem(
                model_name=model_name,
                llm_backend=llm_backend,
                llm_model=llm_model,
                evo_threshold=evo_threshold,
                api_key=api_key,
            )
        self._evidence: Dict[str, Dict[str, Any]] = {}

    # -- MemoryBackendAdapter ------------------------------------- #
    def snapshot(self) -> List[Dict[str, Any]]:
        memories = []
        for note_id, note in self.system.memories.items():
            meta = self._evidence.get(note_id, {})
            memories.append(
                {
                    "id": note_id,
                    "text": getattr(note, "content", ""),
                    "context": getattr(note, "context", ""),
                    "keywords": list(getattr(note, "keywords", []) or []),
                    "tags": list(getattr(note, "tags", []) or []),
                    "links": list(getattr(note, "links", []) or []),
                    "category": getattr(note, "category", "Uncategorized"),
                    # Merge in side-channel bookkeeping so RQ5
                    # evidence_recall + driver QA rendering see the
                    # LoCoMo-side metadata that A-mem itself doesn't
                    # store on MemoryNote.
                    "dia_ids": list(meta.get("dia_ids", []) or []),
                    "session_index": meta.get("session_index"),
                    "speaker": meta.get("speaker", ""),
                    "session_date_time": meta.get("session_date_time", ""),
                }
            )
        return memories

    def apply(self, operation: Dict[str, Any]) -> Dict[str, Any]:
        op = operation.get("op")
        evidence = list(operation.get("dia_ids", []))
        session_index = operation.get("session_index")
        speaker = operation.get("speaker", "")
        if op == "add_memory":
            text = operation["text"]
            tags = list(operation.get("tags", []))
            if speaker:
                tags = list(dict.fromkeys(tags + [f"speaker:{speaker}"]))
            session_date_time = operation.get("session_date_time", "")
            # A-mem's add_note(content, time=...) stuffs `time` into the
            # MemoryNote.timestamp field, which is then surfaced by
            # find_related_memories as `talk start time:<value>`. Pass
            # LoCoMo's session_date_time so QA-time retrieval sees the
            # canonical talk-time anchor (matches A-mem's intended usage).
            note_id = self.system.add_note(
                text, time=session_date_time or None, tags=tags
            )
            self._evidence[note_id] = {
                "dia_ids": evidence,
                "session_index": session_index,
                "speaker": speaker,
                "session_date_time": session_date_time,
            }
            return self._fetch_record(note_id)
        if op == "update_memory":
            target_id = operation["memory_id"]
            new_text = operation["text"]
            old_meta = self._evidence.get(target_id, {})
            try:
                self.system.delete(target_id)
            except Exception:
                pass
            note_id = self.system.add_note(new_text)
            merged_evidence = list(
                dict.fromkeys(
                    list(old_meta.get("dia_ids", [])) + evidence
                )
            )
            self._evidence[note_id] = {
                "dia_ids": merged_evidence,
                "session_index": session_index or old_meta.get("session_index"),
                "speaker": speaker or old_meta.get("speaker", ""),
            }
            self._evidence.pop(target_id, None)
            return self._fetch_record(note_id)
        if op == "delete_memory":
            target_id = operation["memory_id"]
            ok = bool(self.system.delete(target_id))
            self._evidence.pop(target_id, None)
            return {"id": target_id, "deleted": ok}
        raise ValueError(f"Unsupported operation: {op}")

    def search(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        return list(self.system.search(query, k=k))

    # ----- watermark sampler injection ----- #
    def attach_sampler(self, sampler: Any) -> None:
        """Wrap A-mem's internal ``LLMController`` with the
        watermark sampler. Every internal LLM call A-mem makes
        (``analyze_content`` for keywords/context/tags +
        ``process_memory`` for evolution decisions) now goes through
        keyed n-best sampling.
        """

        from memmark.llm.watermarked import WatermarkedAMemController

        if hasattr(self.system, "llm_controller"):
            self.system.llm_controller = WatermarkedAMemController(
                sampler, self.system.llm_controller, prompt_name="amem"
            )

    # ----- canonical QA context ----- #
    def qa_context(
        self,
        question: str,
        k: int = 10,
        *,
        category: Optional[int] = None,
        gold_answer: Optional[str] = None,
        llm_client: Optional[Any] = None,
    ) -> Dict[str, Any]:
        """A-mem QA pipeline.

        When ``llm_client`` and ``category`` are both provided, runs the
        official **robust** A-mem LoCoMo QA protocol verbatim
        (``A-mem/test_advanced_robust.py:109-153``):

          1. ``generate_query_llm(question)``  → keyword string
          2. ``find_related_memories_raw(keywords, k)``  → raw context
          3. category-specific prompt (cat 2 = DATE-aware, cat 3 = exact
             words, cat 5 = adversarial A/B with gold), default = exact
             words from context
          4. plain-text answer (no json_schema), via ``llm_client``
          5. return ``{"mode": "answer", "text": <answer>}``

        The QA-time ``llm_client`` is the driver's separate raw client
        (NOT the watermark-wrapped one inside A-mem); this keeps QA
        read-only and does not embed bits during verification.

        If ``llm_client`` / ``category`` are absent, falls back to the
        retrieval-only context path (mode=``context``) using
        ``find_related_memories``.
        """

        # Robust A-mem QA protocol path
        if llm_client is not None and category is not None and self.system.memories:
            return self._qa_amem_robust(
                question, k=k,
                category=category, gold_answer=gold_answer,
                llm_client=llm_client,
            )

        # Fallback: context-only path
        if not self.system.memories:
            return {"mode": "context", "text": "(no long-term memory available)"}
        try:
            related_str, _ids = self.system.find_related_memories(question, k=k)
        except Exception:
            return {"mode": "context", "text": "(retrieval error)"}
        text = related_str or "(no related memories found)"
        return {"mode": "context", "text": text}

    def _qa_amem_robust(
        self,
        question: str,
        *,
        k: int,
        category: int,
        gold_answer: Optional[str],
        llm_client: Any,
    ) -> Dict[str, Any]:
        from memmark.benchmarks.locomo.qa_eval import (
            build_amem_keyword_prompt,
            build_cat_aware_qa_prompt,
        )

        # Step 1: keyword extraction (test_advanced_robust.py:96-107)
        keywords = question
        try:
            kw_raw = llm_client.complete(
                [{"role": "user", "content": build_amem_keyword_prompt(question)}],
                temperature=0.0,
            )
            try:
                import json as _json

                parsed = _json.loads(_strip_code_fence(kw_raw))
                kws = parsed.get("keywords")
                if isinstance(kws, str) and kws.strip():
                    keywords = kws.strip()
            except Exception:
                if isinstance(kw_raw, str) and kw_raw.strip():
                    keywords = kw_raw.strip()
        except Exception:
            pass

        # Step 2: raw retrieval (prefer find_related_memories_raw, fallback
        # to formatted find_related_memories on older A-mem SDK builds)
        raw_context = ""
        try:
            if hasattr(self.system, "find_related_memories_raw"):
                raw_context = self.system.find_related_memories_raw(keywords, k=k)
            else:
                related_str, _ = self.system.find_related_memories(keywords, k=k)
                raw_context = related_str or ""
        except Exception:
            raw_context = ""

        # Step 3: cat-aware prompt + plain-text answer
        user_prompt, temperature = build_cat_aware_qa_prompt(
            category, raw_context, question, gold_answer=gold_answer,
        )
        try:
            answer = llm_client.complete(
                [{"role": "user", "content": user_prompt}], temperature=temperature
            )
        except Exception:
            answer = ""
        return {"mode": "answer", "text": (answer or "").strip()}

    # -- internals ------------------------------------------------- #
    def _fetch_record(self, note_id: str) -> Dict[str, Any]:
        note = self.system.memories.get(note_id)
        meta = self._evidence.get(note_id, {})
        base = {
            "id": note_id,
            "text": getattr(note, "content", "") if note else "",
            "links": list(getattr(note, "links", []) or []) if note else [],
            "dia_ids": list(meta.get("dia_ids", [])),
            "session_index": meta.get("session_index"),
            "speaker": meta.get("speaker", ""),
            "session_date_time": meta.get("session_date_time", ""),
        }
        if note is not None:
            base.update(
                {
                    "context": getattr(note, "context", ""),
                    "keywords": list(getattr(note, "keywords", []) or []),
                    "tags": list(getattr(note, "tags", []) or []),
                }
            )
        return base
