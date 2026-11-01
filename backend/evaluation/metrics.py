"""Ranking and classification metrics used by the offline evaluation.

Grades follow the dataset rubric: 0 (not relevant) to 3 (strong fit). A candidate
counts as relevant from ``RELEVANT_GRADE`` up.
"""

from __future__ import annotations

import math
from typing import Sequence

RELEVANT_GRADE = 2


def dcg(grades: Sequence[int]) -> float:
    """Discounted cumulative gain of grades listed in ranked order.

    Gain is ``2**grade - 1`` (a strong fit counts much more than a weak one) and
    position ``i`` (0-based) is discounted by ``log2(i + 2)``.
    """
    return sum((2**grade - 1) / math.log2(i + 2) for i, grade in enumerate(grades))


def ndcg_at_k(ranked_grades: Sequence[int], k: int) -> float:
    """NDCG@k: DCG of the top ``k`` divided by the best DCG possible with the same grades.

    1.0 means the top ``k`` is ordered perfectly. Returns 0.0 when no candidate has a
    grade above 0, since there is nothing to rank.
    """
    ideal = dcg(sorted(ranked_grades, reverse=True)[:k])
    return dcg(ranked_grades[:k]) / ideal if ideal else 0.0


def precision_at_k(ranked_grades: Sequence[int], k: int, relevant: int = RELEVANT_GRADE) -> float:
    """Share of the top ``k`` whose grade is at least ``relevant`` (missing slots count as misses)."""
    return sum(grade >= relevant for grade in ranked_grades[:k]) / k


def f1_score(predicted: Sequence[bool], actual: Sequence[bool]) -> float:
    """Harmonic mean of precision and recall for a yes/no decision such as "shortlisted"."""
    true_positives = sum(p and a for p, a in zip(predicted, actual, strict=True))
    if true_positives == 0:
        return 0.0
    precision = true_positives / sum(predicted)
    recall = true_positives / sum(actual)
    return 2 * precision * recall / (precision + recall)
