from fastapi.testclient import TestClient

import app.main as main_module
from app.main import app


client = TestClient(app)


def test_connector_registry_never_claims_native_platforms_are_connected() -> None:
    response = client.get("/api/v1/health-connectors")
    assert response.status_code == 200
    connectors = {item["id"]: item for item in response.json()}
    assert connectors["apple_healthkit"]["status"] == "requires_native_bridge"
    assert connectors["android_health_connect"]["status"] == "requires_native_bridge"
    assert connectors["huawei_health_kit"]["status"] == "requires_credentials"
    assert connectors["generic_import"]["status"] == "available"


def test_generic_ingest_forces_device_source_and_deduplicates() -> None:
    payload = {
        "consent_receipt": "consent-test-20260811",
        "observations": [
            {
                "external_id": "test-device-reading-20260811",
                "observation": {
                    "kind": "steps",
                    "value": 4321,
                    "source": "self_report",
                },
            }
        ],
    }
    first = client.post("/api/v1/health-connectors/generic_import/ingest", json=payload)
    second = client.post("/api/v1/health-connectors/generic_import/ingest", json=payload)
    assert first.status_code == 200
    assert first.json()["accepted"] == 1
    assert first.json()["records"][0]["source"] == "device"
    assert second.json()["accepted"] == 0
    assert second.json()["skipped"] == 1


def test_observation_can_be_deleted() -> None:
    created = client.post(
        "/api/v1/observations",
        json={"kind": "water_ml", "value": 123, "source": "self_report"},
    ).json()
    deleted = client.delete(f"/api/v1/observations/{created['id']}")
    assert deleted.status_code == 200
    assert deleted.json()["id"] == created["id"]
    assert client.delete(f"/api/v1/observations/{created['id']}").status_code == 404


def test_observation_batch_is_written_together() -> None:
    response = client.post(
        "/api/v1/observations/batch",
        json={
            "observations": [
                {"kind": "water_ml", "value": 450, "source": "self_report"},
                {"kind": "steps", "value": 3210, "source": "self_report"},
            ]
        },
    )
    assert response.status_code == 200
    assert [item["kind"] for item in response.json()] == ["water_ml", "steps"]


def test_profile_analysis_has_safe_fallback(monkeypatch) -> None:
    monkeypatch.setattr(main_module, "_ai_provider", None)
    response = client.post("/api/v1/profile/analyze")
    assert response.status_code == 200
    body = response.json()
    assert body["source"] == "deterministic_fallback"
    assert len(body["cards"]) == 1
    card = body["cards"][0]
    assert card["title"] == "综合健康分析"
    assert len(card["preview"]) >= 12
    assert any(item["label"] == "需关注信号" for item in card["details"])
    assert any(item["label"] == "生活建议" for item in card["details"])
