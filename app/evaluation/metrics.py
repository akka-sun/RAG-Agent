from __future__ import annotations

from collections.abc import Sequence


def recall_at_k(expected: set[str], retrieved: Sequence[str], k: int) -> float:
    if not expected or k <= 0:
        return 0.0
    top_k = set(retrieved[:k])
    return len(expected & top_k) / len(expected)


def mrr(expected: set[str], retrieved: Sequence[str]) -> float:
    if not expected:
        return 0.0
    for index, item in enumerate(retrieved, start=1):
        if item in expected:
            return 1 / index
    return 0.0


def citation_hit_rate(expected: set[str], actual: set[str]) -> float:
    if not expected:
        return 0.0
    return len(expected & actual) / len(expected)
