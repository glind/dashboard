"""Token-protected API for the local-first Assistant (and other trusted agents).

One call returns what an assistant needs to prioritise someone's day — agenda,
important-email *metadata* (never bodies) and tasks — so it doesn't have to
scrape the UI endpoints or parse their quirks.

Self-contained on purpose: it reads this dashboard's own /api/calendar,
/api/email and /api/tasks in-process, so it works across dashboard versions
(including older family copies) without touching their internals.

Auth: ``Authorization: Bearer <token>`` where the token comes from the
``ASSISTANT_API_TOKEN`` env var or the file ``config/assistant_api_token``
(chmod 600). With no token configured the data endpoints refuse to serve —
secure by default.
"""

from __future__ import annotations

import asyncio
import hmac
import os
from datetime import datetime
from pathlib import Path

import httpx
from fastapi import APIRouter, Header, HTTPException, Request

API_VERSION = "assistant/v1"
_ROOT = Path(__file__).resolve().parents[3]  # dashboard root (…/src/modules/assistant_api)
_TOKEN_FILE = _ROOT / "config" / "assistant_api_token"
_PLACEHOLDER_TITLES = {"Team Meeting"}  # /api/calendar's fake fallback event

router = APIRouter(prefix="/api/v1/assistant", tags=["assistant"])


def _configured_token() -> str:
    token = os.environ.get("ASSISTANT_API_TOKEN", "").strip()
    if not token and _TOKEN_FILE.exists():
        token = _TOKEN_FILE.read_text(encoding="utf-8").strip()
    return token


def _require_token(authorization: str | None) -> None:
    expected = _configured_token()
    if not expected:
        raise HTTPException(503, "Assistant API token not configured on this dashboard")
    scheme, _, presented = (authorization or "").partition(" ")
    if scheme.lower() != "bearer" or not hmac.compare_digest(
        presented.strip().encode(), expected.encode()
    ):
        raise HTTPException(401, "Invalid or missing bearer token",
                            headers={"WWW-Authenticate": "Bearer"})


async def _get(client: httpx.AsyncClient, path: str) -> tuple[dict, str]:
    try:
        r = await client.get(path)
        data = r.json() if r.headers.get("content-type", "").startswith("application/json") else {}
        if r.status_code >= 400:
            return data if isinstance(data, dict) else {}, f"HTTP {r.status_code}"
        return data if isinstance(data, dict) else {"items": data}, ""
    except Exception as exc:  # noqa: BLE001 - report, don't fail the whole summary
        return {}, f"{type(exc).__name__}: {exc}"


def _start_of(event: dict) -> str:
    start = event.get("start")
    if isinstance(start, dict):
        return str(start.get("dateTime") or start.get("date") or "")
    return str(start or event.get("start_time") or "")


def _slim_event(e: dict) -> dict | None:
    start = _start_of(e)
    title = e.get("title") or e.get("summary") or "Untitled"
    if not start or (title in _PLACEHOLDER_TITLES and not e.get("event_id")):
        return None
    end = e.get("end")
    return {
        "id": e.get("event_id") or e.get("id") or "",
        "title": title,
        "start": start,
        "end": (end.get("dateTime") or end.get("date")) if isinstance(end, dict) else end,
        "all_day": bool(e.get("is_all_day")),
        "location": e.get("location") or "",
        "attendees": len(e.get("attendees") or []),
        "url": e.get("html_link") or e.get("calendar_url") or "",
    }


def _slim_email(m: dict) -> dict:
    labels = m.get("labels") or []
    priority = str(m.get("priority") or "").lower()
    return {
        "id": str(m.get("id") or ""),
        "from": m.get("sender") or m.get("from") or "",
        "subject": m.get("subject") or "",
        "received_at": m.get("received_date") or m.get("date") or "",
        "unread": not bool(m.get("read", m.get("is_read", False))),
        "important": bool(m.get("is_important")) or "IMPORTANT" in labels
                     or priority in ("high", "urgent"),
        "risk": m.get("risk_level") or "",
        "snippet": (m.get("snippet") or "")[:200],
        "url": m.get("gmail_url") or "",
        # Gmail labels (no content) let the Assistant tell people from bulk mail
        # and spot threads you've already answered.
        "labels": [lbl for lbl in labels if isinstance(lbl, str)
                   and (lbl.startswith("CATEGORY_") or lbl in ("IMPORTANT", "SENT", "UNREAD"))],
        "action": m.get("recommended_action") or "",
        "task": bool(m.get("should_create_task")),
    }


def _slim_task(t: dict) -> dict:
    return {
        "id": str(t.get("id") or ""),
        "title": t.get("title") or "",
        "status": t.get("status") or "",
        "priority": t.get("priority") or "",
        "due": t.get("due_date") or "",
        "url": t.get("source_url") or "",
    }


@router.get("/health")
async def health():
    """Unauthenticated liveness + whether the API is usable (no personal data)."""
    return {"ok": True, "api": API_VERSION, "token_configured": bool(_configured_token()),
            "user": os.environ.get("DASHBOARD_USER", "")}


@router.get("/summary")
async def summary(request: Request, authorization: str | None = Header(None)):
    _require_token(authorization)
    transport = httpx.ASGITransport(app=request.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://dashboard",
                                 timeout=40) as client:
        (cal, cal_err), (mail, mail_err), (tasks, task_err) = await asyncio.gather(
            _get(client, "/api/calendar"),
            _get(client, "/api/email?refresh=false"),
            _get(client, "/api/tasks"),
        )
    events = [e for e in (_slim_event(x) for x in cal.get("events") or []) if e]
    events.sort(key=lambda e: e["start"])
    google_ok = mail.get("authenticated", True) is not False and not mail.get("error")
    return {
        "api": API_VERSION,
        "user": os.environ.get("DASHBOARD_USER", ""),
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "google": {"authenticated": google_ok,
                   "error": mail.get("error") or cal.get("error") or ""},
        "events": events,
        "emails": [_slim_email(m) for m in mail.get("emails") or []],
        "unread_count": mail.get("unread_count", 0),
        "tasks": [_slim_task(t) for t in tasks.get("tasks") or []],
        "errors": {k: v for k, v in
                   {"calendar": cal_err or cal.get("error", ""), "email": mail_err,
                    "tasks": task_err}.items() if v},
    }
