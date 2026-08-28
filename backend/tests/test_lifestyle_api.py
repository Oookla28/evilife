from datetime import datetime, timezone

from fastapi.testclient import TestClient

from app.main import app
from app.lifestyle import LifestyleStore, ObservationCreate


client = TestClient(app)


def test_fasting_timer_start_active_end_round_trip() -> None:
    started = client.post("/api/v1/fasts/start", json={"goal_hours": 16})
    assert started.status_code == 200
    record = started.json()
    assert record["status"] == "active"
    assert record["goal_hours"] == 16

    duplicate = client.post("/api/v1/fasts/start", json={"goal_hours": 14})
    assert duplicate.status_code == 409

    active = client.get("/api/v1/fasts/active")
    assert active.json()["id"] == record["id"]

    ended = client.post(f"/api/v1/fasts/{record['id']}/end")
    assert ended.status_code == 200
    assert ended.json()["status"] == "completed"
    assert ended.json()["end_at"] is not None
    assert client.get("/api/v1/fasts/active").json() is None


def test_confirmed_meal_is_visible_in_today_summary() -> None:
    action_id = "action-meal-test"
    response = client.post(
        f"/api/v1/actions/{action_id}/confirm",
        json={
            "run_id": "run-test",
            "confirmed": True,
            "client_action_id": action_id,
            "edited_items": [
                {
                    "id": "food-1",
                    "name": "燕麦粥",
                    "portion": "1 碗",
                    "estimated_calories": [180, 240],
                    "uncertainty": "份量来自图片估算",
                }
            ],
            "estimated_total_calories": [180, 240],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["affected_resource"]["type"] == "meal_record"

    today = datetime.now(timezone.utc).date().isoformat()
    summary = client.get("/api/v1/today", params={"date": today})
    assert summary.status_code == 200
    meals = summary.json()["meals"]
    assert any(meal["action_id"] == action_id for meal in meals)
    assert next(
        meal for meal in meals if meal["action_id"] == action_id
    )["estimated_total_calories"] == [180, 240]


def test_rejected_meal_is_not_written() -> None:
    action_id = "action-meal-rejected"
    response = client.post(
        f"/api/v1/actions/{action_id}/confirm",
        json={
            "run_id": "run-test",
            "confirmed": False,
            "client_action_id": action_id,
        },
    )
    assert response.status_code == 200
    assert response.json()["status"] == "cancelled"


def test_observation_round_trip_and_today_summary() -> None:
    created = client.post(
        "/api/v1/observations",
        json={
            "kind": "water_ml",
            "value": 350,
            "source": "self_report",
            "note": "早餐后",
        },
    )
    assert created.status_code == 200
    record = created.json()
    assert record["kind"] == "water_ml"
    assert record["value"] == 350
    assert record["source"] == "self_report"

    listed = client.get(
        "/api/v1/observations",
        params={"kind": "water_ml", "limit": 10},
    )
    assert listed.status_code == 200
    assert any(item["id"] == record["id"] for item in listed.json())

    today = datetime.now(timezone.utc).date().isoformat()
    summary = client.get("/api/v1/today", params={"date": today})
    assert any(item["id"] == record["id"] for item in summary.json()["observations"])


def test_observation_rejects_invalid_mood_score() -> None:
    response = client.post(
        "/api/v1/observations",
        json={"kind": "mood_score", "value": 8, "source": "self_report"},
    )
    assert response.status_code == 422


def test_lifestyle_store_persists_observations_across_restart(tmp_path) -> None:
    storage = tmp_path / "lifestyle.json"
    first = LifestyleStore(storage)
    saved = first.add_observation(
        ObservationCreate(
            kind="weight_kg",
            value=69.2,
            source="self_report",
        )
    )

    restored = LifestyleStore(storage)
    records = restored.list_observations(kind="weight_kg")
    assert records[0].id == saved.id
    assert records[0].value == 69.2
