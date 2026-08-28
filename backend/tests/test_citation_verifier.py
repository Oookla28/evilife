import json
from pathlib import Path

import pytest

from app.evidence import (
    CitedClaim,
    CitationReference,
    CitationVerificationError,
    CitationVerifier,
)
from app.schemas import EvidencePacket

ROOT = Path(__file__).resolve().parents[2]


def load_sodium_packet() -> EvidencePacket:
    path = ROOT / "data" / "evidence" / "sodium.json"
    return EvidencePacket.model_validate_json(path.read_text(encoding="utf-8"))


def citation(**overrides: str) -> CitationReference:
    values = {
        "evidence_id": "E2",
        "source_id": "COCHRANE_CD004022_2020",
        "url": "https://www.cochrane.org/evidence/CD004022_effect-low-salt-diet-blood-pressure-and-some-hormones-and-lipids-people-normal-and-elevated-blood",
    }
    values.update(overrides)
    return CitationReference(**values)


def issue_codes(error: CitationVerificationError) -> set[str]:
    return {issue.code for issue in error.result.issues}


def test_valid_citation_passes() -> None:
    verifier = CitationVerifier(load_sodium_packet())
    claim = CitedClaim(
        text="高血压人群的平均血压降幅为 5.7/2.9 mmHg。",
        citations=[citation()],
    )

    result = verifier.verify_or_raise(claim)

    assert result.valid is True
    assert result.issues == []


def test_fake_citation_is_rejected() -> None:
    verifier = CitationVerifier(load_sodium_packet())
    claim = CitedClaim(
        text="减少钠摄入可以降低血压。",
        citations=[citation(evidence_id="E99")],
    )

    with pytest.raises(CitationVerificationError) as captured:
        verifier.verify_or_raise(claim)

    assert "unknown_evidence_id" in issue_codes(captured.value)


def test_source_id_mismatch_is_rejected() -> None:
    verifier = CitationVerifier(load_sodium_packet())
    claim = CitedClaim(
        text="减少钠摄入可以降低血压。",
        citations=[citation(source_id="WHO_SODIUM_GUIDELINE_2012")],
    )

    with pytest.raises(CitationVerificationError) as captured:
        verifier.verify_or_raise(claim)

    assert "source_id_mismatch" in issue_codes(captured.value)


def test_packet_external_url_is_rejected() -> None:
    verifier = CitationVerifier(load_sodium_packet())
    claim = CitedClaim(
        text="减少钠摄入可以降低血压。",
        citations=[citation(url="https://example.org/not-in-packet")],
    )

    with pytest.raises(CitationVerificationError) as captured:
        verifier.verify_or_raise(claim)

    assert "packet_external_url" in issue_codes(captured.value)


def test_unsupported_exact_number_is_rejected() -> None:
    verifier = CitationVerifier(load_sodium_packet())
    claim = CitedClaim(
        text="减少钠摄入能让血压下降 37.2 mmHg。",
        citations=[citation()],
    )

    with pytest.raises(CitationVerificationError) as captured:
        verifier.verify_or_raise(claim)

    assert "unsupported_exact_number" in issue_codes(captured.value)
