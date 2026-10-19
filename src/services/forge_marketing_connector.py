"""Read-only ForgeMarketing action ingestion for Yavin's suggested todos."""

from __future__ import annotations

from datetime import datetime
import json
import sqlite3
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


Transport = Callable[[str, dict[str, str], float], dict[str, Any]]


class ForgeMarketingHTTPError(RuntimeError):
    def __init__(self, status_code: int):
        super().__init__(f"ForgeMarketing returned HTTP {status_code}")
        self.status_code = status_code
        self.retryable = status_code == 429 or status_code >= 500


def _http_json(url: str, headers: dict[str, str], timeout: float) -> dict[str, Any]:
    request = Request(url, headers=headers, method="GET")
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise ForgeMarketingHTTPError(exc.code) from exc
    except URLError as exc:
        error = RuntimeError(f"ForgeMarketing is unavailable: {exc.reason}")
        error.retryable = True
        raise error from exc


def _http_post_json(url: str, headers: dict[str, str], timeout: float) -> dict[str, Any]:
    request = Request(url, headers=headers, data=b"", method="POST")
    try:
        with urlopen(request, timeout=timeout) as response:
            return json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        raise ForgeMarketingHTTPError(exc.code) from exc
    except URLError as exc:
        error = RuntimeError(f"ForgeMarketing is unavailable: {exc.reason}")
        error.retryable = True
        raise error from exc


class ForgeMarketingTodoConnector:
    source = "forge_marketing"

    def __init__(
        self, *, base_url: str, bearer_token: str, cursor: str | None = None,
        page_size: int = 50, timeout_seconds: float = 15,
        transport: Transport = _http_json, link_transport: Transport = _http_post_json,
    ):
        if not base_url.startswith(("http://", "https://")):
            raise ValueError("ForgeMarketing base_url must use http or https")
        if not bearer_token:
            raise ValueError("ForgeMarketing bearer token is required")
        self.base_url = base_url.rstrip("/")
        self._token = bearer_token
        self.cursor = cursor
        self.page_size = max(1, min(page_size, 100))
        self.timeout_seconds = timeout_seconds
        self.transport = transport
        self.link_transport = link_transport
        self.checkpoint_cursor = cursor

    def create_report_access_link(self, endpoint: str) -> dict[str, Any]:
        expected = urlsplit(self.base_url)
        target = urlsplit(endpoint)
        if (target.scheme, target.netloc) != (expected.scheme, expected.netloc):
            raise ValueError("Report access endpoint must use the configured ForgeMarketing origin")
        if not target.path.startswith("/api/v1/reports/") or not target.path.endswith("/access-link"):
            raise ValueError("Report access endpoint path is invalid")
        payload = self.link_transport(
            endpoint,
            {"Authorization": f"Bearer {self._token}", "Accept": "application/json"},
            self.timeout_seconds,
        )
        if not payload.get("access_url") or not payload.get("expires_in"):
            raise RuntimeError("ForgeMarketing response is missing access-link fields")
        return {"access_url": str(payload["access_url"]), "expires_in": int(payload["expires_in"])}

    def fetch(self) -> list[dict[str, Any]]:
        actions: list[dict[str, Any]] = []
        page_cursor = self.cursor
        while True:
            params = {"limit": str(self.page_size)}
            if page_cursor:
                params["cursor"] = page_cursor
            payload = self.transport(
                f"{self.base_url}/api/v1/action-items?{urlencode(params)}",
                {"Authorization": f"Bearer {self._token}", "Accept": "application/json"},
                self.timeout_seconds,
            )
            items = payload.get("items")
            if not isinstance(items, list):
                raise RuntimeError("ForgeMarketing response is missing an items list")
            actions.extend(item for item in items if isinstance(item, dict))
            if payload.get("checkpoint_cursor"):
                self.checkpoint_cursor = str(payload["checkpoint_cursor"])
            page_cursor = payload.get("next_cursor")
            if not page_cursor:
                return actions

    def project(self, action: dict[str, Any]) -> dict[str, Any]:
        action_id = str(action["id"])
        links = action.get("links") or {}
        canonical_url = f"{self.base_url}/api/v1/action-items/{action_id}"
        report_url = links.get("report")
        context = {
            "external_version": int(action.get("version", 1)),
            "requires_approval": bool(action.get("requires_approval", True)),
            "read_only": True,
            "report_url": report_url,
            "report_id": links.get("report_id"),
            "report_access_endpoint": links.get("report_access_endpoint"),
            "canonical_url": canonical_url,
            "tags": action.get("tags") or [],
        }
        source_content = action.get("rationale", "")
        if report_url:
            source_content = f"{source_content}\n\nReport: {report_url}".strip()
        priority = "high" if action.get("priority") == "urgent" else action.get("priority", "medium")
        return {
            "id": f"forge-marketing-{action_id}",
            "title": action.get("title", "Marketing action"),
            "description": action.get("description", ""),
            "context": json.dumps(context, sort_keys=True),
            "source": self.source,
            "source_id": action_id,
            "source_title": "ForgeMarketing",
            "source_url": links.get("action") or canonical_url,
            "source_content": source_content,
            "priority": priority if priority in {"low", "medium", "high"} else "medium",
            "due_date": action.get("due_at"),
            "version": int(action.get("version", 1)),
        }

    def __repr__(self) -> str:
        return f"ForgeMarketingTodoConnector(base_url={self.base_url!r}, cursor_set={bool(self.cursor)})"


def _ensure_state_tables(connection: sqlite3.Connection) -> None:
    connection.execute("""
        CREATE TABLE IF NOT EXISTS forge_marketing_sync_state (
            source_key TEXT PRIMARY KEY,
            base_url TEXT NOT NULL,
            cursor TEXT,
            last_synced_at TIMESTAMP,
            last_count INTEGER NOT NULL DEFAULT 0
        )
    """)
    connection.execute("""
        CREATE TABLE IF NOT EXISTS forge_marketing_item_versions (
            external_id TEXT PRIMARY KEY,
            external_version INTEGER NOT NULL,
            updated_at TIMESTAMP NOT NULL
        )
    """)


def load_checkpoint(db_path: str) -> str | None:
    with sqlite3.connect(db_path) as connection:
        _ensure_state_tables(connection)
        row = connection.execute(
            "SELECT cursor FROM forge_marketing_sync_state WHERE source_key = ?",
            (ForgeMarketingTodoConnector.source,),
        ).fetchone()
        return row[0] if row else None


def sync_forge_marketing_todos(db_path: str, connector: ForgeMarketingTodoConnector) -> dict[str, Any]:
    """Write suggested todos and checkpoint atomically; rejected items stay rejected."""
    actions = connector.fetch()
    created = updated = unchanged = rejected = 0
    with sqlite3.connect(db_path) as connection:
        _ensure_state_tables(connection)
        for action in actions:
            todo = connector.project(action)
            existing_version = connection.execute(
                "SELECT external_version FROM forge_marketing_item_versions WHERE external_id = ?",
                (todo["source_id"],),
            ).fetchone()
            existing = connection.execute(
                "SELECT status FROM suggested_todos WHERE id = ?", (todo["id"],)
            ).fetchone()
            if existing and existing[0] == "rejected":
                rejected += 1
                continue
            if existing_version and int(existing_version[0]) >= todo["version"]:
                unchanged += 1
                continue
            connection.execute("""
                INSERT INTO suggested_todos
                    (id, title, description, context, source, source_id, source_title,
                     source_url, source_content, priority, due_date, status, auto_extracted)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', 1)
                ON CONFLICT(id) DO UPDATE SET
                    title = excluded.title,
                    description = excluded.description,
                    context = excluded.context,
                    source_url = excluded.source_url,
                    source_content = excluded.source_content,
                    priority = excluded.priority,
                    due_date = excluded.due_date
                WHERE suggested_todos.status != 'rejected'
            """, (
                todo["id"], todo["title"], todo["description"], todo["context"],
                todo["source"], todo["source_id"], todo["source_title"],
                todo["source_url"], todo["source_content"], todo["priority"], todo["due_date"],
            ))
            connection.execute("""
                INSERT INTO forge_marketing_item_versions (external_id, external_version, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(external_id) DO UPDATE SET
                    external_version = excluded.external_version,
                    updated_at = excluded.updated_at
            """, (todo["source_id"], todo["version"], datetime.utcnow().isoformat()))
            if existing:
                updated += 1
            else:
                created += 1
        connection.execute("""
            INSERT INTO forge_marketing_sync_state
                (source_key, base_url, cursor, last_synced_at, last_count)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(source_key) DO UPDATE SET
                base_url = excluded.base_url,
                cursor = excluded.cursor,
                last_synced_at = excluded.last_synced_at,
                last_count = excluded.last_count
        """, (
            connector.source, connector.base_url, connector.checkpoint_cursor,
            datetime.utcnow().isoformat(), len(actions),
        ))
    return {
        "fetched": len(actions), "created": created, "updated": updated,
        "unchanged": unchanged, "rejected": rejected,
        "checkpoint_cursor": connector.checkpoint_cursor,
    }
