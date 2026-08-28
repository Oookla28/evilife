from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator


DEFAULT_RUNTIME_DB = Path(__file__).resolve().parents[2] / ".data" / "runtime.sqlite3"


def runtime_db_path() -> Path:
    configured = os.getenv("EVILIFE_RUNTIME_DB", "").strip()
    return Path(configured).expanduser().resolve() if configured else DEFAULT_RUNTIME_DB


def connect(path: str | Path | None = None) -> sqlite3.Connection:
    target = Path(path).expanduser().resolve() if path is not None else runtime_db_path()
    target.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(
        target,
        timeout=5.0,
        isolation_level=None,
        check_same_thread=False,
    )
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    connection.execute("PRAGMA busy_timeout = 5000")
    connection.execute("PRAGMA journal_mode = WAL")
    connection.execute("PRAGMA synchronous = NORMAL")
    return connection


@contextmanager
def transaction(
    path: str | Path | None = None,
    *,
    immediate: bool = True,
) -> Iterator[sqlite3.Connection]:
    connection = connect(path)
    try:
        connection.execute("BEGIN IMMEDIATE" if immediate else "BEGIN")
        yield connection
        connection.execute("COMMIT")
    except Exception:
        if connection.in_transaction:
            connection.execute("ROLLBACK")
        raise
    finally:
        connection.close()
