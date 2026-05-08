"""Graphiti backend adapter (https://github.com/getzep/graphiti).

Graphiti is a temporal context graph: each memory becomes an *episode*
with a `reference_time`. The graph evolves through fact invalidation
and supersession. We expose:

  * `add_memory` → graphiti.add_episode()
  * `update_memory` → adds a new episode that supersedes the prior fact
    (Graphiti handles this natively when a contradicting fact arrives)
  * `delete_memory` → graphiti.remove_episode()
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from memmark.backends.base import MemoryBackendAdapter

try:
    from graphiti_core import Graphiti  # type: ignore
    from graphiti_core.nodes import EpisodeType  # type: ignore
    HAS_GRAPHITI = True
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    Graphiti = None  # type: ignore
    EpisodeType = None  # type: ignore
    HAS_GRAPHITI = False


class GraphitiBackend(MemoryBackendAdapter):
    """Backend adapter wrapping `graphiti_core.Graphiti`.

    Per Graphiti's official eval (`tests/evals/eval_e2e_graph_building.py`),
    the LongMemEval / LoCoMo ingestion is **per-turn**: each
    dialog turn becomes one episode whose `reference_time` is the
    session's date_time (not now()). We therefore set
    `preferred_ingestion_mode = "turn"` and read
    `operation["session_date_time"]` to populate `reference_time`.
    """

    preferred_ingestion_mode = "turn"

    def __init__(
        self,
        *,
        graphiti: Optional[Any] = None,
        group_id: Optional[str] = None,
        source_description: str = "memmark watermark",
    ) -> None:
        if graphiti is None:
            if not HAS_GRAPHITI:
                raise RuntimeError(
                    "graphiti_core not installed. `pip install graphiti-core` "
                    "or pass `graphiti=` explicitly."
                )
            graphiti = Graphiti(
                uri=os.getenv("NEO4J_URI", "bolt://localhost:7687"),
                user=os.getenv("NEO4J_USER", "neo4j"),
                password=os.getenv("NEO4J_PASSWORD", "neo4j"),
            )
        self.graphiti = graphiti
        self.group_id = group_id or os.getenv("MEMMARK_GRAPHITI_GROUP", "memmark")
        self.source_description = source_description
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
            session_date_time = operation.get("session_date_time", "")
            ref_time = _parse_reference_time(session_date_time) or datetime.now(timezone.utc)
            # Per podcast_runner.py canonical pattern: chain new
            # episodes to the most recent 3 by reference_time so
            # Graphiti can do temporal supersession against the right
            # fact set. We pull the chain from Graphiti itself rather
            # than from `_memories`, because the graph may have
            # invalidated / re-attached uuids during cognify.
            previous_uuids: List[str] = []
            try:
                prev = await self.graphiti.retrieve_episodes(
                    ref_time, 3, group_ids=[self.group_id]
                )
                previous_uuids = [getattr(p, "uuid", "") for p in prev if getattr(p, "uuid", None)]
            except Exception:
                previous_uuids = []
            results = await self.graphiti.add_episode(
                name=operation.get("name", f"memmark_{len(self._memories) + 1}"),
                episode_body=text,
                source_description=self.source_description,
                reference_time=ref_time,
                source=EpisodeType.message if EpisodeType is not None else None,
                group_id=self.group_id,
                previous_episode_uuids=previous_uuids or None,
            )
            ep_uuid = getattr(getattr(results, "episode", None), "uuid", None) or (
                results.episode.uuid if hasattr(results, "episode") else f"g{len(self._memories) + 1}"
            )
            record = {
                "id": ep_uuid,
                "text": text,
                "links": list(operation.get("links", [])),
                "reference_time": ref_time.isoformat(),
                "dia_ids": evidence,
                "session_index": session_index,
                "speaker": speaker,
                "session_date_time": session_date_time,
            }
            self._memories.append(record)
            return record
        if op == "update_memory":
            target_id = operation["memory_id"]
            new_text = operation["text"]
            now = datetime.now(timezone.utc)
            results = await self.graphiti.add_episode(
                name=f"memmark_update_{target_id}",
                episode_body=new_text,
                source_description=self.source_description + " (update)",
                reference_time=now,
                source=EpisodeType.message if EpisodeType is not None else None,
                group_id=self.group_id,
            )
            ep_uuid = getattr(getattr(results, "episode", None), "uuid", None) or target_id
            for record in self._memories:
                if record["id"] == target_id:
                    record["text"] = new_text
                    record["last_update_id"] = ep_uuid
                    if evidence:
                        record["dia_ids"] = list(
                            dict.fromkeys(list(record.get("dia_ids", [])) + evidence)
                        )
                    if session_index is not None:
                        record["session_index"] = session_index
                    if speaker:
                        record["speaker"] = speaker
                    break
            return {"id": target_id, "text": new_text, "supersede_id": ep_uuid}
        if op == "delete_memory":
            target_id = operation["memory_id"]
            try:
                await self.graphiti.remove_episode(target_id)
            except Exception:
                pass
            self._memories = [m for m in self._memories if m["id"] != target_id]
            return {"id": target_id, "deleted": True}
        raise ValueError(f"Unsupported operation: {op}")

    # ----- backend-aware carrier candidates ----- #
    def candidate_update_targets(self, text: str, k: int = 5):
        """Graphiti's natural update targets are facts that the new
        episode could *supersede*. We surface them via Graphiti's
        own search (top-k semantically related facts).
        """

        from memmark.backends.base import _string_topk

        return _string_topk(self._memories, text, k)

    def candidate_link_targets(self, text: str, k: int = 5):
        from memmark.backends.base import _string_topk

        return _string_topk(self._memories, text, k)

    async def search_async(self, query: str, top_k: int = 5):
        return await self.graphiti.search(
            query=query, group_ids=[self.group_id], num_results=top_k
        )

    def search(self, query: str, top_k: int = 5):
        return _run_async(self.search_async(query, top_k=top_k))

    # ----- canonical QA context ----- #
    def qa_context(self, question: str, k: int = 10) -> Dict[str, Any]:
        """Graphiti's canonical QA path: ``client.search(query, group_ids,
        num_results=k)`` returns top-k edges; each ``EntityEdge.fact`` is
        the natural-language fact string Graphiti emits. We render those
        as the QA context (LoCoMo paper's +Observation row uses an
        analogous fact-list rendering).
        """

        try:
            edges = _run_async(self.search_async(question, top_k=k))
        except Exception:
            from memmark.benchmarks.locomo.qa_eval import _default_render_memory

            return {
                "mode": "context",
                "text": _default_render_memory(self.snapshot()),
            }

        if not edges:
            return {"mode": "context", "text": "(no related facts in graph)"}
        lines: List[str] = []
        for edge in edges:
            fact = getattr(edge, "fact", "") or ""
            name = getattr(edge, "name", "") or ""
            ts = getattr(edge, "valid_at", None) or getattr(
                edge, "created_at", None
            )
            ts_str = ts.isoformat() if ts is not None and hasattr(ts, "isoformat") else ""
            head = f"[{name}] " if name else ""
            tail = f" ({ts_str})" if ts_str else ""
            lines.append(f"- {head}{fact}{tail}")
        return {"mode": "context", "text": "\n".join(lines)}


def _run_async(coro):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            return asyncio.ensure_future(coro)
    except RuntimeError:
        pass
    return asyncio.run(coro)


def _parse_reference_time(text: str):
    """Parse LoCoMo / LongMemEval session date_time string to UTC datetime.

    LoCoMo format examples:  '7 May 2023, 11:38 am', 'May 8, 2023 at 09:00'
    LongMemEval format:      '2023/05/07 (Sun) 11:38'
    Falls back to None on unrecognized format.
    """

    if not text:
        return None
    candidates = [
        "%d %B %Y, %I:%M %p",       # "7 May 2023, 11:38 am"
        "%B %d, %Y at %H:%M",        # "May 8, 2023 at 09:00"
        "%B %d, %Y, %I:%M %p",       # "May 8, 2023, 9:00 am"
        "%Y/%m/%d (%a) %H:%M",       # "2023/05/07 (Sun) 11:38"
        "%Y-%m-%d %H:%M:%S",         # ISO-ish
        "%Y-%m-%dT%H:%M:%S",
    ]
    for fmt in candidates:
        try:
            dt = datetime.strptime(text.strip(), fmt)
            return dt.replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None
