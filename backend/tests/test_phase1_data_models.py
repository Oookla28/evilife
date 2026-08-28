"""Phase 1 tests: claim models, evidence tool layer, trace, verdict v2 schema."""

from __future__ import annotations

import asyncio

import pytest
from pydantic import ValidationError

from app.claims.models import MAX_CLAIMS, HealthClaim
from app.schemas import Verdict, VerdictEvidenceItem
from app.tools.base import (
    EvidenceProvider,
    EvidenceSource,
    SearchFilters,
    ToolError,
    provider_health_note,
)
from app.tools.europe_pmc import EuropePMCProvider
from app.tools.mock import MockEvidenceProvider
from app.trace.models import TraceRecorder, TraceStep


# ---------------------------------------------------------------------------
# HealthClaim models
# ---------------------------------------------------------------------------


def test_claim_requires_traceable_original() -> None:
    claim = HealthClaim(
        claim_id="C1",
        claim="16:8 限时进食可以帮助控制体重",
        type="effectiveness",
        original_text="16:8 限时进食可以帮助控制体重",
        span_start=0,
        span_end=15,
        source_intent="16:8 限时进食可以帮助控制体重，而且不伤肌肉",
    )
    assert claim.claim_id == "C1"
    assert claim.source_intent == "16:8 限时进食可以帮助控制体重，而且不伤肌肉"


def test_claim_rejects_span_out_of_bounds() -> None:
    with pytest.raises(ValidationError):
        HealthClaim(
            claim_id="C1",
            claim="x",
            type="other",
            original_text="x",
            span_start=5,
            span_end=2,
        )


def test_claim_rejects_non_verbatim_original() -> None:
    with pytest.raises(ValidationError):
        HealthClaim(
            claim_id="C1",
            claim="x",
            type="other",
            original_text="原文字段不来自输入",
            source_intent="完全不同的输入",
        )


def test_claim_id_pattern() -> None:
    with pytest.raises(ValidationError):
        HealthClaim(
            claim_id="bad-id",
            claim="x",
            type="other",
            original_text="x",
        )


def test_max_claims_cap_is_defined() -> None:
    assert MAX_CLAIMS == 5


# ---------------------------------------------------------------------------
# EvidenceSource
# ---------------------------------------------------------------------------


def test_evidence_source_stable_key_prefers_doi() -> None:
    source = EvidenceSource(
        source_id="123",
        source_database="europe_pmc",
        title="Some paper",
        source_type="meta_analysis",
        doi="10.1000/XYZ",
        pmid="999",
        url="https://example.test/1",
    )
    assert source.stable_key() == "doi:10.1000/xyz"


def test_evidence_source_stable_key_falls_back_to_title() -> None:
    source = EvidenceSource(
        source_id="1",
        source_database="mock",
        title="The Title",
        source_type="other",
        url="mock://1",
    )
    assert source.stable_key() == "title:the title"


def test_evidence_source_requires_core_fields() -> None:
    with pytest.raises(ValidationError):
        EvidenceSource(source_id="x")  # missing source_database + title


# ---------------------------------------------------------------------------
# MockEvidenceProvider
# ---------------------------------------------------------------------------


def test_mock_provider_returns_scripted_sources() -> None:
    provider = MockEvidenceProvider()
    results = asyncio.run(provider.search("限钠", direction="support"))
    assert results
    assert results[0].source_database == "mock"
    assert results[0].url.startswith("mock://")
    assert provider.last_query == "限钠"
    assert provider.last_direction == "support"


def test_mock_provider_structured_error() -> None:
    provider = MockEvidenceProvider()
    with pytest.raises(ToolError) as exc_info:
        asyncio.run(provider.search("   "))
    assert exc_info.value.code == "invalid_query"
    assert exc_info.value.provider == "mock"
    assert exc_info.value.to_dict()["retryable"] is False


def test_mock_provider_fetch() -> None:
    provider = MockEvidenceProvider()
    found = asyncio.run(provider.fetch("MOCK-SR-001"))
    assert found is not None
    assert asyncio.run(provider.fetch("NOPE")) is None


# ---------------------------------------------------------------------------
# EuropePMCProvider (mock transport)
# ---------------------------------------------------------------------------


class FakeTransport:
    def __init__(self, items: list[dict]) -> None:
        self.items = items
        self.last_params: dict | None = None

    async def __aenter__(self) -> "FakeTransport":
        return self

    async def __aexit__(self, *args) -> None:
        return None


def _fake_provider(items: list[dict]) -> EuropePMCProvider:
    provider = EuropePMCProvider()

    async def fake_get(url: str, params: dict) -> list[dict]:
        return items

    provider._get_search = fake_get  # type: ignore[method-assign]
    return provider


def test_europe_pmc_provider_parses_metadata() -> None:
    items = [
        {
            "pmid": "12345",
            "pmcid": "PMC67890",
            "title": "Sodium intake and blood pressure: a <i>meta-analysis</i>",
            "abstractText": "We found a significant reduction in systolic blood pressure.",
            "pubYear": "2023",
            "journalTitle": "Example Journal",
            "authorList": {"author": ["Alice", "Bob"]},
            "pubTypeList": {"pubType": ["Journal Article", "Meta-Analysis"]},
            "doi": "10.1000/abc",
        }
    ]
    provider = _fake_provider(items)
    results = asyncio.run(provider.search("sodium"))
    assert len(results) == 1
    source = results[0]
    assert source.pmid == "12345"
    assert source.doi == "10.1000/abc"
    assert source.year == 2023
    assert source.source_type == "meta_analysis"
    assert "meta-analysis" in source.title
    assert source.authors == ["Alice", "Bob"]
    assert source.stable_key() == "doi:10.1000/abc"


def test_europe_pmc_provider_against_direction_appends_null_clauses() -> None:
    compiled = EuropePMCProvider._compile_query(
        "sodium",
        "against",
        SearchFilters(source_types=["rct"], date_from="2020"),
    )
    assert "no benefit" in compiled
    assert "PUB_TYPE:" in compiled
    assert "2020" in compiled


def test_provider_health_note() -> None:
    note = provider_health_note(None)
    assert "未配置" in note
    note2 = provider_health_note(MockEvidenceProvider())
    assert "mock" in note2


# ---------------------------------------------------------------------------
# Trace
# ---------------------------------------------------------------------------


def test_trace_recorder_records_steps() -> None:
    recorder = TraceRecorder("run-1")
    recorder.add(step="claim.parse", action="decompose", output_summary="2 claims")
    recorder.add(
        step="pubmed.search",
        action="search",
        tool="europe_pmc",
        output_summary="12 papers",
        status="ok",
    )
    recorder.add(
        step="provider.fail",
        action="search",
        tool="ncbi",
        output_summary="rate limited",
        status="failed",
    )
    steps = recorder.snapshot()
    assert len(steps) == 3
    assert steps[0].step == "claim.parse"
    assert steps[1].tool == "europe_pmc"
    assert steps[2].status == "failed"
    summary = recorder.to_user_facing_summary()
    assert any("12 papers" in line for line in summary)


def test_trace_recorder_bounded() -> None:
    recorder = TraceRecorder("run-2", max_steps=4)
    for index in range(10):
        recorder.add(step=f"step-{index}", action="x", output_summary=str(index))
    assert len(recorder.snapshot()) == 4


def test_trace_step_requires_step_and_action() -> None:
    with pytest.raises(ValidationError):
        TraceStep(step="", action="")


# ---------------------------------------------------------------------------
# Verdict v2 schema extension
# ---------------------------------------------------------------------------


def test_verdict_supports_v2_detail_field() -> None:
    verdict = Verdict(
        verdict="partly_true",
        confidence=0.6,
        evidence_grade="moderate",
        claim="16:8 限时进食可以帮助控制体重",
        short_reason="证据存在分歧",
        applies_to=["超重成人"],
        does_not_apply_to=["低体重人群"],
        supporting_evidence=[],
        opposing_evidence=[],
        uncertainty=["研究结论不一致"],
        last_updated="2026-08-12",
        verdict_detail="MIXED_EVIDENCE",
        what_could_change_this_verdict=["更长周期的 RCT 结果", "人群特异数据"],
    )
    assert verdict.verdict_detail == "MIXED_EVIDENCE"
    assert len(verdict.what_could_change_this_verdict) == 2


def test_verdict_v2_detail_must_be_valid() -> None:
    with pytest.raises(ValidationError):
        Verdict(
            verdict="true",
            confidence=0.9,
            evidence_grade="high",
            claim="x",
            short_reason="y",
            applies_to=[],
            does_not_apply_to=[],
            supporting_evidence=[],
            opposing_evidence=[],
            uncertainty=[],
            last_updated="2026-08-12",
            verdict_detail="NOT_A_VALID_VALUE",  # type: ignore[arg-type]
        )
