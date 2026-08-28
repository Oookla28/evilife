from __future__ import annotations

import hashlib
from datetime import datetime, timezone

from app.auth import AuthService, LoginRequest, RegisterRequest
from app.db.connection import connect
from app.db.migrate import migrate
from app.db.runtime_repository import RuntimeRepository


def test_migrations_are_repeatable_and_foreign_keys_are_clean(tmp_path) -> None:
    path = tmp_path / "runtime.sqlite3"
    assert migrate(path) == ["001", "002", "003", "004"]
    assert migrate(path) == []
    repository = RuntimeRepository(path)
    report = repository.integrity()
    assert report["integrity_check"] == "ok"
    assert report["foreign_key_check"] == []
    assert [item["version"] for item in report["migrations"]] == [
        "001", "002", "003", "004"
    ]


def test_passwords_are_argon2id_and_sessions_store_only_a_digest(tmp_path) -> None:
    repository = RuntimeRepository(tmp_path / "runtime.sqlite3")
    auth = AuthService(repository)
    registered = auth.register(
        RegisterRequest(
            email="doctor@example.com",
            display_name="循证医生",
            password="Evidence2026",
        )
    )
    authenticated = auth.authenticate(
        LoginRequest(email="DOCTOR@example.com", password="Evidence2026")
    )
    assert authenticated is not None and authenticated.id == registered.id
    user = repository.get_user_by_id(registered.id)
    assert user is not None
    assert user["password_hash"].startswith("$argon2id$")
    assert "Evidence2026" not in user["password_hash"]

    token, expires_at = auth.issue_session(registered.id, user_agent="pytest")
    with connect(repository.path) as connection:
        session = connection.execute("SELECT token_hash FROM auth_sessions").fetchone()
    assert session is not None
    assert session["token_hash"] == hashlib.sha256(token.encode()).hexdigest()
    assert token != session["token_hash"]
    assert auth.resolve(token) is not None
    assert expires_at > datetime.now(timezone.utc)


def test_conversations_are_user_scoped_and_persist_after_reopen(tmp_path) -> None:
    path = tmp_path / "runtime.sqlite3"
    repository = RuntimeRepository(path)
    auth = AuthService(repository)
    alice = auth.register(
        RegisterRequest(email="alice@example.com", display_name="Alice", password="Health2026")
    )
    bob = auth.register(
        RegisterRequest(email="bob@example.com", display_name="Bob", password="Health2026")
    )
    repository.upsert_conversation(
        user_id=alice.id,
        session_id="case-001",
        title="限钠与血压",
        mode="professional",
        messages=[{"id": "m1", "role": "user", "content": "限钠有效吗？"}],
    )
    assert repository.list_conversations(bob.id) == []

    reopened = RuntimeRepository(path)
    items = reopened.list_conversations(alice.id)
    assert items[0]["mode"] == "professional"
    assert items[0]["messages"][0]["content"] == "限钠有效吗？"
    assert reopened.delete_conversation(bob.id, "case-001") is False
    assert reopened.delete_conversation(alice.id, "case-001") is True


def test_device_import_is_idempotent_and_updates_daily_metrics(tmp_path) -> None:
    repository = RuntimeRepository(tmp_path / "runtime.sqlite3")
    subject = "sub-watch"
    item = (
        "apple-step-2026-08-28",
        {
            "kind": "steps",
            "value": 8632,
            "note": None,
            "observed_at": "2026-08-28T08:00:00+00:00",
        },
    )
    accepted, skipped, _ = repository.import_device_observations(
        subject, "apple_health", [item]
    )
    assert (accepted, skipped) == (1, 0)
    accepted, skipped, _ = repository.import_device_observations(
        subject, "apple_health", [item]
    )
    assert (accepted, skipped) == (0, 1)
    with connect(repository.path) as connection:
        metric = connection.execute(
            "SELECT value, unit, source FROM health_daily_metrics WHERE subject_id = ?",
            (subject,),
        ).fetchone()
    assert metric is not None
    assert dict(metric) == {"value": 8632.0, "unit": "count", "source": "apple_health"}


def test_report_upload_deduplicates_by_user_and_checksum(tmp_path) -> None:
    repository = RuntimeRepository(tmp_path / "runtime.sqlite3")
    checksum = hashlib.sha256(b"synthetic medical report").hexdigest()
    first, created = repository.create_report(
        "sub-report",
        sha256=checksum,
        mime_type="application/pdf",
        size_bytes=24,
        storage_key="reports/sub-report/report.pdf",
    )
    second, created_again = repository.create_report(
        "sub-report",
        sha256=checksum,
        mime_type="application/pdf",
        size_bytes=24,
        storage_key="reports/sub-report/duplicate.pdf",
    )
    assert created is True
    assert created_again is False
    assert second["id"] == first["id"]
