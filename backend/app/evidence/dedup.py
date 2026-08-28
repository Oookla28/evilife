"""Deterministic evidence deduplication by stable key."""

from __future__ import annotations

from collections.abc import Iterable


def deduplicate(items: Iterable) -> list:
    """Drop items sharing a stable key, preserving first-seen order.

    Works on any object exposing `.stable_key` (EvidenceSource /
    EvidenceNote); falls back to a normalized title hash otherwise.
    """
    seen: set[str] = set()
    result: list = []
    for item in items:
        key = getattr(item, "stable_key", None)
        if callable(key):
            key = key()
        if key is None:
            key = f"title:{getattr(item, 'title', str(item))[:160]}".strip().lower()
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result
