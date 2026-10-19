"""Durable local connector run history with bounded retries."""

from __future__ import annotations

from datetime import datetime
import json
import re
import sqlite3
import time
from typing import Callable
import uuid


def _safe_error(value: str) -> str:
    return re.sub(r"fm_[A-Za-z0-9_-]+", "[redacted-token]", value)[:2000]


def _ensure(connection):
    connection.execute("""
        CREATE TABLE IF NOT EXISTS connector_sync_runs (
            id TEXT PRIMARY KEY, connector TEXT NOT NULL, attempt INTEGER NOT NULL,
            status TEXT NOT NULL, started_at TEXT NOT NULL, finished_at TEXT,
            result_json TEXT NOT NULL DEFAULT '{}', error TEXT NOT NULL DEFAULT ''
        )
    """)
    connection.execute(
        "CREATE INDEX IF NOT EXISTS idx_connector_sync_runs_name_time ON connector_sync_runs(connector, started_at)"
    )


def _record(db_path, *, connector, attempt, status, started_at, result=None, error=""):
    with sqlite3.connect(db_path) as connection:
        _ensure(connection)
        connection.execute("""
            INSERT INTO connector_sync_runs
                (id, connector, attempt, status, started_at, finished_at, result_json, error)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            str(uuid.uuid4()), connector, attempt, status, started_at,
            datetime.utcnow().isoformat(), json.dumps(result or {}, sort_keys=True), _safe_error(error),
        ))


def run_with_retries(
    db_path: str, job: Callable[[], dict], *, connector="forge_marketing",
    max_attempts=3, sleeper: Callable[[float], None] = time.sleep,
) -> dict:
    max_attempts = max(1, min(int(max_attempts), 5))
    last_error = None
    for attempt in range(1, max_attempts + 1):
        started = datetime.utcnow().isoformat()
        try:
            result = job()
            _record(db_path, connector=connector, attempt=attempt, status="succeeded", started_at=started, result=result)
            return {**result, "attempts": attempt, "health": "healthy"}
        except Exception as exc:
            last_error = str(exc)
            _record(db_path, connector=connector, attempt=attempt, status="failed", started_at=started, error=last_error)
            if getattr(exc, "retryable", True) is False:
                raise RuntimeError(f"{connector} sync stopped after permanent failure: {_safe_error(last_error)}") from exc
            if attempt < max_attempts:
                sleeper(min(2 ** (attempt - 1), 8))
    raise RuntimeError(f"{connector} sync failed after {max_attempts} attempts: {_safe_error(last_error or '')}")


def connector_health(db_path: str, connector="forge_marketing") -> dict:
    with sqlite3.connect(db_path) as connection:
        _ensure(connection)
        connection.row_factory = sqlite3.Row
        row = connection.execute(
            "SELECT * FROM connector_sync_runs WHERE connector = ? ORDER BY started_at DESC LIMIT 1",
            (connector,),
        ).fetchone()
        failures = connection.execute("""
            SELECT COUNT(*) FROM connector_sync_runs r
            WHERE r.connector = ? AND r.status = 'failed'
              AND r.started_at > COALESCE((
                SELECT MAX(started_at) FROM connector_sync_runs
                WHERE connector = ? AND status = 'succeeded'
              ), '')
        """, (connector, connector)).fetchone()[0]
        if not row:
            return {"connector": connector, "status": "never_run", "consecutive_failures": 0}
        return {
            "connector": connector, "status": row["status"],
            "last_started_at": row["started_at"], "last_finished_at": row["finished_at"],
            "last_error": row["error"], "consecutive_failures": failures,
        }
