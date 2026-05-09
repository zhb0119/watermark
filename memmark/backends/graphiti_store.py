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
            # Aligned with Graphiti's official eval
            # (graphiti/tests/evals/eval_e2e_graph_building.py:53-61):
            # name='', source_description='', source=EpisodeType.message,
            # reference_time = session date as datetime, group_id per
            # user. NO previous_episode_uuids — that's a podcast_runner
            # demo optimization, not the eval protocol.
            results = await self.graphiti.add_episode(
                name="",
                episode_body=text,
                source_description="",
                reference_time=ref_time,
                source=EpisodeType.message if EpisodeType is not None else None,
                group_id=self.group_id,
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

    # ----- watermark sampler injection ----- #
    def attach_sampler(self, sampler: Any) -> None:
        """Hot-swap Graphiti's ``llm_client`` with the watermark
        wrapper. Graphiti exposes ``self.graphiti.llm_client`` as a
        public attribute, so we replace the entire client instance.
        Every internal Graphiti LLM call (entity extraction,
        contradiction detection, edge labelling, summarization) now
        goes through keyed n-best sampling.
        """

        from memmark.llm.watermarked import make_watermarked_graphiti_client

        if self.graphiti is not None and hasattr(self.graphiti, "llm_client"):
            self.graphiti.llm_client = make_watermarked_graphiti_client(
                sampler, self.graphiti.llm_client
            )

    async def search_async(self, query: str, top_k: int = 5):
        return await self.graphiti.search(
            query=query, group_ids=[self.group_id], num_results=top_k
        )

    def search(self, query: str, top_k: int = 5):
        return _run_async(self.search_async(query, top_k=top_k))

    # ----- canonical QA context ----- #
    def qa_context(
        self,
        question: str,
        k: int = 10,
        *,
        category: Any = None,
        gold_answer: Any = None,
        llm_client: Any = None,
    ) -> Dict[str, Any]:
        """Graphiti QA pipeline.

        When ``llm_client`` and ``category`` are both provided, runs a
        cat-aware QA protocol mirroring A-mem's ``test_advanced_robust.py``
        but with Graphiti-native retrieval:

          1. ``client.search(question, group_ids, num_results=k)`` →
             top-k EntityEdges (NL ``fact`` + ``valid_at``)
          2. Render edges as context lines: ``[REL] fact (valid_at)``
          3. Cat-aware prompt (cat 2 = DATE-aware, cat 3 = exact words,
             cat 5 = adversarial A/B with gold) — verbatim from
             :func:`build_cat_aware_qa_prompt`
          4. Plain-text answer via ``llm_client``
          5. Return ``{"mode": "answer", "text": <answer>}``

        The QA-time ``llm_client`` is the driver's separate raw client
        (NOT the watermark-wrapped one inside Graphiti); QA is
        read-only and does not embed bits during verification.

        If ``llm_client`` / ``category`` are absent, falls back to the
        retrieval-only context path (``mode=context``) — render edge
        list and let the driver wrap with LoCoMo's generic QA prompt.

        Note: Graphiti has no upstream LoCoMo QA eval to copy
        verbatim. We borrow A-mem's robust cat-aware prompts so QA
        across backends is comparable on LoCoMo's category structure.
        """

        # Step 1: Graphiti-native edge retrieval
        try:
            edges = _run_async(self.search_async(question, top_k=k))
        except Exception:
            from memmark.benchmarks.locomo.qa_eval import _default_render_memory

            return {
                "mode": "context",
                "text": _default_render_memory(self.snapshot()),
            }

        if not edges:
            context_text = "(no related facts in graph)"
        else:
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
            context_text = "\n".join(lines)

        # If caller didn't request the full QA protocol, return rendered
        # context only and let the driver run its generic QA prompt.
        if llm_client is None or category is None:
            return {"mode": "context", "text": context_text}

        # Step 2/3: cat-aware prompt + plain-text answer
        from memmark.benchmarks.locomo.qa_eval import build_cat_aware_qa_prompt

        user_prompt, temperature = build_cat_aware_qa_prompt(
            category, context_text, question, gold_answer=gold_answer,
        )
        try:
            answer = llm_client.complete(
                [{"role": "user", "content": user_prompt}], temperature=temperature
            )
        except Exception:
            answer = ""
        return {"mode": "answer", "text": (answer or "").strip()}


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
