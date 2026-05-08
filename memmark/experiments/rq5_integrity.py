"""RQ5: Memory Integrity (README §10.7).

Reports whether the watermark introduces wrong-target updates, broken
links, duplicates, or contradictions. Some of these need ground-truth
labels; for LoCoMo we use simple heuristics over the final memory
snapshot:

  * duplication_rate     — fraction of memory records with text
                            appearing >1 times in the snapshot
  * contradiction_rate   — placeholder (LoCoMo doesn't ship clean
                            contradiction labels; reserved for the
                            §10.7 appendix using LongMemEval's
                            knowledge-update splits).
  * stale_memory_count   — number of memories with no recent dia_id
                            in their context
  * update_target_accuracy — when carrier=update_target was chosen,
                            whether the picked target was the same
                            entity as the source event (heuristic via
                            string overlap).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, List

from memmark.benchmarks.locomo.driver import LoCoMoDriverResult


@dataclass
class RQ5Report:
    duplication_rate: float = 0.0
    duplicate_count: int = 0
    update_target_accuracy: float = 0.0
    update_target_total: int = 0
    update_target_correct: int = 0
    link_target_total: int = 0
    contradiction_rate: float = 0.0  # placeholder
    overall_records: int = 0
    by_carrier_counts: Dict[str, int] = field(default_factory=dict)


def run_rq5_integrity(driver_result: LoCoMoDriverResult) -> RQ5Report:
    snapshot = driver_result.memory_snapshot_final or []
    overall = len(snapshot)
    report = RQ5Report(overall_records=overall)
    if overall == 0:
        return report

    # Duplication: same `text` appearing more than once
    counts = Counter((r.get("text") or "").strip() for r in snapshot)
    duplicate_count = sum(c for c in counts.values() if c > 1) - sum(
        1 for c in counts.values() if c > 1
    )  # extra occurrences beyond the first
    report.duplicate_count = duplicate_count
    report.duplication_rate = duplicate_count / overall

    # Carrier breakdown of decisions
    by_carrier: Counter = Counter(a.tau for a in driver_result.audits)
    report.by_carrier_counts = dict(by_carrier)

    # Update-target accuracy heuristic: did the chosen update target's
    # original text share keywords with the new event?
    update_total = 0
    update_correct = 0
    for decision, audit in zip(driver_result.decisions, driver_result.audits):
        if audit.tau != "update_target":
            continue
        update_total += 1
        selected = next(
            (c for c in decision.candidates if c.candidate_id == audit.selected_candidate_id),
            None,
        )
        if selected is None:
            continue
        target_text = selected.payload.get("memory_id", "") or ""
        new_text = selected.payload.get("new_text", "") or ""
        if _shares_keywords(target_text, new_text):
            update_correct += 1
    report.update_target_total = update_total
    report.update_target_correct = update_correct
    report.update_target_accuracy = (
        update_correct / update_total if update_total else 0.0
    )
    report.link_target_total = sum(1 for a in driver_result.audits if a.tau == "link_target")
    return report


def _shares_keywords(a: str, b: str, *, min_share: int = 1) -> bool:
    a_words = {w for w in a.lower().split() if len(w) > 3}
    b_words = {w for w in b.lower().split() if len(w) > 3}
    return len(a_words & b_words) >= min_share
