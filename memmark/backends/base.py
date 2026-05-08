from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List


class MemoryBackendAdapter(ABC):
    """Adapter contract per README §4.2.3.

    Required:
      * snapshot()   — list of memory records (dict-shaped)
      * apply(op)    — apply an evolve operation, return the affected
                       memory record. Must propagate any extra keys
                       like `dia_ids`, `session_index`, `speaker` on
                       the returned record so RQ5 evidence checks
                       work.

    Optional (for backend-aware carriers; planner falls back to LLM
    paraphrase if these aren't implemented):

      * candidate_update_targets(text, k)
      * candidate_link_targets(text, k)
      * paraphrase_candidates(text, k)   — only LLM-side; planner
                                            handles default
    """

    @abstractmethod
    def snapshot(self) -> List[Dict[str, Any]]:
        raise NotImplementedError

    @abstractmethod
    def apply(self, operation: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError

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
