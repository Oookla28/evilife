"""Europe PMC provider (EvidenceProvider Protocol implementation).

Full-metadata live search over the Europe PMC REST API. Unlike the lean
`EvidenceBlendService.EuropePMCSearch` (which only keeps rank + snippet),
this provider extracts PMID/DOI/authors/journal/publication types so the
Evidence Note and Citation Integrity layers can work with real identifiers.
"""

from __future__ import annotations

import html
import json
import re
import time
from typing import Literal

import httpx

from .base import (
    EvidenceProvider,
    EvidenceSource,
    SearchDirection,
    SearchFilters,
    ToolError,
    utc_now,
)


class EuropePMCProvider(EvidenceProvider):
    """Live biomedical literature search via Europe PMC REST API."""

    name = "europe_pmc"

    def __init__(
        self,
        *,
        base_url: str = "https://www.ebi.ac.uk/europepmc/webservices/rest",
        timeout_seconds: float = 12,
        cache_ttl_seconds: float = 600.0,
        max_results: int = 8,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.max_results = max_results
        self._client: httpx.AsyncClient | None = None
        self._cache: dict[str, tuple[float, list[EvidenceSource]]] = {}
        self._cache_ttl_seconds = cache_ttl_seconds

    # ------------------------------------------------------------------
    # EvidenceProvider protocol
    # ------------------------------------------------------------------

    async def search(
        self,
        query: str,
        *,
        direction: SearchDirection = "neutral",
        filters: SearchFilters | None = None,
    ) -> list[EvidenceSource]:
        if not query.strip():
            raise ToolError("invalid_query", "empty search query", provider=self.name)
        effective = filters or SearchFilters()
        cache_key = f"{direction}|{query.strip().lower()}|{effective.max_results}"
        cached = self._cache.get(cache_key)
        now = time.monotonic()
        if cached is not None and now - cached[0] < self._cache_ttl_seconds:
            return cached[1]

        compiled = self._compile_query(query, direction, effective)
        try:
            payload = await self._get_search(compiled, effective.max_results)
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429:
                raise ToolError(
                    "rate_limited", "Europe PMC 请求过于频繁，请稍后重试。",
                    provider=self.name, retryable=True,
                ) from exc
            raise ToolError(
                "provider_unavailable", "Europe PMC 暂时不可用。",
                provider=self.name, retryable=True,
            ) from exc
        except httpx.TimeoutException as exc:
            raise ToolError(
                "timeout", "Europe PMC 请求超时。",
                provider=self.name, retryable=True,
            ) from exc
        except httpx.HTTPError as exc:
            raise ToolError(
                "provider_unavailable", "Europe PMC 请求失败。",
                provider=self.name, retryable=True,
            ) from exc

        sources = [self._to_source(item) for item in payload[: effective.max_results]]
        sources = [source for source in sources if source is not None]
        self._cache[cache_key] = (now, sources)
        return sources

    async def fetch(self, source_id: str) -> EvidenceSource | None:
        try:
            payload = await self._get_search(f'EXT_ID:{source_id} AND SRC:MED', 1)
        except ToolError:
            return None
        items = [self._to_source(item) for item in payload]
        return next((item for item in items if item is not None), None)

    # ------------------------------------------------------------------
    # internals
    # ------------------------------------------------------------------

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self.timeout_seconds)
        return self._client

    async def _get_search(self, query: str, page_size: int) -> list[dict]:
        client = await self._get_client()
        response = await client.get(
            f"{self.base_url}/search",
            params={
                "query": query,
                "format": "json",
                "resultType": "core",
                "pageSize": str(page_size),
            },
        )
        response.raise_for_status()
        return response.json().get("resultList", {}).get("result", [])

    @classmethod
    def _compile_query(
        cls,
        query: str,
        direction: SearchDirection,
        filters: SearchFilters,
    ) -> str:
        """Compose an Europe PMC query with direction + metadata filters."""
        parts = [query.strip()]
        if filters.source_types:
            type_clauses = " OR ".join(
                f'PUB_TYPE:"{t.replace("_", " ")}"' for t in filters.source_types
            )
            parts.append(f"({type_clauses})")
        if filters.date_from:
            parts.append(f'(PUB_YEAR:["{filters.date_from}" TO "*"])')
        if filters.date_to:
            parts.append(f'(PUB_YEAR:["*" TO "{filters.date_to}"])')
        if direction == "against":
            # null results / limitations / conflicts
            parts.append(
                '(TITLE_ABS:("no benefit" OR "no effect" OR "no difference" '
                'OR "not superior" OR conflicting OR "no association" OR adverse))'
            )
        return " AND ".join(parts)

    @staticmethod
    def _to_source(item: dict) -> EvidenceSource | None:
        title = EuropePMCProvider._plain(item.get("title", ""))
        abstract = EuropePMCProvider._plain(item.get("abstractText", ""))
        if not title:
            return None
        pmcid = item.get("pmcid")
        pmid = item.get("pmid")
        source_id = pmcid or pmid or item.get("id")
        if not source_id:
            return None
        pub_types = item.get("pubTypeList", {}).get("pubType", [])
        if isinstance(pub_types, str):
            pub_types = [pub_types]
        return EvidenceSource(
            source_id=str(source_id),
            source_database="europe_pmc",
            title=title,
            authors=[
                EuropePMCProvider._plain(a)
                for a in (item.get("authorList", {}) or {}).get("author", [])
            ],
            year=EuropePMCProvider._year(item.get("pubYear")),
            publication_date=item.get("firstPublicationDate") or item.get("pubYear"),
            source_type=EuropePMCProvider._source_type(pub_types),
            journal_or_organization=item.get("journalTitle"),
            pmid=str(pmid) if pmid else None,
            doi=item.get("doi"),
            url=(
                f"https://europepmc.org/article/{'PMC' if pmcid else 'MED'}/{source_id}"
            ),
            abstract=abstract[:1800],
            retrieved_at=utc_now(),
        )

    @staticmethod
    def _plain(value: object) -> str:
        if not isinstance(value, str):
            return ""
        return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", value)).split())

    @staticmethod
    def _year(value: object) -> int | None:
        try:
            year = int(str(value))
        except (TypeError, ValueError):
            return None
        return year if 1800 <= year <= 2100 else None

    @staticmethod
    def _source_type(pub_types: list[str]) -> str:
        joined = " ".join(pub_types).lower()
        if "systematic review" in joined or "meta-analysis" in joined:
            return "meta_analysis" if "meta-analysis" in joined else "systematic_review"
        if "practice guideline" in joined or "guideline" in joined:
            return "guideline"
        if "randomized controlled trial" in joined or "randomized clinical trial" in joined:
            return "rct"
        if "observational" in joined or "cohort" in joined:
            return "observational"
        if "review" in joined:
            return "review"
        return "other"
