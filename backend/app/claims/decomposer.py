"""ClaimDecomposer: one input sentence -> multiple traceable HealthClaims.

Rules-first, deterministic (spec §5 + §48: no mock pretending). Splitting is
conservative: strong separators (；。！？!? 编号) split; weak connectors
(而且/并且/同时/还) split only when the segment carries its own evaluative
predicate; commas and enumeration commas never split.

Every produced claim keeps `original_text` (verbatim fragment) and character
spans so nothing is ever detached from the user's input.
"""

from __future__ import annotations

import re

from .models import MAX_CLAIMS, HealthClaim
from .normalizer import normalize_claim, normalize_fragment
from .worthiness import assess, classify

# Strong separators: definitive clause boundaries.
_STRONG_SPLIT = re.compile(
    r"(?<=[\u4e00-\u9fff0-9a-zA-Z)])(?:；|;|。|！|！？|？|\?|\!|"
    r"\.{2,}|……)\s*"
)
# Weak connectors that may start a new claim when followed by a predicate.
_WEAK_CONNECTOR = re.compile(
    r"(?:而且|并且|同时|还|也|另外|此外|再说|还有)(?=[\u4e00-\u9fff])"
)
# Numbered enumerators that start a new claim.
_ENUM_SPLIT = re.compile(
    r"(?:^|(?<=[。；!?]))\s*(?:第[一二三四五六七八九十0-9]+[、.．]|"
    r"[①-⑩]|[1-9][、.．])"
)


def decompose(text: str, *, max_claims: int = MAX_CLAIMS) -> list[HealthClaim]:
    """Split user input into traceable health claims.

    Returns at most `max_claims` claims. Original text is preserved per claim.
    """
    source = (text or "").strip()
    if not source:
        return []

    fragments: list[tuple[str, int]] = []

    # 1. Split on strong separators.
    strong_parts = _split_with_spans(source, _STRONG_SPLIT)

    # 2. Within each strong part, split on enumerators.
    enumerated: list[tuple[str, int]] = []
    for part, offset in strong_parts:
        enumerated.extend(_split_with_spans(part, _ENUM_SPLIT, base=offset))

    # 3. Within each piece, split on weak connectors that introduce a new
    #    evaluative clause.
    pieces: list[tuple[str, int]] = []
    for part, offset in enumerated:
        pieces.extend(_split_weak(part, offset))

    # 4. Normalize, dedupe, assess worthiness.
    seen: set[str] = set()
    claims: list[HealthClaim] = []
    for index, (raw, offset) in enumerate(pieces, start=1):
        raw_fragment = raw.strip()
        if not raw_fragment:
            continue
        fragment = normalize_fragment(raw_fragment)
        if not fragment or fragment in seen:
            continue
        seen.add(fragment)
        judgment = assess(fragment)
        if not judgment.is_claim:
            continue
        claims.append(
            HealthClaim(
                claim_id=f"C{len(claims) + 1}",
                claim=normalize_claim(fragment),
                type=classify(fragment),  # type: ignore[arg-type]
                # original_text keeps the verbatim raw fragment so it is
                # always a substring of source_intent (traceability rule).
                original_text=raw_fragment,
                span_start=offset + raw.find(raw_fragment),
                span_end=offset + len(raw),
                source_intent=source,
            )
        )
        if len(claims) >= max_claims:
            break
    return claims


def _split_with_spans(
    text: str, pattern: re.Pattern[str], *, base: int = 0
) -> list[tuple[str, int]]:
    """Split on pattern, tracking each fragment's absolute start offset."""
    if not text:
        return []
    result: list[tuple[str, int]] = []
    cursor = 0
    for match in pattern.finditer(text):
        if match.start() > cursor:
            result.append((text[cursor : match.start()], base + cursor))
        cursor = match.end()
    tail = text[cursor:]
    if tail.strip():
        result.append((tail, base + cursor))
    return result


def _split_weak(text: str, offset: int) -> list[tuple[str, int]]:
    """Split on weak connectors, keeping the connector with its new clause."""
    if not text:
        return []
    pieces: list[tuple[str, int]] = []
    cursor = 0
    for match in _WEAK_CONNECTOR.finditer(text):
        # Only split when the segment after the connector looks evaluative.
        remainder = text[match.start() :]
        if assess(remainder).is_claim:
            if match.start() > cursor:
                pieces.append((text[cursor : match.start()], offset + cursor))
            cursor = match.start()
    if text[cursor:].strip():
        pieces.append((text[cursor:], offset + cursor))
    return pieces
