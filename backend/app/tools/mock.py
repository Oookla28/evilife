"""Deterministic mock evidence provider for tests and offline demo.

Honest by construction: sources carry `mock://` URLs and `source_database
= "mock"`, so a mock result can never be mistaken for a real citation in
production output.
"""

from __future__ import annotations

from .base import (
    EvidenceProvider,
    EvidenceSource,
    SearchDirection,
    SearchFilters,
    ToolError,
    utc_now,
)


class MockEvidenceProvider(EvidenceProvider):
    """Deterministic provider returning scripted sources."""

    name = "mock"

    def __init__(self, sources: list[EvidenceSource] | None = None) -> None:
        self.sources = sources or [
            EvidenceSource(
                source_id="MOCK-SR-001",
                source_database="mock",
                title="Mock systematic review",
                year=2024,
                source_type="systematic_review",
                journal_or_organization="Mock Journal",
                url="mock://sr-001",
                abstract="Mock abstract: no real evidence.",
            )
        ]
        self.last_query: str | None = None
        self.last_direction: SearchDirection | None = None

    async def search(
        self,
        query: str,
        *,
        direction: SearchDirection = "neutral",
        filters: SearchFilters | None = None,
    ) -> list[EvidenceSource]:
        self.last_query = query
        self.last_direction = direction
        if not query.strip():
            raise ToolError("invalid_query", "empty query", provider=self.name)
        limit = (filters or SearchFilters()).max_results
        return [source.model_copy() for source in self.sources[:limit]]

    async def fetch(self, source_id: str) -> EvidenceSource | None:
        return next(
            (source for source in self.sources if source.source_id == source_id),
            None,
        )
