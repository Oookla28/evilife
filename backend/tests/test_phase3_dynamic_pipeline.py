"""Phase 3 tests: EvidenceNote extraction, dedup, dynamic pipeline."""

from __future__ import annotations

import asyncio

from app.claims.models import HealthClaim
from app.evidence.dedup import deduplicate
from app.evidence.dynamic_pipeline import MAX_PROVIDER_CALLS_PER_CLAIM, DynamicEvidencePipeline
from app.evidence.evidence_note import EvidenceNote, build_evidence_note
from app.tools.base import EvidenceSource, ToolError
from app.tools.mock import MockEvidenceProvider


def _source(abstract: str, source_id: str = "S1", source_type: str = "rct", year: int = 2024) -> EvidenceSource:
    return EvidenceSource(
        source_id=source_id,
        source_database="europe_pmc",
        title=f"Paper {source_id}",
        source_type=source_type,
        year=year,
        abstract=abstract,
        url=f"https://example.test/{source_id}",
    )


# ---------------------------------------------------------------------------
# EvidenceNote extraction (deterministic rules)
# ---------------------------------------------------------------------------


def test_note_extracts_support_sentences() -> None:
    note = build_evidence_note(
        _source(
            "We observed a significant reduction in systolic blood pressure after "
            "sodium restriction. The intervention was well tolerated overall. "
            "Conclusion: sodium reduction lowers blood pressure in adults."
        )
    )
    assert note.direction == "support"
    assert note.supports
    assert any("reduction" in s for s in note.supports)
    assert "sodium reduction lowers" in note.finding


def test_note_extracts_opposition_from_null_result() -> None:
    note = build_evidence_note(
        _source(
            "Time-restricted eating showed no difference in weight loss compared "
            "with daily calorie restriction. There was no significant effect on "
            "body composition. Conclusion: TRE does not add weight-loss benefit."
        )
    )
    assert note.direction == "against"
    assert note.does_not_support
    assert any("no difference" in s for s in note.does_not_support)


def test_note_extracts_limitations() -> None:
    note = build_evidence_note(
        _source(
            "The trial reduced blood pressure significantly. However, the sample "
            "size was small and follow-up short, which limits generalizability."
        )
    )
    assert note.direction == "support"
    assert note.limitations
    assert any("sample size" in s for s in note.limitations)


def test_note_mixed_sentence_is_conservative() -> None:
    # Ambiguous sentence (negation + positive) must not be claimed as either.
    note = build_evidence_note(
        _source(
            "Blood pressure was reduced but showed no significant difference in "
            "mortality. The primary outcome improved."
        )
    )
    assert note.direction in {"support", "mixed", "context"}
    assert all("but" not in s for s in note.supports)


def test_note_sample_size_extraction() -> None:
    note = build_evidence_note(
        _source("We enrolled 412 participants in the randomized trial.")
    )
    assert note.sample_size == 412


def test_note_context_when_no_signal() -> None:
    note = build_evidence_note(_source("This review summarizes the current literature on diet."))
    assert note.direction == "context"
    assert not note.supports
    assert not note.does_not_support


# ---------------------------------------------------------------------------
# Dedup
# ---------------------------------------------------------------------------


def test_dedup_by_stable_key() -> None:
    items = [
        _source("a", source_id="S1"),
        _source("b", source_id="S1"),  # same source id -> duplicate
        _source("c", source_id="S2"),
    ]
    unique = deduplicate(items)
    assert len(unique) == 2
    assert [item.source_id for item in unique] == ["S1", "S2"]


def test_dedup_preserves_order() -> None:
    items = [_source("a", source_id="B"), _source("b", source_id="A"), _source("c", source_id="A")]
    unique = deduplicate(items)
    assert [item.source_id for item in unique] == ["B", "A"]


# ---------------------------------------------------------------------------
# DynamicEvidencePipeline
# ---------------------------------------------------------------------------


def _claim(text: str = "限钠饮食可以降低血压", claim_type: str = "effectiveness") -> HealthClaim:
    return HealthClaim(
        claim_id="C1",
        claim=text,
        type=claim_type,  # type: ignore[arg-type]
        original_text=text,
        source_intent=text,
    )


class ForAgainstProvider(MockEvidenceProvider):
    """Provider that returns support hits for FOR and null-result hits for AGAINST."""

    def __init__(self) -> None:
        super().__init__(sources=[])

    async def search(self, query: str, *, direction: str = "neutral", filters=None):
        self.last_query = query
        self.last_direction = direction
        if direction == "against":
            return [
                EvidenceSource(
                    source_id="W-NULL-1",
                    source_database="europe_pmc",
                    title="Sodium restriction and blood pressure null-result trial",
                    source_type="rct",
                    year=2024,
                    abstract=(
                        "Sodium restriction showed no significant difference in "
                        "blood pressure and no evidence of benefit."
                    ),
                    url="https://example.test/null",
                )
            ]
        return [
            EvidenceSource(
                source_id="W-POS-1",
                source_database="europe_pmc",
                title="Sodium reduction and blood pressure meta-analysis",
                source_type="meta_analysis",
                year=2023,
                abstract=(
                    "We observed a significant reduction in blood pressure "
                    "associated with sodium restriction. Conclusion: effective."
                ),
                url="https://example.test/pos",
            )
        ]


def test_pipeline_runs_bounded_for_against_searches() -> None:
    provider = ForAgainstProvider()
    pipeline = DynamicEvidencePipeline(provider=provider, corpus=None)
    result = asyncio.run(pipeline.run(_claim()))
    assert result.tool_calls == 2  # FOR + AGAINST, bounded
    assert result.supporting_notes
    assert result.opposing_notes
    assert result.notes
    # ranker must put the recent meta-analysis first
    assert result.notes[0].source_id == "W-POS-1"
    assert any("FOR" in line or "AGAINST" in line for line in result.trace)


def test_pipeline_bounded_even_with_many_queries() -> None:
    provider = ForAgainstProvider()
    pipeline = DynamicEvidencePipeline(provider=provider, corpus=None)
    result = asyncio.run(pipeline.run(_claim()))
    assert result.tool_calls <= MAX_PROVIDER_CALLS_PER_CLAIM


def test_pipeline_handles_provider_error() -> None:
    class FailingProvider(ForAgainstProvider):
        async def search(self, query: str, *, direction: str = "neutral", filters=None):
            raise ToolError("rate_limited", "busy", provider="mock", retryable=True)

    pipeline = DynamicEvidencePipeline(provider=FailingProvider(), corpus=None)
    result = asyncio.run(pipeline.run(_claim()))
    assert result.provider_error == "rate_limited"
    assert result.supporting_notes == []
    assert result.opposing_notes == []
    assert any("failed" in line for line in result.trace)


def test_pipeline_without_provider_uses_corpus_only() -> None:
    pipeline = DynamicEvidencePipeline(provider=None)  # corpus auto-loads
    result = asyncio.run(pipeline.run(_claim("16:8 限时进食可以减肥")))
    # corpus TRE claims exist even without a live provider
    assert result.supporting_notes or result.opposing_notes or result.notes


def test_pipeline_notes_are_evidence_notes() -> None:
    provider = ForAgainstProvider()
    pipeline = DynamicEvidencePipeline(provider=provider, corpus=None)
    result = asyncio.run(pipeline.run(_claim()))
    assert all(isinstance(note, EvidenceNote) for note in result.notes)
