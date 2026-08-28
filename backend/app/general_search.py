"""Bounded public web search for non-medical general questions."""

from __future__ import annotations

import asyncio
import html
import os
import re
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from urllib.parse import urlparse

import httpx
from pydantic import BaseModel, Field


class GeneralSearchResult(BaseModel):
    title: str = Field(min_length=1, max_length=300)
    url: str = Field(min_length=1, max_length=2000)
    snippet: str = Field(default="", max_length=700)
    source: str = Field(min_length=1, max_length=120)
    published_at: str | None = Field(default=None, max_length=120)


class GeneralSearchError(RuntimeError):
    pass


@dataclass(slots=True)
class GeneralWebSearch:
    """Blend bounded web and news RSS results for general questions."""

    base_url: str = "https://www.bing.com/search"
    news_base_url: str | None = "https://news.google.com/rss/search"
    timeout_seconds: float = 12
    max_results: int = 5
    cache_ttl_seconds: float = 300
    transport: httpx.AsyncBaseTransport | None = None
    _cache: dict[str, tuple[float, list[GeneralSearchResult]]] = field(
        init=False,
        default_factory=dict,
        repr=False,
    )

    @classmethod
    def from_env(cls) -> "GeneralWebSearch | None":
        if os.getenv("EVILIFE_GENERAL_SEARCH_ENABLED", "true").lower() != "true":
            return None
        return cls(
            base_url=os.getenv(
                "EVILIFE_GENERAL_SEARCH_BASE_URL",
                "https://www.bing.com/search",
            ).strip(),
            news_base_url=(
                os.getenv(
                    "EVILIFE_GENERAL_NEWS_SEARCH_BASE_URL",
                    "https://news.google.com/rss/search",
                ).strip()
                or None
            ),
            timeout_seconds=float(
                os.getenv("EVILIFE_GENERAL_SEARCH_TIMEOUT_SECONDS", "12")
            ),
            max_results=max(
                1,
                min(8, int(os.getenv("EVILIFE_GENERAL_SEARCH_MAX_RESULTS", "5"))),
            ),
        )

    async def search(self, query: str) -> list[GeneralSearchResult]:
        normalized = " ".join(query.split())[:500]
        if not normalized:
            raise GeneralSearchError("搜索问题不能为空")
        cached = self._cache.get(normalized)
        now = time.monotonic()
        if cached and now - cached[0] < self.cache_ttl_seconds:
            return [item.model_copy() for item in cached[1]]

        async with httpx.AsyncClient(
            timeout=self.timeout_seconds,
            transport=self.transport,
            follow_redirects=True,
            headers={"User-Agent": "EviLife/0.1 general-search"},
        ) as client:
            requests = [
                self._fetch_rss(
                    client,
                    self.base_url,
                    {"q": normalized, "format": "rss", "setlang": "zh-Hans", "mkt": "zh-CN"},
                    is_news=False,
                )
            ]
            if self.news_base_url and self._needs_news(normalized):
                requests.append(
                    self._fetch_rss(
                        client,
                        self.news_base_url,
                        {
                            "q": normalized,
                            "hl": "zh-CN",
                            "gl": "CN",
                            "ceid": "CN:zh-Hans",
                        },
                        is_news=True,
                    )
                )
                english_variant = self._english_news_variant(normalized)
                if english_variant:
                    requests.append(
                        self._fetch_rss(
                            client,
                            self.news_base_url,
                            {
                                "q": english_variant,
                                "hl": "en-US",
                                "gl": "US",
                                "ceid": "US:en",
                            },
                            is_news=True,
                        )
                    )
                    for trusted_query in self._trusted_news_variants(english_variant):
                        requests.append(
                            self._fetch_rss(
                                client,
                                self.news_base_url,
                                {
                                    "q": trusted_query,
                                    "hl": "en-US",
                                    "gl": "US",
                                    "ceid": "US:en",
                                },
                                is_news=True,
                            )
                        )
            batches = await asyncio.gather(*requests, return_exceptions=True)

        successful = [batch for batch in batches if isinstance(batch, list)]
        if not successful:
            raise GeneralSearchError("联网搜索暂时不可用")

        candidates = [item for batch in successful for item in batch]
        candidates.sort(key=lambda item: self._quality_score(normalized, item), reverse=True)
        results = self._deduplicate(candidates)[: self.max_results]
        self._cache[normalized] = (now, results)
        return [item.model_copy() for item in results]

    async def _fetch_rss(
        self,
        client: httpx.AsyncClient,
        url: str,
        params: dict[str, str],
        *,
        is_news: bool,
    ) -> list[GeneralSearchResult]:
        try:
            response = await client.get(url, params=params)
            response.raise_for_status()
        except (httpx.HTTPError, httpx.TimeoutException) as exc:
            raise GeneralSearchError("联网搜索暂时不可用") from exc
        if len(response.content) > 1_500_000:
            raise GeneralSearchError("联网搜索响应过大")
        try:
            root = ET.fromstring(response.content)
        except ET.ParseError as exc:
            raise GeneralSearchError("联网搜索返回格式异常") from exc

        results: list[GeneralSearchResult] = []
        candidate_limit = max(12, self.max_results * 4)
        for item in root.findall(".//item"):
            title = self._plain(item.findtext("title") or "")
            result_url = (item.findtext("link") or "").strip()
            snippet = self._plain(item.findtext("description") or "")
            source_node = item.find("source")
            source = (
                self._plain(source_node.text or "")
                if is_news and source_node is not None
                else (urlparse(result_url).hostname or "网页来源")
            )
            if not title or not self._safe_url(result_url):
                continue
            results.append(
                GeneralSearchResult(
                    title=title,
                    url=result_url,
                    snippet=snippet,
                    source=source or "新闻来源",
                    published_at=(item.findtext("pubDate") or "").strip() or None,
                )
            )
            if len(results) >= candidate_limit:
                break
        return results

    @staticmethod
    def _needs_news(query: str) -> bool:
        markers = (
            "最新", "现在", "目前", "今天", "今年", "近期", "新闻", "近况",
            "结婚", "婚姻", "离婚", "订婚", "去世", "当选", "发布", "上市",
            "价格", "现任", "了吗", "有没有", "宣布", "确认", "比赛", "获奖",
            "latest", "current", "today", "now", "married", "wedding", "divorce",
            "engaged", "died", "elected", "release", "price", "announced",
        )
        lowered = query.lower()
        return bool(re.search(r"\b20\d{2}\b", lowered)) or any(marker in lowered for marker in markers)

    @staticmethod
    def _english_news_variant(query: str) -> str | None:
        search_terms = re.findall(r"[A-Za-z][A-Za-z.'-]*", query)
        modifiers = {
            "latest", "current", "official", "news", "today", "now",
            "status", "relationship", "marital", "spouse", "partner",
            "married", "marriage", "wedding", "divorced", "divorce",
            "engaged", "engagement", "release", "released", "launched",
            "reuters", "ap", "confirmed", "announcement", "announced",
        }
        latin_words = [word for word in search_terms if word.lower() not in modifiers]
        if len(latin_words) < 2:
            return None
        lowered = query.lower()
        translations = (
            (("结婚", "婚姻", "married", "marriage", "marital", "wedding", "spouse"), "married wedding"),
            (("离婚", "divorced", "divorce"), "divorced divorce"),
            (("订婚", "engaged", "engagement"), "engaged engagement"),
            (("去世",), "died death"),
            (("发布", "上市"), "release launched"),
            (("获奖",), "award winner"),
            (("最新", "目前", "现在", "近况"), "latest"),
        )
        extra = next(
            (english for markers, english in translations if any(marker in lowered for marker in markers)),
            "latest news",
        )
        entity = " ".join(latin_words[:6])
        return f'"{entity}" {extra}'[:500]

    @staticmethod
    def _trusted_news_variants(english_query: str) -> tuple[str, str]:
        """Ask Google News for primary wire coverage instead of hoping it ranks first."""
        return (
            f"{english_query} source:Reuters"[:500],
            f"{english_query} source:AP"[:500],
        )

    def _deduplicate(self, items: list[GeneralSearchResult]) -> list[GeneralSearchResult]:
        results: list[GeneralSearchResult] = []
        seen_urls: set[str] = set()
        seen_titles: set[str] = set()
        source_counts: dict[str, int] = {}
        for item in items:
            title_key = re.sub(r"\W+", "", item.title.lower())[:180]
            if item.url in seen_urls or (title_key and title_key in seen_titles):
                continue
            source_key = item.source.lower().strip()
            if source_counts.get(source_key, 0) >= 2:
                continue
            seen_urls.add(item.url)
            seen_titles.add(title_key)
            source_counts[source_key] = source_counts.get(source_key, 0) + 1
            results.append(item)
        return results

    @staticmethod
    def _safe_url(value: str) -> bool:
        parsed = urlparse(value)
        return parsed.scheme in {"http", "https"} and bool(parsed.hostname)

    @staticmethod
    def _plain(value: str) -> str:
        return " ".join(html.unescape(re.sub(r"<[^>]+>", " ", value)).split())[:700]

    @staticmethod
    def _relevance_score(query: str, item: GeneralSearchResult) -> int:
        query_lower = query.lower()
        haystack_title = item.title.lower()
        haystack_all = f"{item.title} {item.snippet} {item.source}".lower()
        latin_tokens = set(re.findall(r"[a-z0-9][a-z0-9.+#-]{1,}", query_lower))
        cjk_runs = re.findall(r"[\u4e00-\u9fff]{2,}", query_lower)
        cjk_tokens = {
            run[index : index + 2]
            for run in cjk_runs
            for index in range(max(1, len(run) - 1))
        }
        score = 0
        for token in latin_tokens | cjk_tokens:
            if token in haystack_title:
                score += 4
            elif token in haystack_all:
                score += 1
        if any(marker in item.source for marker in (".gov", ".edu", "docs.", "developer.")):
            score += 1
        return score

    @classmethod
    def _quality_score(cls, query: str, item: GeneralSearchResult) -> int:
        score = cls._relevance_score(query, item)
        source = item.source.lower()
        trusted_sources = {
            "reuters": 10,
            "associated press": 10,
            "ap news": 10,
            "bbc": 7,
            "cnn": 7,
            "cbs news": 7,
            "pbs": 7,
            "npr": 7,
            "the new york times": 8,
            "new york times": 8,
            "the guardian": 5,
            "al jazeera": 5,
        }
        score += max((weight for name, weight in trusted_sources.items() if name in source), default=0)
        if any(marker in source for marker in (".gov", ".edu", "docs.", "developer.")):
            score += 4
        if item.published_at:
            try:
                published = parsedate_to_datetime(item.published_at)
                if published.tzinfo is None:
                    published = published.replace(tzinfo=timezone.utc)
                age_days = max(0, (datetime.now(timezone.utc) - published).days)
                if age_days <= 7:
                    score += 6
                elif age_days <= 31:
                    score += 5
                elif age_days <= 365:
                    score += 2
            except (TypeError, ValueError, OverflowError):
                pass
        return score
