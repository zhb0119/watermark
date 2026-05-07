"""RQ1: Utility Preservation (README §10.3).

Question: does the watermark break the memory system's own utility?

Compare `+memory-watermark` vs `no_watermark` (and optionally
`signed_metadata_only`) on the LoCoMo QA accuracy + memory-write
success rate. Output is a per-baseline summary that can feed the main
Table 1.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from memmark.benchmarks.locomo.driver import LoCoMoDriverResult


@dataclass
class UtilityRow:
    label: str
    qa_accuracy: float
    qa_count: int
    memory_count: int
    write_failures: int
    bits_embedded: int
    capacity_bits_per_decision: float


@dataclass
class RQ1Report:
    rows: List[UtilityRow] = field(default_factory=list)
    deltas: Dict[str, Dict[str, float]] = field(default_factory=dict)


def run_rq1_utility(
    *,
    runs: Dict[str, LoCoMoDriverResult],
    baseline_label: str = "no_watermark",
) -> RQ1Report:
    """`runs`: {label: LoCoMoDriverResult} for each baseline you ran."""

    rows: List[UtilityRow] = []
    for label, result in runs.items():
        write_failures = sum(
            1 for ev in result.extracted_events if not ev.get("applied")
        )
        capacity = result.capacity_stats.get("bits_per_decision", 0.0)
        rows.append(
            UtilityRow(
                label=label,
                qa_accuracy=result.qa_accuracy,
                qa_count=len(result.qa_predictions),
                memory_count=len(result.memory_snapshot_final),
                write_failures=write_failures,
                bits_embedded=result.bits_embedded_total,
                capacity_bits_per_decision=capacity,
            )
        )

    deltas: Dict[str, Dict[str, float]] = {}
    base = next((r for r in rows if r.label == baseline_label), None)
    if base is not None:
        for row in rows:
            if row.label == baseline_label:
                continue
            deltas[row.label] = {
                "qa_accuracy_delta": row.qa_accuracy - base.qa_accuracy,
                "memory_count_delta": row.memory_count - base.memory_count,
                "write_failures_delta": row.write_failures - base.write_failures,
            }
    return RQ1Report(rows=rows, deltas=deltas)
