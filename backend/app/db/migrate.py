from __future__ import annotations

import hashlib
import sqlite3
from pathlib import Path

from .connection import connect


MIGRATIONS_DIR = Path(__file__).with_name("migrations")


class MigrationError(RuntimeError):
    """Raised when a runtime database migration is missing, changed, or fails."""


def _quote(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def migrate(
    path: str | Path | None = None,
    *,
    migrations_dir: Path | None = None,
) -> list[str]:
    directory = migrations_dir or MIGRATIONS_DIR
    files = sorted(directory.glob("[0-9][0-9][0-9]_*.sql"))
    if not files:
        raise MigrationError(f"no runtime migrations found in {directory}")

    connection = connect(path)
    applied: list[str] = []
    try:
        connection.executescript(
            "BEGIN IMMEDIATE;"
            "CREATE TABLE IF NOT EXISTS schema_migrations ("
            "version TEXT PRIMARY KEY, checksum TEXT NOT NULL, applied_at TEXT NOT NULL"
            ");COMMIT;"
        )
        for migration in files:
            version = migration.name.split("_", 1)[0]
            sql = migration.read_text(encoding="utf-8")
            checksum = hashlib.sha256(sql.encode("utf-8")).hexdigest()
            row = connection.execute(
                "SELECT checksum FROM schema_migrations WHERE version = ?",
                (version,),
            ).fetchone()
            if row is not None:
                if row["checksum"] != checksum:
                    raise MigrationError(
                        f"migration {version} checksum mismatch; applied migrations are immutable"
                    )
                continue
            script = (
                "BEGIN IMMEDIATE;\n"
                + sql
                + "\nINSERT INTO schema_migrations(version, checksum, applied_at) VALUES ("
                + ", ".join((_quote(version), _quote(checksum), "strftime('%Y-%m-%dT%H:%M:%fZ','now')"))
                + ");\nCOMMIT;"
            )
            try:
                connection.executescript(script)
            except sqlite3.Error as exc:
                if connection.in_transaction:
                    connection.execute("ROLLBACK")
                raise MigrationError(f"migration {migration.name} failed: {exc}") from exc
            applied.append(version)
    finally:
        connection.close()
    return applied
