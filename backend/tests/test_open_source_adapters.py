from app.evidence.grounding import (
    STATUS_GROUNDED,
    STATUS_OFF_ENVELOPE,
    STATUS_PHANTOM,
    STATUS_UNCITED,
    verify_claims,
)
from app.evidence.rrf import reciprocal_rank_fusion


def test_grounding_rejects_uncited_phantom_and_off_envelope_claims() -> None:
    report = verify_claims(
        [
            {"text": "有来源", "citations": ["P1"]},
            {"text": "没有来源", "citations": []},
            {"text": "虚构来源", "citations": ["P404"]},
            {"text": "检索范围外", "citations": ["P2"]},
        ],
        known_source_ids={"P1", "P2"},
        allowed_source_ids=["P1"],
    )

    assert report["grounded"] is False
    assert [item["status"] for item in report["claims"]] == [
        STATUS_GROUNDED,
        STATUS_UNCITED,
        STATUS_PHANTOM,
        STATUS_OFF_ENVELOPE,
    ]
    assert report["semantic_entailment_checked"] is False


def test_rrf_rewards_sources_returned_by_multiple_channels() -> None:
    lexical = [{"id": "A"}, {"id": "B"}, {"id": "C"}]
    semantic = [{"id": "B"}, {"id": "D"}, {"id": "A"}]

    fused = reciprocal_rank_fusion(
        [lexical, semantic],
        key=lambda item: item["id"],
        limit=4,
    )

    assert [item["id"] for item in fused] == ["B", "A", "D", "C"]


def test_rrf_deduplicates_a_channel_without_inflating_score() -> None:
    fused = reciprocal_rank_fusion(
        [[{"id": "A"}, {"id": "A"}], [{"id": "B"}]],
        key=lambda item: item["id"],
        limit=5,
    )
    assert [item["id"] for item in fused] == ["A", "B"]
