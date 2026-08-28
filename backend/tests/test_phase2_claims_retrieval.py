"""Phase 2 tests: Claim Decomposer, Query Generator, Evidence Ranker."""

from __future__ import annotations

import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.claims.decomposer import decompose
from app.claims.models import HealthClaim, MAX_CLAIMS
from app.claims.normalizer import normalize_claim
from app.claims.worthiness import assess, classify
from app.evidence.query_generator import MAX_QUERY_EXPANSION, QueryGenerator
from app.evidence.ranker import EvidenceRanker
from app.tools.base import EvidenceSource


# ---------------------------------------------------------------------------
# ClaimDecomposer
# ---------------------------------------------------------------------------


def test_decompose_multi_claim_input() -> None:
    claims = decompose("16:8 限时进食可以减肥，而且还能改善胰岛素抵抗，同时不会掉肌肉。")
    assert len(claims) == 3
    assert claims[0].type == "effectiveness"
    assert claims[1].type == "metabolic"
    assert claims[2].type == "safety_or_body_composition"
    # every claim must trace back to the source verbatim
    for claim in claims:
        assert claim.original_text in claim.source_intent
        assert claim.span_end > claim.span_start


def test_decompose_semicolon_separated() -> None:
    claims = decompose("地中海饮食可以降低心血管风险；限钠饮食有助于降血压。")
    assert len(claims) == 2
    assert "地中海饮食" in claims[0].claim
    assert "限钠" in claims[1].claim


def test_decompose_filters_commands_and_definition_questions() -> None:
    assert decompose("打开16:8计时器") == []
    assert decompose("什么是地中海饮食？") == []


def test_decompose_respects_max_claims() -> None:
    long_input = "；".join(
        f"第{index}种食物能降低血压{index}" for index in range(1, 9)
    )
    claims = decompose(long_input)
    assert len(claims) <= MAX_CLAIMS


def test_decompose_keeps_original_meaning() -> None:
    claims = decompose("咖啡能提神；但长期大量喝咖啡会影响睡眠。")
    assert len(claims) == 2
    assert claims[0].claim == "咖啡能提神"
    assert claims[1].claim == "长期大量喝咖啡会影响睡眠"


def test_claim_ids_are_contiguous() -> None:
    claims = decompose("低盐有益血压，还能帮助减重。")
    assert [c.claim_id for c in claims] == ["C1", "C2"]


def test_worthiness_and_classify() -> None:
    assert assess("16:8 可以减肥").is_claim is True
    assert assess("什么是地中海饮食").is_claim is False
    assert assess("打开计时器").is_claim is False
    assert classify("A 比 B 更有效") == "comparison"
    assert classify("咖啡导致失眠") == "causal"


def test_normalize_claim_strips_question_particle() -> None:
    assert normalize_claim("每天走一万步对健康有好处吗") == "每天走一万步对健康有好处"


# ---------------------------------------------------------------------------
# QueryGenerator
# ---------------------------------------------------------------------------


def _claim(text: str, claim_type: str = "effectiveness") -> HealthClaim:
    return HealthClaim(
        claim_id="C1",
        claim=text,
        type=claim_type,  # type: ignore[arg-type]
        original_text=text,
        source_intent=text,
    )


def test_query_generator_bounded_expansion() -> None:
    queries = QueryGenerator().generate(_claim("16:8 限时进食可以减肥"))
    assert len(queries.queries) <= MAX_QUERY_EXPANSION
    roles = [q.role for q in queries.queries]
    assert "primary" in roles


def test_query_generator_maps_zh_to_en_stem() -> None:
    queries = QueryGenerator().generate(_claim("地中海饮食可以降低心血管风险"))
    en_queries = [q.query for q in queries.queries if q.language == "en"]
    assert any("Mediterranean diet" in q for q in en_queries)
    assert any("cardiovascular" in q for q in en_queries)


def test_query_generator_contradiction_query() -> None:
    queries = QueryGenerator().generate(_claim("限钠饮食能降低血压"))
    assert any(q.role == "contradiction" and "no benefit" in q.query for q in queries.queries)


def test_query_generator_population_claim_primary_direction() -> None:
    queries = QueryGenerator().generate(
        _claim("所有人都应该严格限盐", claim_type="population_claim")
    )
    primary = next(q for q in queries.queries if q.role == "primary")
    assert primary.direction == "against"


# ---------------------------------------------------------------------------
# EvidenceRanker
# ---------------------------------------------------------------------------


def _source(
    source_id: str,
    source_type: str,
    year: int,
    title: str = "",
    abstract: str = "",
    population: str | None = None,
) -> EvidenceSource:
    return EvidenceSource(
        source_id=source_id,
        source_database="mock",
        title=title or f"Title {source_id}",
        source_type=source_type,
        year=year,
        abstract=abstract,
        population=population,
        url=f"mock://{source_id}",
    )


def test_ranker_prefers_high_quality_and_relevant() -> None:
    claim = _claim("限钠饮食可以降低血压", claim_type="effectiveness")
    sources = [
        _source("S1", "observational", 2023, abstract="sodium and blood pressure"),
        _source("S2", "rct", 2023, abstract="sodium intake blood pressure"),
        _source("S3", "guideline", 2012, abstract="sodium blood pressure guideline"),
    ]
    ranked = EvidenceRanker().rank(sources, claim, en_terms=["sodium"], today=date(2026, 8, 12))
    # RCT + recent beats the 2012 guideline; relevant beats irrelevant.
    assert ranked[0].source.source_id == "S2"


def test_ranker_relevant_beats_irrelevant() -> None:
    claim = _claim("咖啡对血压的影响", claim_type="causal")
    sources = [
        _source("S1", "rct", 2024, abstract="unrelated topic about vitamins"),
        _source("S2", "cohort", 2022, abstract="coffee consumption blood pressure cohort"),
    ]
    ranked = EvidenceRanker().rank(sources, claim, en_terms=["coffee", "blood pressure"], today=date(2026, 8, 12))
    assert ranked[0].source.source_id == "S2"


def test_ranker_scores_are_bounded_and_deterministic() -> None:
    claim = _claim("维生素D补充有益骨骼健康")
    sources = [_source("S1", "meta_analysis", 2024, abstract="vitamin D bone"), _source("S2", "review", 2020, abstract="vitamin D")]
    ranker = EvidenceRanker()
    first = ranker.rank(sources, claim)
    second = ranker.rank(sources, claim)
    assert [item.score for item in first] == [item.score for item in second]
    assert all(0 <= item.score <= 1 for item in first)
    assert all(item.reasons for item in first)


def test_ranker_population_match_lifts_score() -> None:
    claim = _claim("孕妇应该补铁吗", claim_type="effectiveness")
    sources = [
        _source("S1", "rct", 2024, abstract="iron", population="general adults"),
        _source("S2", "rct", 2024, abstract="iron supplementation", population="pregnant women"),
    ]
    ranked = EvidenceRanker().rank(sources, claim, en_terms=["iron"], today=date(2026, 8, 12))
    assert ranked[0].source.source_id == "S2"
