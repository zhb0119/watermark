"""LoCoMo-official QA prompt + F1 metric.

Mirrors `locomo/task_eval/{evaluation.py, gpt_utils.py}`:

  * QA_PROMPT  / QA_PROMPT_CAT_5  — original templates
  * f1_score, f1, normalize_answer — original metric (Porter-stemmed
    token-level F1 with category 1 multi-answer split, category 5
    "no information available" check, exact match for category 2/3/4).

Using these for paper main-table numbers makes our results directly
comparable to the LoCoMo paper Table 4 + downstream replications.
"""

from __future__ import annotations

import json
import re
import string
import unicodedata
from collections import Counter
from typing import Any, List, Optional


# ----- official LoCoMo QA prompts ------------------------------------ #

QA_PROMPT = (
    "\nBased on the above context, write an answer in the form of a "
    "short phrase for the following question. Answer with exact words "
    "from the context whenever possible.\n\n"
    "Question: {q} Short answer:\n"
)

QA_PROMPT_CAT_5 = (
    "\nBased on the above context, answer the following question.\n\n"
    "Question: {q} Short answer:\n"
)

CONV_START_PROMPT = (
    "Below is a conversation between two people: {a} and {b}. The "
    "conversation takes place over multiple days and the date of each "
    "conversation is written at the beginning of the conversation.\n\n"
)


# ----- normalization + F1 (LoCoMo evaluation.py) --------------------- #

try:
    from nltk.stem import PorterStemmer  # type: ignore

    _STEMMER = PorterStemmer()
    _stem = _STEMMER.stem
except ModuleNotFoundError:  # pragma: no cover - nltk optional
    def _stem(w: str) -> str:  # type: ignore
        return w


def _normalize(text: str) -> str:
    return unicodedata.normalize("NFD", text)


def normalize_answer(s: str) -> str:
    s = (s or "").replace(",", "")
    # remove articles
    s = re.sub(r"\b(a|an|the|and)\b", " ", s)
    # strip punctuation
    s = "".join(ch for ch in s if ch not in set(string.punctuation))
    # lower + collapse whitespace
    return " ".join(s.lower().split())


def f1_score(prediction: str, ground_truth: str) -> float:
    pred_tokens = [_stem(w) for w in normalize_answer(prediction).split()]
    gold_tokens = [_stem(w) for w in normalize_answer(ground_truth).split()]
    if not pred_tokens or not gold_tokens:
        return 0.0
    common = Counter(pred_tokens) & Counter(gold_tokens)
    num_same = sum(common.values())
    if num_same == 0:
        return 0.0
    precision = num_same / len(pred_tokens)
    recall = num_same / len(gold_tokens)
    return (2 * precision * recall) / (precision + recall)


def f1_multi(prediction: str, ground_truth: str) -> float:
    """Category 1: ground_truth may have ',' separated alternates."""

    preds = [p.strip() for p in (prediction or "").split(",")]
    golds = [g.strip() for g in (ground_truth or "").split(",")]
    if not preds or not golds:
        return 0.0
    return _mean(
        max(f1_score(p, g) for p in preds) for g in golds
    )


def _mean(seq) -> float:
    seq = list(seq)
    return sum(seq) / len(seq) if seq else 0.0


def score_one(prediction: str, gold: str, category: int) -> float:
    """LoCoMo per-category metric (mirrors eval_question_answering)."""

    if category == 3:
        # multi-hop: gold may have ';' separated alternates → take first
        gold = (gold or "").split(";")[0].strip()
        return f1_score(prediction, gold)
    if category in (2, 4):
        return f1_score(prediction, gold)
    if category == 1:
        return f1_multi(prediction, gold)
    if category == 5:
        # adversarial / abstention
        text = (prediction or "").lower()
        if "no information available" in text or "not mentioned" in text \
                or "i don't know" in text:
            return 1.0
        return 0.0
    # unknown → fallback to plain F1
    return f1_score(prediction, gold)


# ----- responder + judge wired to MemoryWatermarker driver ----------- #


def make_locomo_qa_responder(
    llm_client,
    *,
    memory_render: Optional[Any] = None,
    max_chars: int = 12000,
):
    """Returns a `qa_responder(question, snapshot) -> str` closure.

    The responder builds a CONV_START_PROMPT-styled context out of the
    memory snapshot (one record per line) plus LoCoMo's QA_PROMPT or
    QA_PROMPT_CAT_5 (for adversarial questions, category 5).
    """

    render = memory_render or _default_render_memory

    def responder(question, snapshot) -> str:
        ctx = render(snapshot)[:max_chars]
        if question.category == 5:
            qa_template = QA_PROMPT_CAT_5
        else:
            qa_template = QA_PROMPT
        user_prompt = ctx + qa_template.format(q=question.question)
        messages = [
            {
                "role": "system",
                "content": (
                    "You are a careful question-answering assistant. "
                    "Use ONLY the provided memory context. If the answer "
                    "is not in the context, reply: 'No information available'."
                ),
            },
            {"role": "user", "content": user_prompt},
        ]
        try:
            return (llm_client.complete(messages, temperature=0.0) or "").strip()
        except Exception:
            return ""

    return responder


def make_locomo_qa_judge():
    """Returns a `judge(question, predicted) -> bool` using LoCoMo F1.

    A leaf is "correct" if its category-aware F1 ≥ 0.5 (matching
    LoCoMo's table: they report F1 directly; using 0.5 as a binary
    cutoff is our reduction so the rest of the pipeline can still
    aggregate accuracy. Drivers that want the raw F1 should instead
    use `score_one` directly.)
    """

    def judge(question, predicted) -> bool:
        return score_one(predicted, question.answer, question.category) >= 0.5

    return judge


def _default_render_memory(snapshot: List[dict]) -> str:
    """Render memory snapshot into LoCoMo-style natural-language context."""

    lines: List[str] = []
    for rec in snapshot:
        text = rec.get("text") or rec.get("content") or ""
        if not text:
            continue
        meta = []
        if rec.get("dia_ids"):
            meta.append(f"evidence={rec['dia_ids']}")
        if rec.get("session_index") is not None:
            meta.append(f"session={rec['session_index']}")
        if meta:
            lines.append(f"- {text}  ({'; '.join(meta)})")
        else:
            lines.append(f"- {text}")
    return (
        "Below are durable long-term memory entries extracted from a "
        "multi-session conversation:\n\n" + "\n".join(lines)
    )
