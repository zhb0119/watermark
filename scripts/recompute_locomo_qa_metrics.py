from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "locomo"))

from memmark.benchmarks.locomo.qa_eval import bleu1, rouge_l, score_one
from task_eval.evaluation import eval_question_answering


def _mean(values: list[float]) -> float:
    return sum(values) / len(values) if values else 0.0


def _load_qa_predictions(path: Path, baseline: str | None) -> tuple[str, list[dict[str, Any]]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    details = data.get("details", {})
    if baseline is None:
        if len(details) != 1:
            raise SystemExit(f"--baseline required; found baselines={list(details)}")
        baseline = next(iter(details))
    if baseline not in details:
        raise SystemExit(f"baseline {baseline!r} not found; available={list(details)}")
    return baseline, list(details[baseline].get("qa_predictions", []))


def _official_rows(qa_predictions: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    for q in qa_predictions:
        rows.append(
            {
                "question": q.get("question", ""),
                "answer": q.get("answer_gold", ""),
                "prediction": q.get("answer_pred", ""),
                "category": int(q.get("category", 0)),
                "evidence": q.get("evidence", []),
            }
        )
    return rows


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    overall = {
        "n": len(rows),
        "f1": _mean([r["f1"] for r in rows]),
        "bleu1": _mean([r["bleu1"] for r in rows]),
        "rougeL": _mean([r["rougeL"] for r in rows]),
        "acc_f1_ge_0_5": _mean([1.0 if r["f1"] >= 0.5 else 0.0 for r in rows]),
    }
    grouped: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for r in rows:
        grouped[int(r["category"])].append(r)
    by_category = {}
    for cat, items in sorted(grouped.items()):
        by_category[str(cat)] = {
            "n": len(items),
            "f1": _mean([r["f1"] for r in items]),
            "bleu1": _mean([r["bleu1"] for r in items]),
            "rougeL": _mean([r["rougeL"] for r in items]),
            "acc_f1_ge_0_5": _mean([1.0 if r["f1"] >= 0.5 else 0.0 for r in items]),
        }
    return {"overall": overall, "by_category": by_category}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("json_path")
    parser.add_argument("--baseline", default=None)
    parser.add_argument("--out", default=None)
    args = parser.parse_args()

    baseline, qa_predictions = _load_qa_predictions(Path(args.json_path), args.baseline)

    memmark_rows = []
    for q in qa_predictions:
        pred = q.get("answer_pred", "")
        gold = q.get("answer_gold", "")
        cat = int(q.get("category", 0))
        f1 = score_one(pred, gold, cat)
        memmark_rows.append(
            {
                "index": q.get("index"),
                "category": cat,
                "answer_gold": gold,
                "answer_pred": pred,
                "f1": f1,
                "bleu1": bleu1(pred, gold),
                "rougeL": rouge_l(pred, gold),
            }
        )

    official_scores, _, official_recall = eval_question_answering(
        _official_rows(qa_predictions), eval_key="prediction"
    )
    official_rows = []
    for q, official_f1 in zip(qa_predictions, official_scores):
        pred = q.get("answer_pred", "")
        gold = q.get("answer_gold", "")
        official_rows.append(
            {
                "index": q.get("index"),
                "category": int(q.get("category", 0)),
                "answer_gold": gold,
                "answer_pred": pred,
                "f1": float(official_f1),
                "bleu1": bleu1(pred, gold),
                "rougeL": rouge_l(pred, gold),
            }
        )

    out = {
        "source": str(Path(args.json_path)),
        "baseline": baseline,
        "memmark_recomputed": _summarize(memmark_rows),
        "official_locomo_recomputed": {
            **_summarize(official_rows),
            "recall_mean": _mean([float(x) for x in official_recall]),
        },
        "diff": {
            "f1_overall": _summarize(memmark_rows)["overall"]["f1"]
            - _summarize(official_rows)["overall"]["f1"],
            "acc_overall": _summarize(memmark_rows)["overall"]["acc_f1_ge_0_5"]
            - _summarize(official_rows)["overall"]["acc_f1_ge_0_5"],
        },
    }

    text = json.dumps(out, indent=2, ensure_ascii=False)
    print(text)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")


if __name__ == "__main__":
    main()
