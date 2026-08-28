import json
from pathlib import Path

from jsonschema import Draft202012Validator

from app.schemas import EvidencePacket

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_DIR = ROOT / "data" / "evidence"
CONTRACT = ROOT / "contracts" / "evidence-packet.schema.json"


def test_golden_packets_match_pydantic_and_json_schema() -> None:
    schema = json.loads(CONTRACT.read_text(encoding="utf-8"))
    validator = Draft202012Validator(
        schema,
        format_checker=Draft202012Validator.FORMAT_CHECKER,
    )

    paths = sorted(EVIDENCE_DIR.glob("*.json"))
    assert {path.name for path in paths} == {
        "coffee-blood-pressure.json",
        "egg-cardiovascular.json",
        "exercise-sleep.json",
        "mediterranean.json",
        "sodium.json",
        "time-restricted-eating.json",
    }

    for path in paths:
        raw = json.loads(path.read_text(encoding="utf-8"))
        packet = EvidencePacket.model_validate(raw)
        validator.validate(packet.model_dump(mode="json", exclude_none=True))


def test_every_golden_evidence_item_has_traceability_fields() -> None:
    required = {
        "source_id",
        "evidence_id",
        "title",
        "year",
        "source_type",
        "organization",
        "url",
        "population",
        "finding",
        "limitations",
        "supports",
        "does_not_support",
    }
    for path in EVIDENCE_DIR.glob("*.json"):
        raw = json.loads(path.read_text(encoding="utf-8"))
        for item in raw["evidence_items"]:
            assert required <= item.keys()
            assert all(item[field] for field in required)


def test_all_user_facing_packet_content_contains_chinese() -> None:
    def contains_chinese(value: str) -> bool:
        return any("\u3400" <= character <= "\u9fff" for character in value)

    for path in EVIDENCE_DIR.glob("*.json"):
        packet = EvidencePacket.model_validate_json(path.read_text(encoding="utf-8"))
        for item in packet.evidence_items:
            user_facing = [
                item.title,
                item.population,
                item.finding,
                item.limitations,
                *item.supports,
                *item.does_not_support,
            ]
            assert all(contains_chinese(text) for text in user_facing)
        assert all(contains_chinese(text) for text in packet.safe_actions)
        assert all(contains_chinese(text) for text in packet.unsafe_actions)
        assert all(contains_chinese(text) for text in packet.missing_evidence or [])
