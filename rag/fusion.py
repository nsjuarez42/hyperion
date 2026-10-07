"""Combining rankings and comparing vectors."""

from rag.config import RRF_K


def dot(left: list[float], right: list[float]) -> float:
    return sum(a * b for a, b in zip(left, right))


def reciprocal_rank_fusion(rankings: list[list[int]]) -> list[int]:
    """Merge several rankings of chunk indexes into one.

    Each chunk scores 1 / (RRF_K + rank) in every ranking it appears in, so a
    chunk near the top of both keyword and embedding search wins, and neither
    method's raw scores need to be on the same scale.
    """
    scores: dict[int, float] = {}
    for ranking in rankings:
        for rank, index in enumerate(ranking):
            scores[index] = scores.get(index, 0.0) + 1.0 / (RRF_K + rank + 1)
    return sorted(scores, key=lambda index: scores[index], reverse=True)
