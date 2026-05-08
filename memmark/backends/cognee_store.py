"""Cognee backend adapter (https://github.com/topoteretes/cognee).

Cognee's API is async and uses `dataset_name` to scope writes. We bridge
async to sync via `asyncio.run` so MemMark's evolve() loop can stay
synchronous; if you're already inside an event loop, use
`apply_async()` directly.

Each new memory becomes a separate dataset entry. cognify() builds the
KG; search() returns GRAPH_COMPLETION results.
"""

from __future__ import annotations

import asyncio
import os
import uuid
from typing import Any, Dict, List, Optional

from memmark.backends.base import MemoryBackendAdapter

try:  # real Cognee SDK
    import cognee  # type: ignore
    from cognee.api.v1.search import SearchType  # type: ignore
    HAS_COGNEE = True
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    cognee = None  # type: ignore
    SearchType = None  # type: ignore
    HAS_COGNEE = False


class CogneeBackend(MemoryBackendAdapter):
    """Backend adapter wrapping cognee.add / cognee.cognify / cognee.search."""

    def __init__(
        self,
        *,
        dataset_name: Optional[str] = None,
        run_cognify: bool = True,
        user: Optional[Any] = None,
    ) -> None:
        if not HAS_COGNEE:
            raise RuntimeError(
                "cognee not installed. `pip install cognee` or run from "
                "the cloned repo with `pip install -e .` first."
            )
        self.dataset_name = dataset_name or os.getenv(
            "MEMMARK_COGNEE_DATASET", f"memmark_{uuid.uuid4().hex[:8]}"
        )
        self.run_cognify = run_cognify
        self.user = user
        self._memories: List[Dict[str, Any]] = []

    # -- MemoryBackendAdapter ------------------------------------- #
    def snapshot(self) -> List[Dict[str, Any]]:
        return [dict(m) for m in self._memories]

    def apply(self, operation: Dict[str, Any]) -> Dict[str, Any]:
        return _run_async(self.apply_async(operation))

    async def apply_async(self, operation: Dict[str, Any]) -> Dict[str, Any]:
        op = operation.get("op")
        evidence = list(operation.get("dia_ids", []))
        session_index = operation.get("session_index")
        speaker = operation.get("speaker", "")
        if op == "add_memory":
            text = operation["text"]
            await cognee.add(text, dataset_name=self.dataset_name, user=self.user)
            if self.run_cognify:
                await cognee.cognify(datasets=[self.dataset_name], user=self.user)
            mem_id = f"c{len(self._memories) + 1}"
            record = {
                "id": mem_id,
                "text": text,
                "links": list(operation.get("links", [])),
                "dataset": self.dataset_name,
                "dia_ids": evidence,
                "session_index": session_index,
                "speaker": speaker,
            }
            self._memories.append(record)
            return record
        if op == "update_memory":
            target_id = operation["memory_id"]
            new_text = operation["text"]
            for record in self._memories:
                if record["id"] == target_id:
                    record["text"] = new_text
                    if evidence:
                        record["dia_ids"] = list(
                            dict.fromkeys(list(record.get("dia_ids", [])) + evidence)
                        )
                    if session_index is not None:
                        record["session_index"] = session_index
                    if speaker:
                        record["speaker"] = speaker
                    break
            await cognee.add(
                new_text, dataset_name=self.dataset_name, user=self.user
            )
            if self.run_cognify:
                await cognee.cognify(
                    datasets=[self.dataset_name], user=self.user
                )
            return {"id": target_id, "text": new_text}
        if op == "delete_memory":
            target_id = operation["memory_id"]
            self._memories = [m for m in self._memories if m["id"] != target_id]
            return {"id": target_id, "deleted": True}
        raise ValueError(f"Unsupported operation: {op}")

    # ----- backend-aware carrier candidates ----- #
    def candidate_update_targets(self, text: str, k: int = 5):
        """For Cognee, the natural update target is whichever existing
        node / triplet the new text would most plausibly *replace*.
        We surface the top-k by string overlap from the in-memory
        bookkeeping list (Cognee's KG search is async + heavy; for
        the scoped MemMark protocol we don't need the full KG hit
        list, just plausible ids the planner can rank).
        """

        from memmark.backends.base import _string_topk

        return _string_topk(self._memories, text, k)

    def candidate_link_targets(self, text: str, k: int = 5):
        from memmark.backends.base import _string_topk

        return _string_topk(self._memories, text, k)

    async def search_async(self, query: str, top_k: int = 5) -> List[Any]:
        return await cognee.search(
            query_text=query,
            query_type=SearchType.GRAPH_COMPLETION,
            datasets=[self.dataset_name],
            top_k=top_k,
            user=self.user,
        )

    def search(self, query: str, top_k: int = 5) -> List[Any]:
        return _run_async(self.search_async(query, top_k=top_k))


def _run_async(coro):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            return asyncio.ensure_future(coro)
    except RuntimeError:
        pass
    return asyncio.run(coro)
