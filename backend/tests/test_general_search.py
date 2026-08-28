import asyncio

import httpx

from app.general_search import GeneralWebSearch


def test_general_web_search_parses_bounded_rss_results() -> None:
    rss = b"""<?xml version="1.0" encoding="utf-8"?>
    <rss><channel>
      <item><title>Result One</title><link>https://example.com/one</link><description>First &amp; useful result.</description></item>
      <item><title>Unsafe</title><link>javascript:alert(1)</link><description>skip</description></item>
      <item><title>Result Two</title><link>https://example.org/two</link><description><![CDATA[<b>Second</b> result.]]></description></item>
    </channel></rss>"""

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["format"] == "rss"
        assert request.url.params["q"] == "test query"
        return httpx.Response(200, content=rss, headers={"content-type": "text/xml"})

    search = GeneralWebSearch(
        max_results=5,
        transport=httpx.MockTransport(handler),
    )
    results = asyncio.run(search.search("test query"))

    assert [item.title for item in results] == ["Result One", "Result Two"]
    assert results[0].source == "example.com"
    assert results[0].snippet == "First & useful result."
    assert results[1].snippet == "Second result."


def test_general_web_search_reranks_obviously_relevant_results() -> None:
    query = "Next.js 16 官方 发布说明"
    from app.general_search import GeneralSearchResult

    official = GeneralSearchResult(
        title="Next.js 16 Release",
        url="https://nextjs.org/blog/next-16",
        snippet="Official release notes",
        source="nextjs.org",
    )
    shopping = GeneralSearchResult(
        title="Next Official Site: Fashion",
        url="https://nextdirect.example/",
        snippet="Shop clothes",
        source="nextdirect.example",
    )

    assert GeneralWebSearch._relevance_score(query, official) > GeneralWebSearch._relevance_score(query, shopping)


def test_time_sensitive_question_blends_news_and_prefers_recent_trusted_source() -> None:
    web_rss = b"""<?xml version="1.0"?><rss><channel>
      <item><title>Taylor Swift official site</title><link>https://www.taylorswift.com/</link><description>Official website.</description></item>
    </channel></rss>"""
    news_rss = b"""<?xml version="1.0"?><rss><channel>
      <item><title>Taylor Swift and Travis Kelce are married</title><link>https://news.google.com/articles/one</link><description>Marriage confirmed by her publicist.</description><pubDate>Fri, 03 Jul 2026 20:00:00 GMT</pubDate><source url="https://apnews.com">AP News</source></item>
      <item><title>Taylor Swift wedding rumours</title><link>https://news.google.com/articles/two</link><description>Older speculation.</description><pubDate>Fri, 03 Jul 2020 20:00:00 GMT</pubDate><source url="https://example.com">Celebrity Blog</source></item>
    </channel></rss>"""

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "news.google.com":
            return httpx.Response(200, content=news_rss)
        return httpx.Response(200, content=web_rss)

    search = GeneralWebSearch(max_results=3, transport=httpx.MockTransport(handler))
    results = asyncio.run(search.search("Taylor Swift 结婚了吗"))

    assert results[0].source == "AP News"
    assert "are married" in results[0].title
    assert any(item.source == "www.taylorswift.com" for item in results)


def test_news_failure_does_not_discard_working_web_results() -> None:
    web_rss = b"""<?xml version="1.0"?><rss><channel>
      <item><title>Current product release</title><link>https://example.com/release</link><description>Release details.</description></item>
    </channel></rss>"""

    async def handler(request: httpx.Request) -> httpx.Response:
        if request.url.host == "news.google.com":
            return httpx.Response(503)
        return httpx.Response(200, content=web_rss)

    search = GeneralWebSearch(max_results=3, transport=httpx.MockTransport(handler))
    results = asyncio.run(search.search("产品现在发布了吗"))

    assert [item.title for item in results] == ["Current product release"]


def test_news_variant_keeps_entity_but_removes_generic_search_modifiers() -> None:
    query = "Taylor Swift married marriage status 2026 latest official"

    assert GeneralWebSearch._english_news_variant(query) == '"Taylor Swift" married wedding'


def test_trusted_news_variants_target_reuters_and_ap() -> None:
    variants = GeneralWebSearch._trusted_news_variants('"Taylor Swift" married wedding')

    assert variants == (
        '"Taylor Swift" married wedding source:Reuters',
        '"Taylor Swift" married wedding source:AP',
    )
