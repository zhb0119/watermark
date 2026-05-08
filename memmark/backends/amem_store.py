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

from typing import Any, Dict, List, Optional

from memmark.backends.base import MemoryBackendAdapter

try:  # real A-MEM SDK
    from agentic_memory.memory_system import AgenticMemorySystem  # type: ignore
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    AgenticMemorySystem = None  # type: ignore


class AMemBackend(MemoryBackendAdapter):
    """Backend adapter for the A-MEM (agentic memory) SDK.

    Per A-MEM upstream paper (`WujiangXu/AgenticMemory`) + Mem0's
    LoCoMo blog: A-MEM expects pre-extracted, fact-shaped notes
    (one durable observation per `add_note`). The driver therefore
    runs LoCoMo's `CONVERSATION2FACTS_PROMPT` per session and feeds
    the resulting facts (each with dia_id evidence) into A-MEM.
    """

    preferred_ingestion_mode = "fact"

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
            memories.append(
                {
                    "id": note_id,
                    "text": getattr(note, "content", ""),
                    "context": getattr(note, "context", ""),
                    "keywords": list(getattr(note, "keywords", []) or []),
                    "tags": list(getattr(note, "tags", []) or []),
                    "links": list(getattr(note, "links", []) or []),
                    "category": getattr(note, "category", "Uncategorized"),
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
            note_id = self.system.add_note(text, tags=tags)
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

    # ----- backend-aware carrier candidates ----- #
    def candidate_update_targets(self, text: str, k: int = 5):
        """Use A-MEM's ChromaDB retrieval to surface plausible update
        targets — those are the memories whose existing content is
        closest to the incoming event in embedding space."""

        try:
            hits = list(self.system.search(text, k=k))
        except Exception:
            return []
        out = []
        for h in hits:
            note_id = h.get("id") or h.get("memory_id")
            if note_id is None:
                continue
            out.append(self._fetch_record(str(note_id)))
        return out

    def candidate_link_targets(self, text: str, k: int = 5):
        """A-MEM's `find_related_memories` returns top-k semantically
        related notes — exactly the candidate links."""

        try:
            related_str, indices = self.system.find_related_memories(text, k=k)
        except Exception:
            return self.candidate_update_targets(text, k=k)
        out: List[Dict[str, Any]] = []
        for note_id in self.system.memories.keys():
            if len(out) >= k:
                break
            out.append(self._fetch_record(note_id))
        return out

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
