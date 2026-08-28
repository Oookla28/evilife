import json
from pathlib import Path

import pytest

from app.evidence import (
    CitedClaim,
    CitationReference,
    CitationVerifier,
    EvidencePacketNotFoundError,
    EvidencePacketRepository,
    EvidencePacketSchemaError,
    FastPath,
    TopicMatcher,
    UNKNOWN_TOPIC,
)

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_DIR = ROOT / "data" / "evidence"


@pytest.fixture
def repository() -> EvidencePacketRepository:
    return EvidencePacketRepository(EVIDENCE_DIR)


def test_repository_loads_by_topic_and_caches(
    repository: EvidencePacketRepository,
) -> None:
    first = repository.get("sodium_and_hypertension")
    second = repository.get("sodium_and_hypertension")

    assert first is second
    assert first.packet_id == "packet-sodium-hypertension-v1"


def test_repository_reports_missing_topic(
    repository: EvidencePacketRepository,
) -> None:
    with pytest.raises(EvidencePacketNotFoundError, match="topic not found"):
        repository.get("unknown")


def test_repository_reports_invalid_packet(tmp_path: Path) -> None:
    invalid = json.loads((EVIDENCE_DIR / "sodium.json").read_text(encoding="utf-8"))
    invalid.pop("packet_id")
    (tmp_path / "invalid.json").write_text(
        json.dumps(invalid), encoding="utf-8"
    )

    with pytest.raises(EvidencePacketSchemaError, match="Invalid Evidence Packet"):
        EvidencePacketRepository(tmp_path).all()


@pytest.mark.parametrize(
    ("question", "expected"),
    [
        ("限钠饮食对高血压有帮助吗？", "sodium_and_hypertension"),
        ("低盐饮食应该怎么理解？", "sodium_and_hypertension"),
        ("减少钠摄入有助于降低血压吗？", "sodium_and_hypertension"),
        (
            "地中海饮食能降低心血管风险吗？",
            "mediterranean_diet_and_cardiovascular_risk",
        ),
        ("今天睡得好吗？", UNKNOWN_TOPIC),
        ("高血压患者应该如何运动？", UNKNOWN_TOPIC),
        (
            "鸡蛋会增加心血管疾病风险吗？",
            "egg_consumption_and_cardiovascular_risk",
        ),
        ("橄榄油对心血管有益吗？", UNKNOWN_TOPIC),
        ("每天适量喝咖啡对健康有什么影响？", "coffee_and_blood_pressure"),
        ("16:8 限时进食能帮助减重吗？", "time_restricted_eating_and_weight"),
        ("规律运动能改善睡眠吗？", "exercise_and_sleep_quality"),
        ("普通人怎样开始规律运动？", UNKNOWN_TOPIC),
        ("鸡蛋怎样搭配早餐？", UNKNOWN_TOPIC),
    ],
)
def test_topic_matcher(question: str, expected: str) -> None:
    assert TopicMatcher().match(question) == expected


@pytest.mark.parametrize(
    ("question", "topic"),
    [
        ("限钠饮食对高血压有帮助吗？", "sodium_and_hypertension"),
        (
            "地中海饮食与心血管风险有什么关系？",
            "mediterranean_diet_and_cardiovascular_risk",
        ),
    ],
)
def test_fast_path_uses_packet_and_all_citations_verify(
    repository: EvidencePacketRepository,
    question: str,
    topic: str,
) -> None:
    result = FastPath(repository).run(question, module_id="m-test")

    assert result is not None
    assert result.topic == topic
    assert result.module.props["topic"] == topic
    assert result.module.props["evidence_strength"] == result.packet.evidence_strength

    verifier = CitationVerifier(result.packet)
    for item in result.packet.evidence_items:
        citation = CitationReference(
            evidence_id=item.evidence_id,
            source_id=item.source_id,
            url=item.url,
        )
        assert verifier.verify_or_raise(
            CitedClaim(text=item.finding, citations=[citation])
        ).valid


def test_fast_path_does_not_guess_unknown_topic(
    repository: EvidencePacketRepository,
) -> None:
    assert FastPath(repository).run("如何改善睡眠？", module_id="m-test") is None
