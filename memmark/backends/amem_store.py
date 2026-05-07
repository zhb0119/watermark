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
    """Backend adapter for the A-MEM (agentic memory) SDK."""

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
        if op == "add_memory":
            text = operation["text"]
            note_id = self.system.add_note(text)
            return self._fetch_record(note_id)
        if op == "update_memory":
            target_id = operation["memory_id"]
            new_text = operation["text"]
            try:
                self.system.delete(target_id)
            except Exception:
                pass
            note_id = self.system.add_note(new_text)
            return self._fetch_record(note_id)
        if op == "delete_memory":
            target_id = operation["memory_id"]
            ok = bool(self.system.delete(target_id))
            return {"id": target_id, "deleted": ok}
        raise ValueError(f"Unsupported operation: {op}")

    def search(self, query: str, k: int = 5) -> List[Dict[str, Any]]:
        return list(self.system.search(query, k=k))

    # -- internals ------------------------------------------------- #
    def _fetch_record(self, note_id: str) -> Dict[str, Any]:
        note = self.system.memories.get(note_id)
        if note is None:
            return {"id": note_id, "text": "", "links": []}
        return {
            "id": note_id,
            "text": getattr(note, "content", ""),
            "context": getattr(note, "context", ""),
            "keywords": list(getattr(note, "keywords", []) or []),
            "tags": list(getattr(note, "tags", []) or []),
            "links": list(getattr(note, "links", []) or []),
        }
