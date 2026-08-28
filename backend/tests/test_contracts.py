import json
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[2]
CONTRACTS = ROOT / "contracts"


def load_schema(name: str) -> dict:
    return json.loads((CONTRACTS / name).read_text(encoding="utf-8"))


def test_contract_schemas_are_valid() -> None:
    for name in (
        "module-plan.schema.json",
        "stream-events.schema.json",
        "evidence-packet.schema.json",
        "verdict.schema.json",
    ):
        Draft202012Validator.check_schema(load_schema(name))


def test_verdict_schema_validates_realistic_instance() -> None:
    schema = load_schema("verdict.schema.json")
    instance = {
        "verdict": "partly_true",
        "confidence": 0.74,
        "evidence_grade": "high",
        "claim": "所有人都应该严格限盐",
        "short_reason": "存在支持证据，但同样存在边界、冲突或局限证据。",
        "applies_to": ["高血压人群"],
        "does_not_apply_to": ["低血压人群"],
        "supporting_evidence": [
            {
                "evidence_id": "E1-S1",
                "source_id": "WHO_SODIUM_GUIDELINE_2012",
                "title": "成人和儿童钠摄入指南",
                "year": 2012,
                "source_type": "指南",
                "organization": "世界卫生组织",
                "direction": "support",
                "finding": "减少过量钠摄入是有证据支持的群体降压策略。",
                "url": "https://www.who.int/publications/i/item/9789241504836",
                "channel": "curated_database",
                "reliability_score": 0.97,
            }
        ],
        "opposing_evidence": [
            {
                "evidence_id": "W1-A",
                "source_id": "W1",
                "title": "Live source 1",
                "year": 2025,
                "source_type": "Systematic Review",
                "organization": "Test Journal",
                "direction": "against",
                "finding": "conflicting null-result snippet",
                "url": "https://example.test/live/1",
                "channel": "live_medical_search",
                "reliability_score": 0.95,
            }
        ],
        "uncertainty": ["个体反应存在差异"],
        "last_updated": "2026-08-11",
    }
    Draft202012Validator(schema).validate(instance)


def test_module_plan_example_matches_contract() -> None:
    schema = load_schema("module-plan.schema.json")
    instance = {
        "module_id": "m1",
        "type": "EvidenceAnswer",
        "version": "1",
        "priority": 1,
        "status": "ready",
        "props": {"conclusion": "mock"},
    }
    Draft202012Validator(schema).validate(instance)


def test_stream_event_example_matches_contract() -> None:
    schema = load_schema("stream-events.schema.json")
    instance = {
        "event_id": "evt-001",
        "request_id": "req-001",
        "run_id": "run-001",
        "type": "run.completed",
        "timestamp": "2026-08-11T08:00:00+00:00",
        "payload": {"status": "completed"},
    }
    Draft202012Validator(schema, format_checker=Draft202012Validator.FORMAT_CHECKER).validate(instance)
