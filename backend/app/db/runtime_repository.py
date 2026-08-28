from __future__ import annotations

import json
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Sequence
from uuid import uuid4

from .connection import connect, runtime_db_path, transaction
from .migrate import migrate


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def new_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex[:16]}"


class RuntimeRepository:
    """SQLite repository for user-owned runtime data.

    The authoritative medical corpus remains a separate, read-only database.
    This repository stores only logical evidence identifiers, never cross-DB
    foreign keys.
    """

    def __init__(self, path: str | Path | None = None) -> None:
        self.path = Path(path).expanduser().resolve() if path is not None else runtime_db_path()
        migrate(self.path)

    def ensure_subject(
        self,
        subject_id: str,
        *,
        display_name: str = "体验用户",
        timezone_name: str = "Asia/Shanghai",
    ) -> str:
        now = utc_now()
        with transaction(self.path) as connection:
            connection.execute(
                """
                INSERT INTO subjects(id, display_name, timezone, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                    display_name = CASE
                        WHEN subjects.display_name = '体验用户' THEN excluded.display_name
                        ELSE subjects.display_name
                    END,
                    updated_at = excluded.updated_at
                """,
                (subject_id, display_name, timezone_name, now, now),
            )
        return subject_id

    # Authentication -----------------------------------------------------

    def create_user(self, email: str, display_name: str, password_hash: str) -> dict[str, Any]:
        user_id = new_id("usr")
        subject_id = new_id("sub")
        now = utc_now()
        normalized_email = email.strip().lower()
        with transaction(self.path) as connection:
            connection.execute(
                "INSERT INTO subjects(id, display_name, timezone, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
                (subject_id, display_name, "Asia/Shanghai", now, now),
            )
            try:
                connection.execute(
                    """
                    INSERT INTO users(
                        id, subject_id, email, display_name, password_hash,
                        password_algorithm, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, 'argon2id', ?, ?)
                    """,
                    (user_id, subject_id, normalized_email, display_name, password_hash, now, now),
                )
            except sqlite3.IntegrityError as exc:
                raise ValueError("该邮箱已经注册") from exc
        return self.get_user_by_id(user_id) or {}

    def get_user_by_email(self, email: str) -> dict[str, Any] | None:
        with connect(self.path) as connection:
            row = connection.execute(
                "SELECT * FROM users WHERE email = ?",
                (email.strip().lower(),),
            ).fetchone()
        return dict(row) if row is not None else None

    def get_user_by_id(self, user_id: str) -> dict[str, Any] | None:
        with connect(self.path) as connection:
            row = connection.execute("SELECT * FROM users WHERE id = ?", (user_id,)).fetchone()
        return dict(row) if row is not None else None

    def count_users(self) -> int:
        with connect(self.path) as connection:
            return int(connection.execute("SELECT COUNT(*) FROM users").fetchone()[0])

    def update_password_hash(self, user_id: str, password_hash: str) -> None:
        with transaction(self.path) as connection:
            connection.execute(
                "UPDATE users SET password_hash = ?, updated_at = ? WHERE id = ?",
                (password_hash, utc_now(), user_id),
            )

    def mark_login(self, user_id: str) -> None:
        now = utc_now()
        with transaction(self.path) as connection:
            connection.execute(
                "UPDATE users SET last_login_at = ?, updated_at = ? WHERE id = ?",
                (now, now, user_id),
            )

    def create_auth_session(
        self,
        user_id: str,
        token_hash: str,
        expires_at: str,
        *,
        user_agent: str | None,
    ) -> str:
        session_id = new_id("ses")
        now = utc_now()
        with transaction(self.path) as connection:
            connection.execute(
                """
                INSERT INTO auth_sessions(
                    id, user_id, token_hash, created_at, expires_at, last_seen_at, user_agent
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (session_id, user_id, token_hash, now, expires_at, now, user_agent),
            )
        return session_id

    def resolve_auth_session(self, token_hash: str, now: str) -> dict[str, Any] | None:
        with connect(self.path) as connection:
            row = connection.execute(
                """
                SELECT
                    s.id AS session_id, s.expires_at,
                    u.id AS user_id, u.subject_id, u.email, u.display_name, u.is_active
                FROM auth_sessions s
                JOIN users u ON u.id = s.user_id
                WHERE s.token_hash = ?
                  AND s.revoked_at IS NULL
                  AND s.expires_at > ?
                  AND u.is_active = 1
                """,
                (token_hash, now),
            ).fetchone()
        return dict(row) if row is not None else None

    def touch_auth_session(self, session_id: str) -> None:
        with transaction(self.path, immediate=False) as connection:
            connection.execute(
                "UPDATE auth_sessions SET last_seen_at = ? WHERE id = ?",
                (utc_now(), session_id),
            )

    def revoke_auth_session(self, token_hash: str) -> None:
        with transaction(self.path) as connection:
            connection.execute(
                "UPDATE auth_sessions SET revoked_at = ? WHERE token_hash = ? AND revoked_at IS NULL",
                (utc_now(), token_hash),
            )

    # Conversations ------------------------------------------------------

    def upsert_conversation(
        self,
        *,
        user_id: str,
        session_id: str,
        title: str,
        mode: str,
        messages: Sequence[dict[str, Any]],
    ) -> dict[str, Any]:
        now = utc_now()
        serialized = json.dumps(list(messages), ensure_ascii=False, separators=(",", ":"))
        with transaction(self.path) as connection:
            existing = connection.execute(
                "SELECT id, created_at FROM conversations WHERE user_id = ? AND session_id = ?",
                (user_id, session_id),
            ).fetchone()
            conversation_id = existing["id"] if existing is not None else new_id("conv")
            created_at = existing["created_at"] if existing is not None else now
            connection.execute(
                """
                INSERT INTO conversations(
                    id, user_id, session_id, title, mode, messages_json, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, session_id) DO UPDATE SET
                    title = excluded.title,
                    mode = excluded.mode,
                    messages_json = excluded.messages_json,
                    updated_at = excluded.updated_at
                """,
                (conversation_id, user_id, session_id, title, mode, serialized, created_at, now),
            )
        return self.get_conversation(user_id, session_id) or {}

    def get_conversation(self, user_id: str, session_id: str) -> dict[str, Any] | None:
        with connect(self.path) as connection:
            row = connection.execute(
                "SELECT * FROM conversations WHERE user_id = ? AND session_id = ?",
                (user_id, session_id),
            ).fetchone()
        return self._conversation(row) if row is not None else None

    def list_conversations(self, user_id: str, limit: int = 50) -> list[dict[str, Any]]:
        with connect(self.path) as connection:
            rows = connection.execute(
                "SELECT * FROM conversations WHERE user_id = ? ORDER BY updated_at DESC LIMIT ?",
                (user_id, limit),
            ).fetchall()
        return [self._conversation(row) for row in rows]

    def delete_conversation(self, user_id: str, session_id: str) -> bool:
        with transaction(self.path) as connection:
            cursor = connection.execute(
                "DELETE FROM conversations WHERE user_id = ? AND session_id = ?",
                (user_id, session_id),
            )
        return cursor.rowcount > 0

    @staticmethod
    def _conversation(row: sqlite3.Row) -> dict[str, Any]:
        item = dict(row)
        item["messages"] = json.loads(item.pop("messages_json"))
        return item

    # Lifestyle ----------------------------------------------------------

    def start_fast(self, subject_id: str, goal_hours: float) -> dict[str, Any]:
        self.ensure_subject(subject_id)
        record_id = new_id("fast")
        now = utc_now()
        try:
            with transaction(self.path) as connection:
                connection.execute(
                    """
                    INSERT INTO fasts(id, subject_id, start_at, goal_hours, status, created_at)
                    VALUES (?, ?, ?, ?, 'active', ?)
                    """,
                    (record_id, subject_id, now, goal_hours, now),
                )
        except sqlite3.IntegrityError as exc:
            raise ValueError("an active timer already exists") from exc
        return self.get_fast(subject_id, record_id) or {}

    def get_fast(self, subject_id: str, fast_id: str) -> dict[str, Any] | None:
        with connect(self.path) as connection:
            row = connection.execute(
                "SELECT * FROM fasts WHERE subject_id = ? AND id = ?",
                (subject_id, fast_id),
            ).fetchone()
        return dict(row) if row is not None else None

    def active_fast(self, subject_id: str) -> dict[str, Any] | None:
        with connect(self.path) as connection:
            row = connection.execute(
                "SELECT * FROM fasts WHERE subject_id = ? AND status = 'active' ORDER BY start_at DESC LIMIT 1",
                (subject_id,),
            ).fetchone()
        return dict(row) if row is not None else None

    def end_fast(self, subject_id: str, fast_id: str) -> dict[str, Any]:
        now = utc_now()
        with transaction(self.path) as connection:
            cursor = connection.execute(
                """
                UPDATE fasts SET end_at = ?, status = 'completed'
                WHERE id = ? AND subject_id = ? AND status = 'active'
                """,
                (now, fast_id, subject_id),
            )
            if cursor.rowcount != 1:
                raise KeyError(fast_id)
        return self.get_fast(subject_id, fast_id) or {}

    def list_fasts(self, subject_id: str, limit: int = 20) -> list[dict[str, Any]]:
        with connect(self.path) as connection:
            rows = connection.execute(
                "SELECT * FROM fasts WHERE subject_id = ? ORDER BY start_at DESC LIMIT ?",
                (subject_id, limit),
            ).fetchall()
        return [dict(row) for row in rows]

    def create_meal(
        self,
        subject_id: str,
        *,
        action_id: str,
        items: Sequence[dict[str, Any]],
        calorie_range: tuple[int, int],
        calorie_center: int,
    ) -> dict[str, Any]:
        self.ensure_subject(subject_id)
        meal_id = new_id("meal")
        now = utc_now()
        with transaction(self.path) as connection:
            existing = connection.execute(
                "SELECT id FROM meals WHERE subject_id = ? AND action_id = ?",
                (subject_id, action_id),
            ).fetchone()
            if existing is not None:
                meal_id = existing["id"]
            else:
                connection.execute(
                    """
                    INSERT INTO meals(
                        id, subject_id, action_id, created_at, calories_low,
                        calories_high, calories_center, status
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 'confirmed')
                    """,
                    (meal_id, subject_id, action_id, now, calorie_range[0], calorie_range[1], calorie_center),
                )
                for item in items:
                    grams = item.get("portion_grams")
                    connection.execute(
                        """
                        INSERT INTO meal_items(
                            id, meal_id, name, portion, portion_grams_low, portion_grams_high,
                            calories_low, calories_high, calories_center, confidence,
                            reference_basis, uncertainty
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            item.get("id") or new_id("food"), meal_id, item["name"], item["portion"],
                            grams[0] if grams else None, grams[1] if grams else None,
                            item["estimated_calories"][0], item["estimated_calories"][1],
                            item["estimated_calories_center"], item.get("confidence"),
                            item.get("reference_basis"), item.get("uncertainty"),
                        ),
                    )
        return self.get_meal(subject_id, meal_id) or {}

    def get_meal(self, subject_id: str, meal_id: str) -> dict[str, Any] | None:
        with connect(self.path) as connection:
            row = connection.execute(
                "SELECT * FROM meals WHERE subject_id = ? AND id = ?",
                (subject_id, meal_id),
            ).fetchone()
            if row is None:
                return None
            items = connection.execute(
                "SELECT * FROM meal_items WHERE meal_id = ? ORDER BY rowid",
                (meal_id,),
            ).fetchall()
        result = dict(row)
        result["items"] = [dict(item) for item in items]
        return result

    def list_meals(self, subject_id: str, selected_date: date | None = None) -> list[dict[str, Any]]:
        sql = "SELECT id FROM meals WHERE subject_id = ?"
        params: list[Any] = [subject_id]
        if selected_date is not None:
            sql += " AND substr(created_at, 1, 10) = ?"
            params.append(selected_date.isoformat())
        sql += " ORDER BY created_at DESC"
        with connect(self.path) as connection:
            ids = [row["id"] for row in connection.execute(sql, params).fetchall()]
        return [item for meal_id in ids if (item := self.get_meal(subject_id, meal_id))]

    def add_observation(
        self,
        subject_id: str,
        payload: dict[str, Any],
    ) -> tuple[dict[str, Any], bool]:
        self.ensure_subject(subject_id)
        observation_id = payload.get("id") or new_id("obs")
        observed_at = payload["observed_at"]
        now = utc_now()
        with transaction(self.path) as connection:
            try:
                connection.execute(
                    """
                    INSERT INTO observations(
                        id, subject_id, kind, value, note, source, observed_at,
                        connector_id, external_id, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        observation_id, subject_id, payload["kind"], payload.get("value"),
                        payload.get("note"), payload["source"], observed_at,
                        payload.get("connector_id"), payload.get("external_id"), now,
                    ),
                )
                created = True
            except sqlite3.IntegrityError:
                connector_id = payload.get("connector_id")
                external_id = payload.get("external_id")
                if not connector_id or not external_id:
                    raise
                existing = connection.execute(
                    """
                    SELECT * FROM observations
                    WHERE subject_id = ? AND connector_id = ? AND external_id = ?
                    """,
                    (subject_id, connector_id, external_id),
                ).fetchone()
                if existing is None:
                    raise
                return dict(existing), False
        return self.get_observation(subject_id, observation_id) or {}, created

    def add_observations(
        self,
        subject_id: str,
        payloads: Sequence[dict[str, Any]],
        *,
        sync_run_id: str | None = None,
    ) -> tuple[list[dict[str, Any]], int, int]:
        self.ensure_subject(subject_id)
        now = utc_now()
        accepted = 0
        skipped = 0
        records: list[dict[str, Any]] = []
        with transaction(self.path) as connection:
            for payload in payloads:
                observation_id = payload.get("id") or new_id("obs")
                try:
                    connection.execute(
                        """
                        INSERT INTO observations(
                            id, subject_id, kind, value, note, source, observed_at,
                            connector_id, external_id, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """,
                        (
                            observation_id, subject_id, payload["kind"], payload.get("value"),
                            payload.get("note"), payload["source"], payload["observed_at"],
                            payload.get("connector_id"), payload.get("external_id"), now,
                        ),
                    )
                    accepted += 1
                    row = connection.execute(
                        "SELECT * FROM observations WHERE id = ?", (observation_id,)
                    ).fetchone()
                    if payload["source"] == "device" and payload.get("value") is not None:
                        unit = {
                            "steps": "count",
                            "water_ml": "ml",
                            "sleep_minutes": "min",
                            "weight_kg": "kg",
                            "waist_cm": "cm",
                            "resting_heart_rate": "count/min",
                            "mood_score": "score",
                        }.get(payload["kind"], "value")
                        metric_id = new_id("metric")
                        connection.execute(
                            """
                            INSERT INTO health_daily_metrics(
                                id, subject_id, sync_run_id, metric_date, metric_type,
                                value, unit, source, created_at, updated_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                            ON CONFLICT(subject_id, metric_date, metric_type, source) DO UPDATE SET
                                value = excluded.value,
                                unit = excluded.unit,
                                sync_run_id = excluded.sync_run_id,
                                updated_at = excluded.updated_at
                            """,
                            (
                                metric_id, subject_id, sync_run_id, payload["observed_at"][:10],
                                payload["kind"], payload["value"], unit,
                                payload.get("connector_id") or "device", now, now,
                            ),
                        )
                except sqlite3.IntegrityError:
                    connector_id = payload.get("connector_id")
                    external_id = payload.get("external_id")
                    if not connector_id or not external_id:
                        raise
                    row = connection.execute(
                        """
                        SELECT * FROM observations
                        WHERE subject_id = ? AND connector_id = ? AND external_id = ?
                        """,
                        (subject_id, connector_id, external_id),
                    ).fetchone()
                    if row is None:
                        raise
                    skipped += 1
                records.append(dict(row))
        return records, accepted, skipped

    def import_device_observations(
        self,
        subject_id: str,
        connector_id: str,
        items: Sequence[tuple[str, dict[str, Any]]],
    ) -> tuple[int, int, str]:
        sync_id = new_id("sync")
        started = utc_now()
        self.ensure_subject(subject_id)
        with transaction(self.path) as connection:
            connection.execute(
                """
                INSERT INTO health_sync_runs(
                    id, subject_id, connector_id, status, received, started_at
                ) VALUES (?, ?, ?, 'running', ?, ?)
                """,
                (sync_id, subject_id, connector_id, len(items), started),
            )
        payloads = [
            {
                **payload,
                "source": "device",
                "connector_id": connector_id,
                "external_id": external_id,
            }
            for external_id, payload in items
        ]
        try:
            _, accepted, skipped = self.add_observations(
                subject_id, payloads, sync_run_id=sync_id
            )
        except Exception as exc:
            with transaction(self.path) as connection:
                connection.execute(
                    "UPDATE health_sync_runs SET status = 'failed', error = ?, completed_at = ? WHERE id = ?",
                    (type(exc).__name__, utc_now(), sync_id),
                )
            raise
        with transaction(self.path) as connection:
            connection.execute(
                """
                UPDATE health_sync_runs
                SET status = 'completed', accepted = ?, skipped = ?, completed_at = ?
                WHERE id = ?
                """,
                (accepted, skipped, utc_now(), sync_id),
            )
        return accepted, skipped, sync_id

    def get_observation(self, subject_id: str, observation_id: str) -> dict[str, Any] | None:
        with connect(self.path) as connection:
            row = connection.execute(
                "SELECT * FROM observations WHERE subject_id = ? AND id = ?",
                (subject_id, observation_id),
            ).fetchone()
        return dict(row) if row is not None else None

    def list_observations(
        self,
        subject_id: str,
        *,
        kind: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        sql = "SELECT * FROM observations WHERE subject_id = ?"
        params: list[Any] = [subject_id]
        if kind is not None:
            sql += " AND kind = ?"
            params.append(kind)
        sql += " ORDER BY observed_at DESC LIMIT ?"
        params.append(limit)
        with connect(self.path) as connection:
            rows = connection.execute(sql, params).fetchall()
        return [dict(row) for row in rows]

    def delete_observation(self, subject_id: str, observation_id: str) -> dict[str, Any]:
        existing = self.get_observation(subject_id, observation_id)
        if existing is None:
            raise KeyError(observation_id)
        with transaction(self.path) as connection:
            connection.execute(
                "DELETE FROM observations WHERE subject_id = ? AND id = ?",
                (subject_id, observation_id),
            )
        return existing

    # Reports and analysis ----------------------------------------------

    def create_report(
        self,
        subject_id: str,
        *,
        sha256: str,
        mime_type: str,
        size_bytes: int,
        storage_key: str,
        retention_until: str | None = None,
    ) -> tuple[dict[str, Any], bool]:
        self.ensure_subject(subject_id)
        report_id = new_id("rpt")
        with transaction(self.path) as connection:
            existing = connection.execute(
                "SELECT * FROM reports WHERE subject_id = ? AND sha256 = ?",
                (subject_id, sha256),
            ).fetchone()
            if existing is not None:
                return dict(existing), False
            now = utc_now()
            connection.execute(
                """
                INSERT INTO reports(
                    id, subject_id, sha256, mime_type, size_bytes, storage_key,
                    status, retention_until, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'uploaded', ?, ?)
                """,
                (report_id, subject_id, sha256, mime_type, size_bytes, storage_key, retention_until, now),
            )
        return self.get_report(subject_id, report_id) or {}, True

    def get_report(self, subject_id: str, report_id: str) -> dict[str, Any] | None:
        with connect(self.path) as connection:
            row = connection.execute(
                "SELECT * FROM reports WHERE subject_id = ? AND id = ?",
                (subject_id, report_id),
            ).fetchone()
        return dict(row) if row is not None else None

    def save_report_analysis(
        self,
        subject_id: str,
        report_id: str,
        *,
        model: str,
        summary: str,
        items: list[dict[str, Any]],
        limitations: list[str],
    ) -> None:
        run_id = new_id("ana")
        now = utc_now()
        with transaction(self.path) as connection:
            connection.execute(
                "UPDATE reports SET status = 'analyzed' WHERE id = ? AND subject_id = ?",
                (report_id, subject_id),
            )
            connection.execute(
                """INSERT INTO analysis_runs(id, subject_id, report_id, kind, status, model,
                   prompt_version, created_at, completed_at) VALUES (?, ?, ?, 'medical_report',
                   'completed', ?, 'report-v1', ?, ?)""",
                (run_id, subject_id, report_id, model, now, now),
            )
            for item in items:
                connection.execute(
                    """INSERT INTO lab_items(id, report_id, item_name, value_text, unit,
                       reference_range, confirmed, created_at) VALUES (?, ?, ?, ?, ?, ?, 0, ?)""",
                    (new_id("lab"), report_id, item["name"], item.get("value", ""),
                     item.get("unit", ""), item.get("reference_range", ""), now),
                )
            connection.execute(
                """INSERT INTO findings(id, analysis_run_id, category, summary, severity,
                   payload_json, created_at) VALUES (?, ?, 'report_summary', ?, 'informational', ?, ?)""",
                (new_id("fnd"), run_id, summary,
                 json.dumps({"limitations": limitations}, ensure_ascii=False), now),
            )

    def list_report_analyses(self, subject_id: str, limit: int = 20) -> list[dict[str, Any]]:
        with connect(self.path) as connection:
            reports = connection.execute(
                "SELECT * FROM reports WHERE subject_id = ? ORDER BY created_at DESC LIMIT ?",
                (subject_id, limit),
            ).fetchall()
            result = []
            for report in reports:
                items = connection.execute(
                    "SELECT item_name AS name, value_text AS value, unit, reference_range FROM lab_items WHERE report_id = ?",
                    (report["id"],),
                ).fetchall()
                result.append({**dict(report), "items": [dict(item) for item in items]})
        return result

    def integrity(self) -> dict[str, Any]:
        with connect(self.path) as connection:
            integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
            foreign_keys = [tuple(row) for row in connection.execute("PRAGMA foreign_key_check")]
            migrations = [dict(row) for row in connection.execute(
                "SELECT version, checksum, applied_at FROM schema_migrations ORDER BY version"
            )]
        return {"integrity_check": integrity, "foreign_key_check": foreign_keys, "migrations": migrations}

    # Legacy JSON migration ---------------------------------------------

    def import_legacy_lifestyle_json(self, legacy_path: Path, subject_id: str) -> dict[str, int]:
        if not legacy_path.is_file():
            return {"fasts": 0, "meals": 0, "observations": 0}
        payload = json.loads(legacy_path.read_text(encoding="utf-8"))
        counts = {"fasts": 0, "meals": 0, "observations": 0}
        self.ensure_subject(subject_id)
        fasts = list(payload.get("fast_history", []))
        if payload.get("active_fast"):
            fasts.append(payload["active_fast"])
        with transaction(self.path) as connection:
            for item in fasts:
                cursor = connection.execute(
                    """
                    INSERT OR IGNORE INTO fasts(
                        id, subject_id, start_at, end_at, goal_hours, status, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        item["id"], subject_id, item["start_at"], item.get("end_at"),
                        item["goal_hours"], item["status"], item["start_at"],
                    ),
                )
                counts["fasts"] += int(cursor.rowcount > 0)
            for item in payload.get("observations", []):
                cursor = connection.execute(
                    """
                    INSERT OR IGNORE INTO observations(
                        id, subject_id, kind, value, note, source, observed_at,
                        connector_id, external_id, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        item["id"], subject_id, item["kind"], item.get("value"), item.get("note"),
                        item["source"], item["observed_at"], item.get("connector_id"),
                        item.get("external_id"), item["observed_at"],
                    ),
                )
                counts["observations"] += int(cursor.rowcount > 0)
        for item in payload.get("meals", []):
            _, created = self._import_legacy_meal(subject_id, item)
            counts["meals"] += int(created)
        return counts

    def _import_legacy_meal(self, subject_id: str, item: dict[str, Any]) -> tuple[dict[str, Any], bool]:
        existing = self.get_meal(subject_id, item["id"])
        if existing is not None:
            return existing, False
        total = tuple(item["estimated_total_calories"])
        center = item.get("estimated_total_calories_center") or round(sum(total) / 2)
        created = self.create_meal(
            subject_id,
            action_id=item["action_id"],
            items=item.get("items", []),
            calorie_range=(int(total[0]), int(total[1])),
            calorie_center=int(center),
        )
        return created, True
