"""Claim normalizer: light normalization without changing user meaning.

Only safe transformations: whitespace/case trimming, full-width/half-width
conversion, removing leading enumerators, collapsing repeated punctuation.
Never rewrites the claim semantics.
"""

from __future__ import annotations

import re

_FULLWIDTH_MAP = str.maketrans(
    "０１２３４５６７８９ａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚ"
    "ＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ，。！？：；（）",
    "0123456789abcdefghijklmnopqrstuvwxyz"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ,.!?:;()",
)

_ENUM_PREFIX = re.compile(
    r"^\s*(?:第[一二三四五六七八九十0-9]+[、.．]|[①-⑩]|[1-9０-９]+[、.．]|"
    r"[（(][0-9一二三四五六七八九十]+[)）])\s*"
)


def normalize_fragment(text: str) -> str:
    """Normalize a fragment while preserving its meaning."""
    if not text:
        return ""
    text = text.strip().translate(_FULLWIDTH_MAP)
    text = _ENUM_PREFIX.sub("", text)
    # Drop leading contrast connectors that carry no proposition content.
    text = re.sub(r"^(?:但是|但|不过|然而|另外|此外|同时|而且|并且|再说)\s*", "", text)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"[。．]+$", "", text)
    return text.strip()


def normalize_claim(claim: str) -> str:
    """Normalize a full claim sentence."""
    normalized = normalize_fragment(claim)
    # Strip question particles and trailing punctuation when converting to
    # a proposition, but keep the original in HealthClaim.original_text.
    normalized = re.sub(r"[吗呢]$|[,，;；]$", "", normalized).strip()
    return normalized or claim.strip()
