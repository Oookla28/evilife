"""Small, dependency-free Reciprocal Rank Fusion adapter.

The rank-only fusion approach follows MedRAG (Public Domain Notice) and
medgroundAI (MIT). It intentionally does not import either project's corpus,
models, storage layer, or network stack.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import TypeVar


T = TypeVar("T")
RRF_K = 60


def reciprocal_rank_fusion(
    ranked_lists: Sequence[Sequence[T]],
    *,
    key: Callable[[T], str],
    limit: int,
    rank_constant: int = RRF_K,
) -> list[T]:
    """Fuse ranked channels without comparing their incompatible raw scores."""
    if limit <= 0:
        return []

    scores: dict[str, float] = {}
    first_seen: dict[str, int] = {}
    values: dict[str, T] = {}
    seen_order = 0
    for ranked in ranked_lists:
        channel_seen: set[str] = set()
        for rank, item in enumerate(ranked, start=1):
            item_key = key(item)
            if not item_key or item_key in channel_seen:
                continue
            channel_seen.add(item_key)
            if item_key not in values:
                values[item_key] = item
                first_seen[item_key] = seen_order
                seen_order += 1
            scores[item_key] = scores.get(item_key, 0.0) + 1.0 / (
                rank_constant + rank
            )

    ordered = sorted(
        values,
        key=lambda item_key: (-scores[item_key], first_seen[item_key]),
    )
    return [values[item_key] for item_key in ordered[:limit]]
