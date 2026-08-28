"""Tests for the Dynamic Evidence Engine: bidirectional live search,
authoritative corpus channel, and claim-level Verdict computation."""

from __future__ import annotations

import asyncio
import json
from datetime import date

from fastapi.testclient import TestClient

from app.evidence.corpus import AuthoritativeCorpus
from app.evidence.repository import EvidencePacketRepository
from app.evidence.verdict import build_verdict
from app.evidence_blend import EvidenceBlendService, RetrievedEvidence
from app.main import app
from app.schemas import EvidenceStrength, VerdictEvidenceItem


client = TestClient(app)


def _live(count: int = 2) -> type:
    class FakeLiveSearch:
        def __init__(self, n: int = count) -> None:
            self.n = n
            self.queries: list[str] = []

        async def search_directional(
            self, query: str, direction: str
        ) -> list[RetrievedEvidence]:
            self.queries.append(f"{direction}:{query}")
            return [
                RetrievedEvidence(
                    source_id=f"W{index}",
                    title=(
                        "Sodium blood pressure and time-restricted eating "
                        f"weight-loss evidence {index}"
                    ),
                    url=f"https://example.test/live/{index}",
                    source_type="Systematic Review",
                    organization="Test Journal",
                    year=2025,
                    snippet=(
                        "Sodium reduction lowered blood pressure; time-restricted "
                        "eating reduced body weight."
                        if direction == "support"
                        else "Sodium reduction showed no difference in blood "
                        "pressure; time-restricted eating showed no difference "
                        "in body weight."
                    ),
                    reliability_score=0.95,
                    channel="live_medical_search",
                )
                for index in range(1, self.n + 1)
            ]

    return FakeLiveSearch


def _directional(
    evidence_id: str,
    direction: str,
    finding: str = "sample finding",
) -> VerdictEvidenceItem:
    return VerdictEvidenceItem(
        evidence_id=evidence_id,
        source_id=f"SRC-{evidence_id}",
        title=f"Source {evidence_id}",
        year=2024,
        source_type="systematic review",
        organization="Test Org",
        direction=direction,  # type: ignore[arg-type]
        finding=finding,
        url="https://example.test/src",
        channel="curated_database",
        reliability_score=0.9,
    )


# ---------------------------------------------------------------------------
# corpus channel (P1)
# ---------------------------------------------------------------------------


def test_corpus_loads_authoritative_database() -> None:
    corpus = AuthoritativeCorpus()
    assert corpus.db_path.is_file(), "authoritative_health.sqlite3 must exist"


def test_corpus_claims_are_direction_labelled() -> None:
    corpus = AuthoritativeCorpus()
    hits = corpus.search_claims("地中海饮食", limit=6)
    assert hits, "corpus must return Mediterranean claims"
    assert any(hit.direction == "support" for hit in hits)
    assert any(hit.direction == "context" for hit in hits)
    assert all(hit.channel == "curated_database" for hit in hits)


def test_corpus_claims_topic_fallback() -> None:
    corpus = AuthoritativeCorpus()
    hits = corpus.search_claims(
        "所有人都应该严格限盐吗",
        topic="sodium_and_hypertension",
        limit=4,
    )
    assert hits, "topic-backed queries must fall back to the reviewed claims"


def test_corpus_literature_is_tier_ranked() -> None:
    corpus = AuthoritativeCorpus()
    hits = corpus.search_literature("sodium", limit=5)
    assert hits
    assert all(hit.url.startswith("http") for hit in hits)


def test_corpus_missing_file_degrades_gracefully() -> None:
    from pathlib import Path

    corpus = AuthoritativeCorpus(db_path=Path("/nonexistent/corpus.sqlite3"))
    assert corpus.search("任何问题") == []
    assert corpus.search_claims("任何问题") == []
    assert corpus.search_literature("anything") == []


# ---------------------------------------------------------------------------
# bidirectional blend (P0)
# ---------------------------------------------------------------------------


def test_bidirectional_search_uses_independent_queries() -> None:
    packet = EvidencePacketRepository().get("sodium_and_hypertension")
    fake = _live(2)()
    blend = asyncio.run(
        EvidenceBlendService(live_search=fake).build_bidirectional(
            question="限钠饮食对高血压有帮助吗？",
            support_query="support-query",
            boundary_query="boundary-query",
            mode="auto",
            packet=packet,
            topic="sodium_and_hypertension",
        )
    )
    assert len(fake.queries) == 2, "FOR and AGAINST must be searched independently"
    assert fake.queries[0].startswith("support:")
    assert fake.queries[1].startswith("against:")
    assert 'TITLE_ABS:"sodium intake"' in fake.queries[0]
    assert "no benefit" in fake.queries[1]
    assert blend.supporting_evidence
    assert blend.opposing_evidence


def test_bidirectional_blend_keeps_both_sides_separate() -> None:
    packet = EvidencePacketRepository().get("sodium_and_hypertension")
    blend = asyncio.run(
        EvidenceBlendService(live_search=_live(2)()).build_bidirectional(
            question="限钠饮食对高血压有帮助吗？",
            support_query="q",
            boundary_query="q",
            mode="auto",
            packet=packet,
            topic="sodium_and_hypertension",
        )
    )
    support_ids = {item.evidence_id for item in blend.supporting_evidence}
    oppose_ids = {item.evidence_id for item in blend.opposing_evidence}
    assert support_ids & oppose_ids == set(), "same claim must not be double-counted"
    assert any(item.channel == "live_medical_search" for item in blend.supporting_evidence)
    assert any(item.channel == "curated_database" for item in blend.supporting_evidence)


def test_bidirectional_unknown_topic_uses_corpus_and_live() -> None:
    fake = _live(2)()
    blend = asyncio.run(
        EvidenceBlendService(live_search=fake).build_bidirectional(
            question="16:8 限时进食是否比普通控制热量更有效？",
            support_query="time restricted eating",
            boundary_query="time restricted eating null",
            mode="deep",
        )
    )
    # The corpus contains human-reviewed TRE claims, so even without a golden
    # packet the engine must find both directions.
    assert blend.supporting_evidence
    assert blend.opposing_evidence
    assert blend.reliable_weight >= 0.78


# ---------------------------------------------------------------------------
# verdict (P2)
# ---------------------------------------------------------------------------


def test_verdict_true_when_strong_support_and_no_opposition() -> None:
    verdict = build_verdict(
        claim="减少过量钠摄入可以降低血压",
        supporting=[_directional("E1-S1", "support")],
        opposing=[],
        evidence_strength="high",
        gate_status="normal",
        conflict_detected=False,
        applies_to=["高血压人群"],
        does_not_apply_to=[],
        limitations=["个体反应存在差异"],
        today=date(2026, 8, 11),
    )
    assert verdict.verdict == "true"
    assert verdict.confidence == 0.9
    assert verdict.evidence_grade == "high"
    assert verdict.last_updated == "2026-08-11"


def test_verdict_partly_true_on_conflict() -> None:
    verdict = build_verdict(
        claim="所有人都应该严格限盐",
        supporting=[_directional("E1-S1", "support")],
        opposing=[_directional("E1-A1", "against")],
        evidence_strength="medium",
        gate_status="degraded",
        conflict_detected=True,
        applies_to=[],
        does_not_apply_to=["低血压人群"],
        limitations=["证据存在冲突"],
        today=date(2026, 8, 11),
    )
    assert verdict.verdict == "partly_true"
    assert verdict.uncertainty
    assert "直接反对证据" in " ".join(verdict.uncertainty)


def test_verdict_keeps_applicability_boundary_out_of_counterevidence() -> None:
    verdict = build_verdict(
        claim="地中海饮食可以降低心血管风险",
        supporting=[_directional("E1-S1", "support")],
        opposing=[
            _directional(
                "E1-B1", "context", "不能据此外推到所有人或替代治疗"
            )
        ],
        evidence_strength="medium",
        gate_status="normal",
        conflict_detected=False,
        applies_to=[],
        does_not_apply_to=[],
        limitations=[],
        today=date(2026, 8, 12),
    )
    assert verdict.verdict == "true"
    assert verdict.verdict_detail == "SUPPORTED"
    assert "不等同于反证" in " ".join(verdict.uncertainty)


def test_verdict_insufficient_when_no_support() -> None:
    verdict = build_verdict(
        claim="只看一张照片能判断缺什么营养",
        supporting=[],
        opposing=[_directional("E1-A1", "against")],
        evidence_strength="insufficient",
        gate_status="normal",
        conflict_detected=False,
        applies_to=[],
        does_not_apply_to=[],
        limitations=["证据不足"],
        today=date(2026, 8, 11),
    )
    assert verdict.verdict == "insufficient"
    assert verdict.confidence == 0.3


def test_verdict_false_when_opposition_dominates() -> None:
    verdict = build_verdict(
        claim="16:8 一定比普通限热量更有效",
        supporting=[_directional("E1-S1", "support")],
        opposing=[
            _directional("E1-A1", "against"),
            _directional("E2-A1", "against"),
            _directional("E3-A1", "against"),
        ],
        evidence_strength="medium",
        gate_status="normal",
        conflict_detected=False,
        applies_to=[],
        does_not_apply_to=[],
        limitations=["研究结论不一致"],
        today=date(2026, 8, 11),
    )
    assert verdict.verdict == "false"


def test_verdict_refused_keeps_insufficient() -> None:
    verdict = build_verdict(
        claim="高血压能不能停药",
        supporting=[_directional("E1-S1", "support")],
        opposing=[],
        evidence_strength="high",
        gate_status="refused",
        conflict_detected=False,
        applies_to=[],
        does_not_apply_to=[],
        limitations=["涉及停药"],
        today=date(2026, 8, 11),
    )
    assert verdict.verdict == "insufficient"
    assert verdict.confidence == 0.25


# ---------------------------------------------------------------------------
# orchestrator integration
# ---------------------------------------------------------------------------


def _orchestrate(question: str, mode: str = "eviroute_gate") -> dict:
    response = client.post(
        "/api/v1/orchestrate",
        data={"session_id": "dynamic-engine", "mode": mode, "text": question},
    )
    assert response.status_code == 200
    return response.json()


def test_deep_path_response_contains_verdict() -> None:
    body = _orchestrate("所有人都应该严格限盐吗？")
    props = body["module_plan"][0]["props"]

    assert body["route"] == "deep_path"
    verdict = props.get("verdict")
    assert verdict is not None
    assert verdict["verdict"] in {"true", "partly_true", "false", "insufficient"}
    assert 0 <= verdict["confidence"] <= 1
    assert verdict["supporting_evidence"]
    assert verdict["opposing_evidence"]
    assert body["support_evidence_count"] > 0
    assert body["boundary_evidence_count"] > 0
    assert verdict["last_updated"]


def test_fast_path_response_contains_verdict() -> None:
    body = _orchestrate("限钠饮食对高血压有帮助吗？")
    props = body["module_plan"][0]["props"]

    assert body["route"] == "fast_path"
    verdict = props.get("verdict")
    assert verdict is not None
    assert verdict["supporting_evidence"]
    assert props.get("evidence_mix", {}).get("support_evidence_count", 0) > 0


def test_tre_topic_returns_verdict_with_precompiled_packet() -> None:
    body = _orchestrate("限时进食对比普通控制热量是否更有效？")
    props = body["module_plan"][0]["props"]

    assert body["route"] in {"deep_path", "fast_path"}
    verdict = props.get("verdict")
    assert verdict is not None
    assert verdict["verdict"] in {"true", "partly_true", "false", "insufficient"}
    # TRE now has a reviewed packet; corpus/live channels may still enrich it.
    assert verdict["supporting_evidence"] or verdict["opposing_evidence"]
    assert props.get("source") == "hybrid_fast_path"
    assert props.get("packet_id") == "packet-time-restricted-eating-weight-v1"


def test_refused_question_verdict_is_insufficient() -> None:
    body = _orchestrate("高血压能不能停药只吃低盐？")
    props = body["module_plan"][0]["props"]

    assert body["gate_status"] == "refused"
    verdict = props.get("verdict")
    assert verdict is not None
    assert verdict["verdict"] == "insufficient"


def test_verdict_survives_json_serialization() -> None:
    body = _orchestrate("所有人都应该严格限盐吗？")
    raw = json.dumps(body, ensure_ascii=False)
    assert '"verdict"' in raw
    assert '"confidence"' in raw


def test_evidence_snapshot_counts_verdict_sides() -> None:
    start = _orchestrate("所有人都应该严格限盐吗？")
    response = client.get(f"/api/v1/runs/{start['run_id']}/events")
    assert response.status_code == 200
    snapshot = next(
        json.loads(line.removeprefix("data: "))
        for line in response.text.splitlines()
        if line.startswith("data: ")
        and json.loads(line.removeprefix("data: "))["type"] == "evidence.snapshot"
    )
    assert snapshot["payload"]["support_evidence_count"] > 0
    assert snapshot["payload"]["boundary_evidence_count"] > 0


def test_tre_topic_exposes_packet_traceability() -> None:
    body = _orchestrate("限时进食对比普通控制热量是否更有效？")
    props = body["module_plan"][0]["props"]
    assert props["packet_id"] == "packet-time-restricted-eating-weight-v1"
    assert props["citations"]
    assert all(item["url"].startswith("https://") for item in props["citations"])
    verdict = props["verdict"]
    assert body["support_evidence_count"] == len(verdict["supporting_evidence"])
    assert body["boundary_evidence_count"] == len(verdict["opposing_evidence"])
    assert body["evidence_count"] > 0
    assert any(
        step["step"] == "evidence.compose"
        for step in props["trace_steps"]
    )


def test_dynamic_notes_survive_schema_validation() -> None:
    body = _orchestrate("限时进食对比普通控制热量是否更有效？")
    props = body["module_plan"][0]["props"]
    from app.schemas import EvidenceAnswer

    EvidenceAnswer.model_validate(props)  # must not raise extra-forbidden
