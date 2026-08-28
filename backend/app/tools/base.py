"""Evidence Tool Layer: one tool, one job.

Every evidence source is normalized into `EvidenceSource` regardless of the
provider (NCBI / Europe PMC / ClinicalTrials / guidelines / mock). Providers
implement the `EvidenceProvider` Protocol so they are interchangeable.

Principles:
- Tool errors are structured (`ToolError`), never raw exceptions to the user.
- Secrets (API keys, cookies, tokens) never appear in outputs or errors.
- A source is only user-visible after Citation Integrity verification.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal, Protocol

from pydantic import BaseModel, Field


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


class EvidenceSource(BaseModel):
    """One normalized, traceable evidence item from any provider."""

    source_id: str = Field(min_length=1, description="provider 内唯一 ID")
    source_database: str = Field(min_length=1, description="pubmed/europe_pmc/clinicaltrials/guidelines/mock")
    title: str = Field(min_length=1)
    authors: list[str] = Field(default_factory=list)
    year: int | None = None
    publication_date: str | None = None
    source_type: str = Field(
        min_length=1,
        description="guideline / systematic_review / meta_analysis / rct / observational / review / other",
    )
    journal_or_organization: str | None = None
    pmid: str | None = None
    doi: str | None = None
    nct_id: str | None = None
    url: str = ""
    abstract: str = ""
    population: str | None = None
    intervention: str | None = None
    comparator: str | None = None
    outcome: str | None = None
    retrieved_at: str = Field(default_factory=utc_now)

    def stable_key(self) -> str:
        """Dedup key: prefer DOI, then PMID/NCT, then normalized title."""
        if self.doi:
            return f"doi:{self.doi.lower()}"
        if self.pmid:
            return f"pmid:{self.pmid}"
        if self.nct_id:
            return f"nct:{self.nct_id}"
        return f"title:{self.title.strip().lower()[:160]}"


SearchDirection = Literal["support", "against", "neutral"]
SourceType = Literal[
    "guideline",
    "systematic_review",
    "meta_analysis",
    "rct",
    "observational",
    "review",
    "cohort",
    "other",
]


class SearchFilters(BaseModel):
    """Metadata filters applied by the provider before returning results."""

    source_types: list[SourceType] = Field(default_factory=list)
    date_from: str | None = None
    date_to: str | None = None
    max_results: int = Field(default=8, ge=1, le=20)
    population: str | None = None
    intervention: str | None = None
    outcome: str | None = None


ToolErrorCode = Literal[
    "provider_unavailable",
    "rate_limited",
    "timeout",
    "invalid_query",
    "source_not_found",
    "no_results",
]


class ToolError(RuntimeError):
    """Structured tool failure. Never exposes secrets or PHI."""

    def __init__(
        self,
        code: ToolErrorCode,
        message: str,
        *,
        provider: str | None = None,
        retryable: bool = False,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.provider = provider
        self.retryable = retryable

    def to_dict(self) -> dict:
        return {
            "error": self.code,
            "provider": self.provider,
            "message": self.message,
            "retryable": self.retryable,
        }


class EvidenceProvider(Protocol):
    """Interchangeable evidence search backend."""

    name: str

    async def search(
        self,
        query: str,
        *,
        direction: SearchDirection = "neutral",
        filters: SearchFilters | None = None,
    ) -> list[EvidenceSource]:
        """Search one provider; raise ToolError on structured failure."""
        ...

    async def fetch(self, source_id: str) -> EvidenceSource | None:
        """Fetch a single source's metadata; None when not found."""
        ...


def provider_health_note(provider: EvidenceProvider | None) -> str:
    """User-facing degradation note (spec §36)."""
    if provider is None:
        return "实时医学检索未配置，已使用缓存与本地语料证据。"
    return f"{provider.name} 暂时不可用，已使用缓存证据。"
