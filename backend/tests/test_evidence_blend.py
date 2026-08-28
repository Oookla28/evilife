import asyncio

from app.evidence.repository import EvidencePacketRepository
from app.evidence_blend import (
    EvidenceBlendService,
    RetrievedEvidence,
)


class FakeLiveSearch:
    def __init__(self, count: int) -> None:
        self.count = count
        self.query: str | None = None

    async def search(self, query: str) -> list[RetrievedEvidence]:
        self.query = query
        normalized = query.lower()
        if "sodium" in normalized:
            title = "限钠与血压证据"
            snippet = "研究显示减少钠摄入可以降低血压。"
        elif "pregnancy" in normalized or "medication" in normalized:
            title = "孕妇药物剂量安全证据"
            snippet = "孕妇规范药物剂量有助于改善用药安全。"
        else:
            title = "成年人睡眠改善证据"
            snippet = "睡眠干预可以改善成年人的睡眠。"
        return [
            RetrievedEvidence(
                source_id=f"W{index}",
                title=f"{title} {index}",
                url=f"https://example.test/{index}",
                source_type="Systematic Review",
                organization="Test Journal",
                year=2025,
                snippet=snippet,
                reliability_score=0.95,
                channel="live_medical_search",
            )
            for index in range(1, self.count + 1)
        ]


def test_packet_plus_live_search_uses_at_least_88_percent_reliable_evidence() -> None:
    packet = EvidencePacketRepository().get("sodium_and_hypertension")
    search = FakeLiveSearch(3)
    blend = asyncio.run(
        EvidenceBlendService(live_search=search).build(
            question="限钠饮食对高血压有帮助吗？",
            search_query="ignored for known packet",
            mode="auto",
            packet=packet,
        )
    )

    assert blend.reliable_weight == 0.88
    assert blend.general_weight == 0.12
    assert blend.live_search_status == "ok"
    assert blend.fusion_method == "rrf"
    assert len(blend.trusted_sources) >= 5
    assert blend.trusted_sources[0].channel == "curated_database"
    assert any(
        source.channel == "live_medical_search"
        for source in blend.trusted_sources
    )
    assert blend.supporting_evidence
    assert blend.opposing_evidence
    assert 'TITLE_ABS:"sodium intake"' in (search.query or "")


def test_high_risk_question_targets_88_percent_reliable_evidence() -> None:
    blend = asyncio.run(
        EvidenceBlendService(live_search=FakeLiveSearch(3)).build(
            question="孕妇能否自行调整药物剂量？",
            search_query="pregnancy medication dose safety",
            mode="auto",
        )
    )
    assert blend.target_reliable_weight == 0.88
    assert blend.reliable_weight == 0.88


def test_sparse_live_evidence_is_capped_at_65_percent() -> None:
    blend = asyncio.run(
        EvidenceBlendService(live_search=FakeLiveSearch(1)).build(
            question="如何改善睡眠？",
            search_query="sleep improvement adults",
            mode="auto",
        )
    )
    assert blend.reliable_weight == 0.65
    assert blend.general_weight == 0.35
    assert "来源较少" in blend.policy_reason


def test_no_traceable_source_forces_general_only_degraded_mode() -> None:
    blend = asyncio.run(
        EvidenceBlendService().build(
            question="未知健康问题",
            search_query="unknown health question",
            mode="auto",
        )
    )
    assert blend.reliable_weight == 0
    assert blend.general_weight == 1
    assert blend.trusted_sources == []
