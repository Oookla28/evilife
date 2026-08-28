from __future__ import annotations

import asyncio
import html
import os
import re
import time
from dataclasses import dataclass, field
from typing import ClassVar, Literal

import httpx
from pydantic import BaseModel, Field

from .evidence.corpus import AuthoritativeCorpus
from .evidence.admission import (
    assess_evidence,
    boundary_direction,
    calibrate_direction,
    is_absolute_claim,
)
from .evidence.rrf import reciprocal_rank_fusion
from .evidence.query_generator import QueryGenerator
from .schemas import EvidencePacket, VerdictEvidenceItem


class RetrievedEvidence(BaseModel):
    source_id: str
    title: str
    url: str
    source_type: str
    organization: str | None = None
    year: int | None = None
    snippet: str
    reliability_score: float = Field(ge=0, le=1)
    channel: Literal["curated_database", "live_medical_search"]


class EvidenceBlend(BaseModel):
    reliable_weight: float = Field(ge=0, le=1)
    general_weight: float = Field(ge=0, le=1)
    target_reliable_weight: float = Field(ge=0, le=1)
    policy_reason: str
    search_query: str
    live_search_status: Literal["disabled", "ok", "empty", "failed"]
    fusion_method: Literal["single_channel", "rrf"] = "single_channel"
    trusted_sources: list[RetrievedEvidence] = Field(default_factory=list)
    supporting_evidence: list[VerdictEvidenceItem] = Field(default_factory=list)
    opposing_evidence: list[VerdictEvidenceItem] = Field(default_factory=list)

    def prompt_context(self) -> str:
        if not self.trusted_sources:
            return "当前没有检索到可追溯来源。不得生成具体统计数字、论文或机构引用。"
        blocks = []
        for source in self.trusted_sources:
            blocks.append(
                f"[{source.source_id}] {source.title}\n"
                f"来源类型：{source.source_type}；机构/期刊：{source.organization or '未标明'}；"
                f"年份：{source.year or '未标明'}；可靠度：{source.reliability_score:.2f}\n"
                f"内容：{source.snippet}\nURL：{source.url}"
            )
        return "\n\n".join(blocks)

    def metadata(self) -> dict:
        return {
            "reliable_weight": self.reliable_weight,
            "general_weight": self.general_weight,
            "target_reliable_weight": self.target_reliable_weight,
            "policy_reason": self.policy_reason,
            "live_search_status": self.live_search_status,
            "fusion_method": self.fusion_method,
            "search_query": self.search_query,
            "trusted_source_count": len(self.trusted_sources),
            "support_evidence_count": len(self.supporting_evidence),
            "opposing_evidence_count": len(self.opposing_evidence),
        }


class EuropePMCSearch:
    """Live biomedical-literature search using Europe PMC's public REST API.

    A single topic is searched twice with independent queries: a FOR query
    aimed at systematic reviews / meta-analyses / guidelines, and an AGAINST
    query aimed at null results, limitations and conflicting evidence. The
    two directions are never mixed before the ranker runs.
    """

    def __init__(
        self,
        *,
        base_url: str = "https://www.ebi.ac.uk/europepmc/webservices/rest",
        max_results: int = 4,
        timeout_seconds: float = 12,
        cache_ttl_seconds: float = 600.0,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.max_results = max(1, min(max_results, 8))
        self.timeout_seconds = timeout_seconds
        self._client: httpx.AsyncClient | None = None
        # Query -> (cached_at, results); TTL avoids hammering Europe PMC on
        # repeated turns with the same topic query.
        self._cache: dict[str, tuple[float, list[RetrievedEvidence]]] = {}
        self._cache_ttl_seconds = cache_ttl_seconds

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=self.timeout_seconds)
        return self._client

    def clear_cache(self) -> None:
        self._cache.clear()

    def cache_size(self) -> int:
        return len(self._cache)

    @classmethod
    def from_env(cls) -> "EuropePMCSearch | None":
        enabled = os.getenv("EVILIFE_LIVE_SEARCH_ENABLED", "false").lower() == "true"
        if not enabled:
            return None
        return cls(
            base_url=os.getenv(
                "EVILIFE_EUROPE_PMC_BASE_URL",
                "https://www.ebi.ac.uk/europepmc/webservices/rest",
            ),
            max_results=int(os.getenv("EVILIFE_LIVE_SEARCH_MAX_RESULTS", "4")),
        )

    async def search(self, query: str) -> list[RetrievedEvidence]:
        """Single-direction live search (kept for deterministic tests)."""
        return await self._run(query)

    async def search_directional(
        self,
        query: str,
        direction: Literal["support", "against"],
    ) -> list[RetrievedEvidence]:
        return await self._run(query)

    async def _run(self, query: str) -> list[RetrievedEvidence]:
        now = time.monotonic()
        cached = self._cache.get(query)
        if cached is not None and now - cached[0] < self._cache_ttl_seconds:
            return cached[1]

        params = {
            "query": query,
            "format": "json",
            "resultType": "core",
            "pageSize": str(self.max_results),
        }
        client = await self._get_client()
        response = await client.get(f"{self.base_url}/search", params=params)
        response.raise_for_status()
        results = response.json().get("resultList", {}).get("result", [])
        sources: list[RetrievedEvidence] = []
        for index, item in enumerate(results[: self.max_results], start=1):
            title = self._plain_text(item.get("title", ""))
            abstract = self._plain_text(item.get("abstractText", ""))
            if not title or not abstract:
                continue
            pmcid = item.get("pmcid")
            pmid = item.get("pmid")
            identifier = pmcid or pmid or item.get("id")
            if not identifier:
                continue
            source_prefix = "PMC" if pmcid else "MED"
            pub_types = item.get("pubTypeList", {}).get("pubType", [])
            if isinstance(pub_types, str):
                pub_types = [pub_types]
            source_type = ", ".join(pub_types[:2]) or "同行评议医学文献"
            sources.append(
                RetrievedEvidence(
                    source_id=f"W{index}",
                    title=title,
                    url=f"https://europepmc.org/article/{source_prefix}/{identifier}",
                    source_type=source_type,
                    organization=item.get("journalTitle") or "Europe PMC",
                    year=self._year(item.get("pubYear")),
                    # Truncate the snippet: full 1800-char abstracts roughly
                    # double prompt tokens for marginal retrieval quality.
                    snippet=abstract[:900],
                    reliability_score=self._reliability(pub_types),
                    channel="live_medical_search",
                )
            )
        self._cache[query] = (now, sources)
        return sources

    @staticmethod
    def _plain_text(value: object) -> str:
        if not isinstance(value, str):
            return ""
        return " ".join(
            html.unescape(re.sub(r"<[^>]+>", " ", value)).split()
        )

    @staticmethod
    def _year(value: object) -> int | None:
        try:
            year = int(str(value))
        except (TypeError, ValueError):
            return None
        return year if 1800 <= year <= 2100 else None

    @staticmethod
    def _reliability(pub_types: list[str]) -> float:
        normalized = " ".join(pub_types).lower()
        if "systematic review" in normalized or "meta-analysis" in normalized:
            return 0.95
        if "guideline" in normalized or "practice guideline" in normalized:
            return 0.94
        if "randomized controlled trial" in normalized:
            return 0.90
        if "review" in normalized:
            return 0.84
        return 0.76


@dataclass(slots=True)
class EvidenceBlendService:
    live_search: EuropePMCSearch | None = None
    corpus: AuthoritativeCorpus | None = None
    # Instance-level blend cache: per-request instances stay isolated so tests
    # and concurrent sessions never poison each other's retrieval results.
    _blend_cache: dict[str, tuple[float, EvidenceBlend]] = field(
        default_factory=dict, repr=False, compare=False
    )
    _blend_cache_ttl_seconds: float = field(
        default=300.0, repr=False, compare=False
    )

    TOPIC_QUERIES: ClassVar[dict[str, str]] = {
        "sodium_and_hypertension": (
            'TITLE_ABS:"sodium intake" AND TITLE_ABS:(hypertension OR "blood pressure") '
            'AND (PUB_TYPE:"systematic review" OR PUB_TYPE:"meta-analysis" '
            'OR PUB_TYPE:"practice guideline")'
        ),
        "mediterranean_diet_and_cardiovascular_risk": (
            'TITLE_ABS:"Mediterranean diet" AND TITLE_ABS:(cardiovascular OR stroke) '
            'AND (PUB_TYPE:"systematic review" OR PUB_TYPE:"meta-analysis" '
            'OR PUB_TYPE:"randomized controlled trial")'
        ),
    }
    # Independent FOR and AGAINST queries per golden topic. The AGAINST query
    # deliberately targets null results, limitations and conflicts.
    TOPIC_DIRECTION_QUERIES: ClassVar[dict[str, dict[str, str]]] = {
        "sodium_and_hypertension": {
            "support": (
                'TITLE_ABS:"sodium intake" AND TITLE_ABS:(hypertension OR "blood pressure") '
                'AND (PUB_TYPE:"systematic review" OR PUB_TYPE:"meta-analysis" '
                'OR PUB_TYPE:"practice guideline")'
            ),
            "against": (
                'TITLE_ABS:"sodium intake" AND TITLE_ABS:(hypertension OR "blood pressure") '
                'AND TITLE_ABS:(limitations OR "no benefit" OR "no effect" OR '
                '"no association" OR conflicting OR "not superior" OR "no mortality benefit")'
            ),
        },
        "mediterranean_diet_and_cardiovascular_risk": {
            "support": (
                'TITLE_ABS:"Mediterranean diet" AND TITLE_ABS:(cardiovascular OR stroke) '
                'AND (PUB_TYPE:"systematic review" OR PUB_TYPE:"meta-analysis" '
                'OR PUB_TYPE:"randomized controlled trial")'
            ),
            "against": (
                'TITLE_ABS:"Mediterranean diet" AND TITLE_ABS:(cardiovascular OR stroke) '
                'AND TITLE_ABS:(limitations OR "no benefit" OR "no effect" OR '
                '"no association" OR "not superior" OR conflicting OR "no mortality benefit")'
            ),
        },
    }
    HIGH_RISK_MARKERS: ClassVar[tuple[str, ...]] = (
        "药物",
        "剂量",
        "停药",
        "孕妇",
        "哺乳",
        "儿童",
        "急救",
        "胸痛",
        "呼吸困难",
        "过敏",
        "自杀",
    )

    def __post_init__(self) -> None:
        if self.corpus is None:
            self.corpus = AuthoritativeCorpus.from_env()

    async def build(
        self,
        *,
        question: str,
        search_query: str,
        mode: str,
        packet: EvidencePacket | None = None,
    ) -> EvidenceBlend:
        """Compatibility entrypoint: single-query bidirectional build."""
        topic = packet.topic if packet is not None else None
        return await self.build_bidirectional(
            question=question,
            support_query=search_query,
            boundary_query=search_query,
            mode=mode,
            packet=packet,
            topic=topic,
        )

    async def build_bidirectional(
        self,
        *,
        question: str,
        support_query: str,
        boundary_query: str,
        mode: str,
        packet: EvidencePacket | None = None,
        topic: str | None = None,
    ) -> EvidenceBlend:
        """Build FOR and AGAINST evidence groups through independent channels.

        FOR   = curated packet supports + corpus support claims + live support
        AGAINST = curated packet boundaries + corpus boundary claims + live against

        Each direction is fused separately (RRF), then combined into one blend
        so the Evidence Mixer and the Verdict can read both sides.
        """
        direction_queries = self.TOPIC_DIRECTION_QUERIES.get(topic or "")
        support_live_query = (
            direction_queries["support"] if direction_queries else support_query
        )
        against_live_query = (
            direction_queries["against"] if direction_queries else boundary_query
        )

        # Same-question repeat turns skip retrieval and re-run the mixer.
        cached = self._blend_cache_get(question, topic, mode)
        if cached is not None:
            return cached

        curated_support = self._packet_directional(packet, "support", question)
        curated_against = self._packet_directional(packet, "against", question)

        corpus_support: list[VerdictEvidenceItem] = []
        corpus_against: list[VerdictEvidenceItem] = []
        if self.corpus is not None:
            # The corpus is a Chinese consumer-health store: search with the
            # original question text, never the English PMC query string.
            literature_query = (
                question
                if topic
                else QueryGenerator.english_query(question) or question
            )
            corpus_hits = [
                *self.corpus.search_claims(question, topic=topic, limit=4),
                *self.corpus.search_literature(
                    literature_query, topic=topic, limit=2 if topic else 4
                ),
            ]
            for hit in corpus_hits:
                decision = assess_evidence(
                    question, title=hit.title, text=hit.finding
                )
                if not decision.relevant:
                    continue
                original_direction = hit.direction
                if hit.evidence_id.startswith("L"):
                    # PubMed rows carry only a coarse regex direction. The
                    # claim-aware admission decision is the authoritative
                    # direction for this concrete question.
                    original_direction = decision.direction
                calibrated_direction = calibrate_direction(
                    question,
                    f"{hit.title} {hit.finding}",
                    original_direction,
                )
                hit = hit.model_copy(update={"direction": calibrated_direction})
                if hit.direction == "context" and original_direction == "context":
                    direct_direction = boundary_direction(
                        question, hit.finding, hit.title
                    )
                    hit = hit.model_copy(update={"direction": direct_direction})
                elif is_absolute_claim(question) and hit.direction == "support":
                    hit = hit.model_copy(update={"direction": "context"})
                elif is_absolute_claim(question) and hit.direction == "mixed":
                    hit = hit.model_copy(update={"direction": "against"})
                if hit.direction == "support":
                    corpus_support.append(hit)
                elif hit.direction == "against":
                    corpus_against.append(hit)
                elif hit.direction == "mixed":
                    corpus_support.append(hit)
                    corpus_against.append(hit)

        live_support: list[VerdictEvidenceItem] = []
        live_against: list[VerdictEvidenceItem] = []
        status: Literal["disabled", "ok", "empty", "failed"] = "disabled"
        if self.live_search is not None:
            support_result, against_result = await self._live_both(
                support_live_query, against_live_query
            )
            live_support = self._tag_direction(
                support_result, "support", question
            )
            live_against = self._tag_direction(
                against_result, "against", question
            )
            total_live = len(live_support) + len(live_against)
            status = "ok" if total_live else "empty"

        supporting = self._fuse(
            [curated_support, corpus_support, live_support], limit=8
        )
        opposing = self._fuse(
            [curated_against, corpus_against, live_against], limit=8
        )

        trusted = self._fuse(
            [
                supporting,
                opposing,
            ],
            limit=8,
        )

        target = self._target_weight(question, mode)
        realized, reason = self._realized_weight(
            target=target,
            has_packet=packet is not None,
            live_ok=status == "ok",
            trusted=trusted,
        )

        blend = EvidenceBlend(
            reliable_weight=round(realized, 2),
            general_weight=round(1 - realized, 2),
            target_reliable_weight=round(target, 2),
            policy_reason=reason,
            search_query=support_query,
            live_search_status=status,
            fusion_method="rrf" if len(trusted) > 1 else "single_channel",
            trusted_sources=[
                self._to_retrieved(item)
                for item in trusted[:8]
            ],
            supporting_evidence=supporting,
            opposing_evidence=opposing,
        )
        self._blend_cache_set(question, topic, mode, blend)
        return blend

    # ------------------------------------------------------------------
    # blend-level cache (question + topic + mode, TTL)
    # ------------------------------------------------------------------

    def _blend_cache_key(self, question: str, topic: str | None, mode: str) -> str:
        normalized = "".join((question or "").split()).lower()
        return f"{normalized}|{topic or 'none'}|{mode}"

    def _blend_cache_get(
        self, question: str, topic: str | None, mode: str
    ) -> EvidenceBlend | None:
        key = self._blend_cache_key(question, topic, mode)
        entry = self._blend_cache.get(key)
        if entry is None:
            return None
        cached_at, blend = entry
        if time.monotonic() - cached_at >= self._blend_cache_ttl_seconds:
            self._blend_cache.pop(key, None)
            return None
        return blend

    def _blend_cache_set(
        self, question: str, topic: str | None, mode: str, blend: EvidenceBlend
    ) -> None:
        key = self._blend_cache_key(question, topic, mode)
        self._blend_cache[key] = (time.monotonic(), blend)
        if len(self._blend_cache) > 128:
            # Evict the oldest entries.
            for old_key in sorted(
                self._blend_cache, key=lambda k: self._blend_cache[k][0]
            )[:64]:
                self._blend_cache.pop(old_key, None)

    def clear_blend_cache(self) -> None:
        self._blend_cache.clear()

    # ------------------------------------------------------------------
    # helpers
    # ------------------------------------------------------------------

    async def _live_both(
        self,
        support_query: str,
        against_query: str,
    ) -> tuple[list[RetrievedEvidence], list[RetrievedEvidence]]:
        """Run independent live searches in parallel (FOR + AGAINST)."""
        if hasattr(self.live_search, "search_directional"):
            support_result, against_result = await asyncio.gather(
                self.live_search.search_directional(support_query, "support"),
                self.live_search.search_directional(against_query, "against"),
            )
            return support_result, against_result
        try:
            support_result, against_result = await asyncio.gather(
                self.live_search.search(support_query),
                self.live_search.search(against_query),
            )
        except (httpx.HTTPError, KeyError, TypeError, ValueError):
            return [], []
        return support_result, against_result

    def _fuse(
        self,
        channels: list[list[VerdictEvidenceItem]],
        *,
        limit: int,
    ) -> list[VerdictEvidenceItem]:
        non_empty = [channel for channel in channels if channel]
        if not non_empty:
            return []
        if len(non_empty) == 1:
            return non_empty[0][:limit]
        return reciprocal_rank_fusion(
            non_empty,
            key=lambda item: item.evidence_id,
            limit=limit,
        )

    @staticmethod
    def _tag_direction(
        sources: list[RetrievedEvidence],
        direction: Literal["support", "against"],
        question: str,
    ) -> list[VerdictEvidenceItem]:
        suffix = "S" if direction == "support" else "A"
        admitted: list[VerdictEvidenceItem] = []
        accepted = {direction, "mixed"}
        for source in sources:
            decision = assess_evidence(
                question, title=source.title, text=source.snippet
            )
            if not decision.relevant or decision.direction not in accepted:
                continue
            admitted.append(VerdictEvidenceItem(
                evidence_id=f"{source.source_id}-{suffix}",
                source_id=source.source_id,
                title=source.title,
                year=source.year,
                source_type=source.source_type,
                organization=source.organization,
                direction=decision.direction,  # type: ignore[arg-type]
                finding=source.snippet,
                url=source.url,
                channel="live_medical_search",
                reliability_score=source.reliability_score,
            ))
        return admitted

    @staticmethod
    def _packet_directional(
        packet: EvidencePacket | None,
        direction: Literal["support", "against"],
        question: str,
    ) -> list[VerdictEvidenceItem]:
        if packet is None:
            return []
        items: list[VerdictEvidenceItem] = []
        for item in packet.evidence_items:
            claims = (
                item.supports if direction == "support" else item.does_not_support
            )
            for index, claim in enumerate(claims, start=1):
                evidence_id = (
                    f"{item.evidence_id}-{'S' if direction == 'support' else 'A'}{index}"
                    if len(claims) > 1
                    else f"{item.evidence_id}-{'S' if direction == 'support' else 'A'}"
                )
                items.append(
                    VerdictEvidenceItem(
                        evidence_id=evidence_id,
                        source_id=item.source_id,
                        title=item.title,
                        year=item.year,
                        source_type=item.source_type,
                        organization=item.organization,
                        # Packet does_not_support entries describe population,
                        # extrapolation and treatment boundaries. They remain
                        # visible in the opposing panel but are not direct
                        # counterevidence unless a source reports a null result.
                        direction=(
                            "context"
                            if direction == "support" and is_absolute_claim(question)
                            else "support"
                            if direction == "support"
                            else boundary_direction(question, claim, item.title)
                        ),  # type: ignore[arg-type]
                        finding=claim,
                        url=str(item.url),
                        channel="curated_database",
                        reliability_score=0.97,
                    )
                )
        return items

    @staticmethod
    def _to_retrieved(item: VerdictEvidenceItem) -> RetrievedEvidence:
        return RetrievedEvidence(
            source_id=item.source_id,
            title=item.title,
            url=item.url,
            source_type=item.source_type,
            organization=item.organization,
            year=item.year,
            snippet=item.finding[:900],
            reliability_score=item.reliability_score or 0.8,
            channel=item.channel or "curated_database",
        )

    @classmethod
    def _target_weight(cls, question: str, mode: str) -> float:
        compact = "".join(question.split())
        if any(marker in compact for marker in cls.HIGH_RISK_MARKERS):
            return 0.88
        if mode in {"deep", "evaluation"}:
            return 0.82
        return 0.78

    @staticmethod
    def _realized_weight(
        *,
        target: float,
        has_packet: bool,
        live_ok: bool,
        trusted: list[VerdictEvidenceItem],
    ) -> tuple[float, str]:
        if has_packet and live_ok:
            return max(target, 0.88), "本地核验包与实时医学文献同时可用。"
        if has_packet:
            return max(target, 0.84), "使用本地核验包；实时医学检索未提供额外结果。"
        if len(trusted) >= 3:
            return target, "实时医学检索返回至少 3 条可追溯来源。"
        if trusted:
            return min(target, 0.65), "可追溯来源较少，降低可靠证据权重并标记降级。"
        return 0.0, "没有可追溯来源，仅允许输出保守的一般信息。"


def citation_payloads(blend: EvidenceBlend) -> list[dict[str, str | int | float | None]]:
    return [
        {
            "evidence_id": f"E{index}",
            "source_id": source.source_id,
            "title": source.title,
            "year": source.year,
            "source_type": source.source_type,
            "organization": source.organization,
            "url": source.url,
            "reliability_score": source.reliability_score,
            "channel": source.channel,
        }
        for index, source in enumerate(blend.trusted_sources, start=1)
    ]
