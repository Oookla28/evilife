from fastapi.testclient import TestClient

from app.main import app
from app.main import _normalized_image_type
from app.schemas import EvidenceAnswer

client = TestClient(app)


def test_windows_octet_stream_image_type_is_recovered() -> None:
    assert _normalized_image_type(
        "application/octet-stream",
        "meal.jpg",
        b"\xff\xd8\xfffake-jpeg",
    ) == "image/jpeg"
    assert _normalized_image_type("", "clipboard.png", b"not-real-but-named") == "image/png"


def test_health() -> None:
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_orchestrate_text_contract() -> None:
    response = client.post(
        "/api/v1/orchestrate",
        data={
            "session_id": "test-session",
            "mode": "auto",
            "text": "限钠饮食对高血压是否真的有帮助？",
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["session_id"] == "test-session"
    assert body["request_id"].startswith("req-")
    assert body["run_id"].startswith("run-")
    assert body["gate_status"] == "normal"
    assert body["status"] == "running"
    assert body["module_plan"][0]["type"] == "EvidenceAnswer"
    assert body["module_plan"][0]["status"] == "ready"
    props = body["module_plan"][0]["props"]
    EvidenceAnswer.model_validate(props)
    assert props["packet_id"] == "packet-sodium-hypertension-v1"
    assert props["topic"] == "sodium_and_hypertension"
    assert props["evidence_strength"] == "high"
    assert props["citations"]
    assert props["evidence_mix"]["reliable_weight"] >= 0.84
    assert props["evidence_mix"]["general_weight"] <= 0.16
    assert {
        "conclusion",
        "gate_status",
        "evidence_strength",
        "explanation",
        "target_population",
        "non_target_population",
        "general_advice",
        "limitations",
        "citations",
    } <= props.keys()
    assert body["actions"] == []


def test_orchestrate_mediterranean_fast_path() -> None:
    response = client.post(
        "/api/v1/orchestrate",
        data={
            "session_id": "test-session",
            "mode": "auto",
            "text": "地中海饮食对心血管风险有什么证据？",
        },
    )

    assert response.status_code == 200
    props = response.json()["module_plan"][0]["props"]
    assert props["packet_id"] == "packet-mediterranean-cardiovascular-v1"
    assert props["topic"] == "mediterranean_diet_and_cardiovascular_risk"


def test_orchestrate_unknown_topic_uses_mock_fallback() -> None:
    response = client.post(
        "/api/v1/orchestrate",
        data={
            "session_id": "test-session",
            "mode": "auto",
            "text": "如何改善睡眠？",
        },
    )

    assert response.status_code == 200
    body = response.json()
    props = body["module_plan"][0]["props"]
    assert body["gate_status"] == "degraded"
    assert props["gate_status"] == "degraded"
    assert props["evidence_strength"] == "insufficient"
    assert props["citations"] == []
    assert "packet_id" not in props


def test_orchestrate_refuses_stopping_medication_for_low_salt() -> None:
    response = client.post(
        "/api/v1/orchestrate",
        data={
            "session_id": "test-session",
            "mode": "auto",
            "text": "高血压能不能停药只吃低盐？",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["gate_status"] == "refused"
    assert body["risk_level"] == "high"
    assert body["module_plan"][0]["type"] == "EvidenceAnswer"
    props = body["module_plan"][0]["props"]
    EvidenceAnswer.model_validate(props)
    assert props["gate_status"] == "refused"
    assert props["evidence_strength"] == "insufficient"
    assert props["citations"] == []
    assert "packet_id" not in props


def test_orchestrate_degrades_population_boundary() -> None:
    response = client.post(
        "/api/v1/orchestrate",
        data={
            "session_id": "test-session",
            "mode": "auto",
            "text": "孕妇高血压采用低盐饮食的证据充分吗？",
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body["gate_status"] == "degraded"
    assert body["risk_level"] == "medium"
    props = body["module_plan"][0]["props"]
    EvidenceAnswer.model_validate(props)
    assert props["gate_status"] == "degraded"
    assert props["packet_id"] == "packet-sodium-hypertension-v1"
    assert props["citations"]


def test_orchestrate_requires_input() -> None:
    response = client.post(
        "/api/v1/orchestrate",
        data={"session_id": "test-session", "mode": "auto"},
    )
    assert response.status_code == 422


def test_orchestrate_rejects_two_attachments() -> None:
    response = client.post(
        "/api/v1/orchestrate",
        data={"session_id": "test-session", "mode": "auto"},
        files={
            "image": ("meal.png", b"fake", "image/png"),
            "document": ("paper.pdf", b"fake", "application/pdf"),
        },
    )
    assert response.status_code == 422


def test_orchestrate_rejects_unsupported_or_empty_images() -> None:
    unsupported = client.post(
        "/api/v1/orchestrate",
        data={"session_id": "test-session", "mode": "auto"},
        files={"image": ("meal.gif", b"GIF89a", "image/gif")},
    )
    assert unsupported.status_code == 415

    empty = client.post(
        "/api/v1/orchestrate",
        data={"session_id": "test-session", "mode": "auto"},
        files={"image": ("meal.png", b"", "image/png")},
    )
    assert empty.status_code == 422


def test_sse_completes_run() -> None:
    start = client.post(
        "/api/v1/orchestrate",
        data={
            "session_id": "test-session",
            "mode": "auto",
            "text": "限钠饮食对高血压有帮助吗？",
        },
    ).json()
    response = client.get(f"/api/v1/runs/{start['run_id']}/events")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/event-stream")
    assert '"type": "run.started"' in response.text
    assert '"type": "route.selected"' in response.text
    assert '"route": "hybrid_fast_path"' in response.text
    assert '"type": "evidence.snapshot"' in response.text
    assert '"packet_id": "packet-sodium-hypertension-v1"' in response.text
    assert '"evidence_mix"' in response.text
    assert '"type": "module.ready"' in response.text
    assert '"type": "gate.completed"' in response.text
    assert '"status": "normal"' in response.text
    assert '"type": "run.completed"' in response.text

    status = client.get(f"/api/v1/runs/{start['run_id']}")
    assert status.status_code == 200
    assert status.json()["status"] == "completed"


def test_refused_sse_has_safety_route_without_evidence_snapshot() -> None:
    start = client.post(
        "/api/v1/orchestrate",
        data={
            "session_id": "test-session",
            "mode": "auto",
            "text": "高血压能不能停药只吃低盐？",
        },
    ).json()

    response = client.get(f"/api/v1/runs/{start['run_id']}/events")

    assert '"route": "safety_refusal"' in response.text
    assert '"type": "evidence.snapshot"' not in response.text
    assert '"type": "gate.completed"' in response.text
    assert '"status": "refused"' in response.text
