from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from memmark.backends.base import MemoryBackendAdapter


class JsonMemoryStore(MemoryBackendAdapter):
    def __init__(self, path: Optional[str] = None) -> None:
        self.path = Path(path) if path else None
        self._memories: List[Dict[str, Any]] = []
        if self.path and self.path.exists():
            self._memories = json.loads(self.path.read_text(encoding="utf-8"))

    def snapshot(self) -> List[Dict[str, Any]]:
        return [dict(item) for item in self._memories]

    def apply(self, operation: Dict[str, Any]) -> Dict[str, Any]:
        if operation.get("op") != "add_memory":
            raise ValueError(f"Unsupported operation: {operation.get('op')}")
        memory = {
            "id": f"m{len(self._memories) + 1}",
            "text": operation["text"],
            "links": operation.get("links", []),
        }
        self._memories.append(memory)
        self._persist()
        return memory

    def _persist(self) -> None:
        if not self.path:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._memories, ensure_ascii=False, indent=2), encoding="utf-8")
