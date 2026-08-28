from __future__ import annotations

import re
from typing import Literal

from pydantic import AnyUrl, BaseModel, ConfigDict, Field

from ..schemas import EvidenceItem, EvidencePacket


IssueCode = Literal[
    "unknown_evidence_id",
    "source_id_mismatch",
    "packet_external_url",
    "citation_url_mismatch",
    "unsupported_exact_number",
]

_NUMBER_PATTERN = re.compile(
    r"(?<![\w.])[-+]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?(?![\w.])"
)


class CitationReference(BaseModel):
    """Source metadata emitted alongside one E1-En reference."""

    model_config = ConfigDict(extra="forbid")

    evidence_id: str = Field(pattern=r"^E[1-9]\d*$")
    source_id: str = Field(min_length=1)
    url: AnyUrl


class CitedClaim(BaseModel):
    """A user-facing claim and every citation used to ground it."""

    model_config = ConfigDict(extra="forbid")

    text: str = Field(min_length=1)
    citations: list[CitationReference] = Field(min_length=1)


class VerificationIssue(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: IssueCode
    message: str
    citation_index: int | None = None
    value: str | None = None


class CitationVerificationResult(BaseModel):
    model_config = ConfigDict(extra="forbid")

    valid: bool
    issues: list[VerificationIssue] = Field(default_factory=list)


class CitationVerificationError(ValueError):
    """Raised when an answer tries to leave its bounded Evidence Packet."""

    def __init__(self, result: CitationVerificationResult) -> None:
        self.result = result
        summary = "; ".join(issue.message for issue in result.issues)
        super().__init__(summary)


class CitationVerifier:
    """Pure, deterministic checks for packet-bounded citations and numbers."""

    def __init__(self, packet: EvidencePacket) -> None:
        self.packet = packet
        self._items_by_evidence_id = {
            item.evidence_id: item for item in packet.evidence_items
        }
        self._packet_urls = {str(item.url) for item in packet.evidence_items}

    def verify(self, claim: CitedClaim) -> CitationVerificationResult:
        issues: list[VerificationIssue] = []
        resolved_items: list[EvidenceItem] = []

        for index, citation in enumerate(claim.citations):
            item = self._items_by_evidence_id.get(citation.evidence_id)
            if item is None:
                issues.append(
                    VerificationIssue(
                        code="unknown_evidence_id",
                        message=f"{citation.evidence_id} does not exist in {self.packet.packet_id}",
                        citation_index=index,
                        value=citation.evidence_id,
                    )
                )
                continue

            citation_url = str(citation.url)
            if citation.source_id != item.source_id:
                issues.append(
                    VerificationIssue(
                        code="source_id_mismatch",
                        message=(
                            f"{citation.evidence_id} maps to {item.source_id}, "
                            f"not {citation.source_id}"
                        ),
                        citation_index=index,
                        value=citation.source_id,
                    )
                )

            if citation_url not in self._packet_urls:
                issues.append(
                    VerificationIssue(
                        code="packet_external_url",
                        message=f"URL is not present in {self.packet.packet_id}: {citation_url}",
                        citation_index=index,
                        value=citation_url,
                    )
                )
            elif citation_url != str(item.url):
                issues.append(
                    VerificationIssue(
                        code="citation_url_mismatch",
                        message=f"{citation.evidence_id} does not map to URL {citation_url}",
                        citation_index=index,
                        value=citation_url,
                    )
                )

            if citation.source_id == item.source_id and citation_url == str(item.url):
                resolved_items.append(item)

        supported_numbers = self._supported_numbers(resolved_items)
        for number in sorted(self._numbers_in(claim.text)):
            if number not in supported_numbers:
                issues.append(
                    VerificationIssue(
                        code="unsupported_exact_number",
                        message=f"Exact number is not supported by the cited evidence: {number}",
                        value=number,
                    )
                )

        return CitationVerificationResult(valid=not issues, issues=issues)

    def verify_or_raise(self, claim: CitedClaim) -> CitationVerificationResult:
        result = self.verify(claim)
        if not result.valid:
            raise CitationVerificationError(result)
        return result

    @classmethod
    def _supported_numbers(cls, items: list[EvidenceItem]) -> set[str]:
        numbers: set[str] = set()
        for item in items:
            claim_supporting_text = [
                str(item.year) if item.year is not None else "",
                item.population,
                item.finding,
                item.limitations,
                item.intervention or "",
                item.outcome or "",
                *item.supports,
                *item.does_not_support,
            ]
            numbers.update(cls._numbers_in(" ".join(claim_supporting_text)))
        return numbers

    @staticmethod
    def _numbers_in(text: str) -> set[str]:
        return {match.group(0).replace(",", "") for match in _NUMBER_PATTERN.finditer(text)}
