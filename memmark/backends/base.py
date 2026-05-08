from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List


class MemoryBackendAdapter(ABC):
    """Adapter contract per README §4.2.3.

    Required:
      * snapshot()   — list of memory records (dict-shaped)
      * apply(op)    — apply an evolve operation, return the affected
                       memory record. Must propagate any extra keys
                       like `dia_ids`, `session_index`, `speaker`,
                       `session_date_time` on the returned record so
                       RQ5 evidence checks work.

    Optional class attribute:
      * preferred_ingestion_mode  — "turn" / "session" / "fact"
        Driver dispatches on this to feed the backend in the way its
        upstream paper / repo uses for LoCoMo / LongMemEval:
          - "turn":    one memory event per LoCoMo turn  (Graphiti)
          - "session": one memory event per LoCoMo session text  (Cognee)
          - "fact":    LoCoMo-style per-session LLM fact extraction
                       with dia_id evidence   (A-MEM, Mem0)

    Optional carrier-aware retrieval (planner falls back to keyword
    overlap if these aren't implemented):

      * candidate_update_targets(text, k)
      * candidate_link_targets(text, k)
    """

    # Driver fallback when a backend doesn't override.
    preferred_ingestion_mode: str = "turn"

    @abstractmethod
    def snapshot(self) -> List[Dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def apply(self, operation: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

    # ------------- canonical QA context ------------------ #
    def qa_context(self, question: str, k: int = 10) -> Dict[str, Any]:
        """Return per-question retrieval context for the QA prompt.

        Returns ``{"mode": "context"|"answer", "text": str}``:

          * ``"context"`` — pre-rendered memory text. The driver wraps
            it in LoCoMo's QA_PROMPT and asks our own LLM.
          * ``"answer"``  — the system already produced the answer
            (e.g. Cognee GRAPH_COMPLETION). The driver returns it
            verbatim, skipping the QA prompt.

        Default: render the entire snapshot via session-marker
        grouping (matching LoCoMo's full-conversation Base/Observation
        rendering). Backends with a native canonical retrieve API
        (A-MEM ``find_related_memories``, Cognee ``search``, Graphiti
        ``search``) override this so QA sees memory in the shape the
        upstream system intends.
        """

        from memmark.benchmarks.locomo.qa_eval import _default_render_memory

        return {"mode": "context", "text": _default_render_memory(self.snapshot())}

    # ------------- optional carrier helpers -------------- #
    def candidate_update_targets(
        self, text: str, k: int = 5
    ) -> List[Dict[str, Any]]:
        """Existing memory ids that are *plausible update targets* for
        this incoming text. Default: top-k by string similarity over
        snapshot(). Real backends should override with a vector / KG
        query that reflects the backend's actual evolve freedom.
        """

        return _string_topk(self.snapshot(), text, k)

    def candidate_link_targets(
        self, text: str, k: int = 5
    ) -> List[Dict[str, Any]]:
        """Existing memory ids that are *plausible link targets*.
        Default same as update; backends with native graph / cluster
        retrieval should override.
        """

        return _string_topk(self.snapshot(), text, k)


def _string_topk(snapshot: List[Dict[str, Any]], query: str, k: int):
    """Cheap baseline: keyword-overlap top-k over snapshot.

    Used by JsonMemoryStore + as a defensive fallback for backends
    that didn't override the candidate_* methods.
    """

    qwords = {w for w in (query or "").lower().split() if len(w) > 2}
    scored = []
    for record in snapshot:
        text = (record.get("text") or "").lower()
        if not text:
            continue
        rwords = {w for w in text.split() if len(w) > 2}
        score = len(qwords & rwords)
        if score == 0:
            continue
        scored.append((score, record))
    scored.sort(key=lambda kv: -kv[0])
    return [r for _, r in scored[:k]]
