"""EvidenceNote: structured, machine-checkable summary of one evidence item.

The note is the unit the generator consumes — never a full abstract. The
supports / does_not_support / limitations fields are extracted from the real
literature text by deterministic rules (negation markers, conclusion
sentences, limitation clauses); nothing here is model-generated.

Extraction is deliberately conservative: if a sentence is ambiguous, it goes
to `source_excerpt` only and is not claimed as support or opposition.
"""

from __future__ import annotations

import re
from typing import Literal

from pydantic import BaseModel, Field

from ..tools.base import EvidenceSource

NoteDirection = Literal["support", "against", "mixed", "context"]


class EvidenceNote(BaseModel):
    evidence_id: str = Field(min_length=1)
    source_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    year: int | None = None
    study_type: str = "other"
    population: str | None = None
    sample_size: int | None = None
    intervention: str | None = None
    comparator: str | None = None
    outcome: str | None = None
    finding: str = Field(default="")
    supports: list[str] = Field(default_factory=list)
    does_not_support: list[str] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
    applicability: str | None = None
    source_excerpt: str = Field(default="")
    url: str = ""
    retrieved_at: str = ""
    direction: NoteDirection = "context"

    @property
    def stable_key(self) -> str:
        return self.source_id or self.title.strip().lower()[:160]


# Negation markers: the evidence argues AGAINST the claim.
_NEGATION = re.compile(
    r"\b(no benefit|no effect|no difference|not superior|not better|"
    r"no association|no significant|did not reduce|did not lower|"
    r"failed to|no improvement|no mortality benefit|adverse|harmful|"
    r"no evidence of benefit)\b",
    re.IGNORECASE,
)
# Positive effect markers: the evidence SUPPORTS the claim.
_SUPPORT = re.compile(
    r"\b(reduced|lowered|decreased|improved|associated with lower|"
    r"beneficial|significant reduction|significant decrease|"
    r"significant improvement|effective|reduced risk)\b",
    re.IGNORECASE,
)
# Limitation clauses.
_LIMITATION = re.compile(
    r"\b(however|but|although|limitation|limitations|caveat|caveats|"
    r"not generalizable|small sample|short duration|observational|"
    r"confounding|cannot be generalized)\b",
    re.IGNORECASE,
)
_SAMPLE_SIZE = re.compile(
    r"\b(?:n\s*=\s*(\d{2,})|(\d{2,})\s*(?:participants|patients|subjects)|"
    r"enrolled\s+(\d{2,})|sample\s+of\s+(\d{2,}))",
    re.IGNORECASE,
)


def _sentences(text: str) -> list[str]:
    return [
        sentence.strip()
        for sentence in re.split(r"(?<=[.!?。！？])\s+", text)
        if len(sentence.strip()) >= 20
    ]


def build_evidence_note(
    source: EvidenceSource,
    *,
    direction_hint: NoteDirection | None = None,
    max_support: int = 3,
    max_limitations: int = 3,
) -> EvidenceNote:
    """Build an EvidenceNote from a provider EvidenceSource (deterministic)."""
    abstract = source.abstract or ""
    sentences = _sentences(abstract)

    supports: list[str] = []
    opposes: list[str] = []
    limitations: list[str] = []

    for sentence in sentences:
        negated = bool(_NEGATION.search(sentence))
        positive = bool(_SUPPORT.search(sentence))
        if negated and positive:
            # Mixed sentence — keep as excerpt, claim nothing.
            continue
        if negated and len(opposes) < max_support:
            opposes.append(sentence[:220])
            continue
        if positive and len(supports) < max_support:
            supports.append(sentence[:220])
            continue
        if _LIMITATION.search(sentence) and len(limitations) < max_limitations:
            limitations.append(sentence[:220])

    # Retrieval intent is not evidence semantics.  A hit from an AGAINST query
    # is only against when its own text contains a direct null-result signal.
    if supports and opposes:
        direction = "mixed"
    elif opposes:
        direction = "against"
    elif supports:
        direction = "support"
    else:
        direction = "context"

    finding = _finding(sentences, abstract)
    sample_size = _sample_size(abstract)

    return EvidenceNote(
        evidence_id=f"N-{source.source_id}",
        source_id=source.source_id,
        title=source.title,
        year=source.year,
        study_type=source.source_type,
        population=source.population,
        sample_size=sample_size,
        intervention=source.intervention,
        comparator=source.comparator,
        outcome=source.outcome,
        finding=finding,
        supports=supports,
        does_not_support=opposes,
        limitations=limitations,
        source_excerpt=abstract[:1200],
        url=source.url,
        retrieved_at=source.retrieved_at,
        direction=direction,
    )


def _finding(sentences: list[str], abstract: str) -> str:
    """Best-effort conclusion sentence (deterministic)."""
    for sentence in sentences:
        if re.search(r"\b(conclusion|in summary|we conclude|in conclusion)\b", sentence, re.I):
            return sentence[:260]
    if sentences:
        return sentences[-1][:260]
    return abstract[:260]


def _sample_size(abstract: str) -> int | None:
    match = _SAMPLE_SIZE.search(abstract)
    if not match:
        return None
    for group in match.groups():
        if group:
            try:
                return int(group)
            except ValueError:
                return None
    return None
