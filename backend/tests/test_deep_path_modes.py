import json

import pytest
from fastapi.testclient import TestClient

from app.evidence import (
    CitationVerifier,
    DeepPath,
    EvidencePacketRepository,
    SafetyRouter,
)
from app.main import app


client = TestClient(app)


def orchestrate(question: str, mode: str) -> dict:
    response = client.post(
        "/api/v1/orchestrate",
        data={
            "session_id": "deep-path-test",
            "mode": mode,
            "text": question,
        },
    )
    assert response.status_code == 200
    return response.json()


def test_deep_path_builds_support_and_boundary_groups() -> None:
    question = "所有人都应该严格限盐吗？"
    safety = SafetyRouter().assess(question)
    result = DeepPath(EvidencePacketRepository()).run(
        question,
        module_id="m-deep",
        safety=safety,
    )

    assert result is not None
    assert result.dynamic_packet.queries.support_query.startswith(question)
    assert result.dynamic_packet.queries.boundary_query.startswith(question)
    assert result.dynamic_packet.support_evidence
    assert result.dynamic_packet.boundary_evidence
    assert result.answer.gate_status == "degraded"
    assert "不支持以下推断" in result.answer.conclusion

    verifier = CitationVerifier(result.packet)
    assert verifier.packet.packet_id == result.dynamic_packet.source_packet_id


def test_eviroute_keeps_ordinary_sodium_question_on_fast_path() -> None:
    body = orchestrate(
        "限钠饮食对高血压有帮助吗？",
        "eviroute_gate",
    )

    assert body["mode"] == "eviroute_gate"
    assert body["route"] == "fast_path"
    assert body["gate_status"] == "normal"
    assert body["evidence_count"] == 2
    verdict = body["module_plan"][0]["props"]["verdict"]
    assert body["support_evidence_count"] == len(verdict["supporting_evidence"])
    assert body["boundary_evidence_count"] == len(verdict["opposing_evidence"])


def test_eviroute_escalates_absolute_question_to_deep_path() -> None:
    body = orchestrate("所有人都应该严格限盐吗？", "eviroute_gate")
    props = body["module_plan"][0]["props"]

    assert body["route"] == "deep_path"
    assert body["gate_status"] == "degraded"
    assert body["support_evidence_count"] > 0
    assert body["boundary_evidence_count"] > 0
    assert props["dynamic_packet_id"].startswith("dynamic-")
    assert props["support_evidence"]
    assert props["boundary_evidence"]
    assert props["queries"]["support_query"]
    assert props["queries"]["boundary_query"]


@pytest.mark.parametrize(
    ("mode", "expected_route", "expected_gate"),
    [
        ("general", "general", "degraded"),
        ("rag", "rag", "normal"),
        ("always_deep", "deep_path", "normal"),
        ("eviroute_gate", "fast_path", "normal"),
    ],
)
def test_all_four_modes_execute(
    mode: str,
    expected_route: str,
    expected_gate: str,
) -> None:
    body = orchestrate("限钠饮食对高血压有帮助吗？", mode)

    assert body["mode"] == mode
    assert body["route"] == expected_route
    assert body["gate_status"] == expected_gate
    assert set(body["timing_ms"]) == {
        "route_ms",
        "retrieve_ms",
        "verify_ms",
        "total_ms",
    }
    assert all(value >= 0 for value in body["timing_ms"].values())


@pytest.mark.parametrize(
    "mode",
    ["general", "rag", "always_deep", "eviroute_gate"],
)
def test_high_risk_request_is_refused_before_every_mode(mode: str) -> None:
    body = orchestrate("高血压能不能停药只吃低盐？", mode)

    assert body["route"] == "safety_refusal"
    assert body["gate_status"] == "refused"
    assert body["evidence_count"] == 0
    assert body["timing_ms"]["retrieve_ms"] == 0
    assert body["timing_ms"]["verify_ms"] == 0


def test_deep_path_sse_contains_snapshot_and_gate_events() -> None:
    start = orchestrate("所有人都应该严格限盐吗？", "eviroute_gate")
    response = client.get(f"/api/v1/runs/{start['run_id']}/events")

    assert response.status_code == 200
    events = [
        json.loads(line.removeprefix("data: "))
        for line in response.text.splitlines()
        if line.startswith("data: ")
    ]
    event_types = [event["type"] for event in events]
    assert "route.selected" in event_types
    assert "evidence.snapshot" in event_types
    assert "gate.completed" in event_types

    route_event = next(event for event in events if event["type"] == "route.selected")
    snapshot = next(event for event in events if event["type"] == "evidence.snapshot")
    assert route_event["payload"]["route"] == "deep_path"
    assert snapshot["payload"]["support_evidence_count"] > 0
    assert snapshot["payload"]["boundary_evidence_count"] > 0
    assert snapshot["payload"]["queries"]["support_query"]
    assert snapshot["payload"]["queries"]["boundary_query"]
