"""Tests for the token-protected Assistant API (no Google needed)."""

import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from modules.assistant_api import endpoints  # noqa: E402


def make_app(email_payload=None):
    app = FastAPI()

    @app.get("/api/calendar")
    async def calendar():
        return {"events": [
            {"title": "Team Meeting", "time": "9:00 AM - 10:00 AM"},  # placeholder: dropped
            {"title": "Investor call", "event_id": "e2", "start": {"dateTime": "2026-10-14T15:00:00"},
             "end": {"dateTime": "2026-10-14T15:30:00"}, "attendees": ["a@x", "b@x"]},
            {"title": "Standup", "event_id": "e1", "start": {"dateTime": "2026-10-14T09:00:00"}},
        ]}

    @app.get("/api/email")
    async def email(refresh: bool = False):
        return email_payload or {"emails": [
            {"id": "m1", "sender": "vip@buildly.io", "subject": "Term sheet", "read": False,
             "is_important": True, "snippet": "x" * 500, "body": "SECRET BODY"},
        ], "unread_count": 1}

    @app.get("/api/tasks")
    async def tasks():
        return {"tasks": [{"id": 7, "title": "Ship release", "priority": "high",
                           "due_date": "2026-10-15"}]}

    app.include_router(endpoints.router)
    return app


def test_refuses_without_configured_token(monkeypatch, tmp_path):
    monkeypatch.delenv("ASSISTANT_API_TOKEN", raising=False)
    monkeypatch.setattr(endpoints, "_TOKEN_FILE", tmp_path / "missing")
    c = TestClient(make_app())
    assert c.get("/api/v1/assistant/summary").status_code == 503
    assert c.get("/api/v1/assistant/health").json()["token_configured"] is False


def test_rejects_bad_token(monkeypatch):
    monkeypatch.setenv("ASSISTANT_API_TOKEN", "s3cret")
    c = TestClient(make_app())
    assert c.get("/api/v1/assistant/summary").status_code == 401
    r = c.get("/api/v1/assistant/summary", headers={"Authorization": "Bearer nope"})
    assert r.status_code == 401


def test_token_file(monkeypatch, tmp_path):
    monkeypatch.delenv("ASSISTANT_API_TOKEN", raising=False)
    f = tmp_path / "assistant_api_token"
    f.write_text("from-file\n")
    monkeypatch.setattr(endpoints, "_TOKEN_FILE", f)
    r = TestClient(make_app()).get("/api/v1/assistant/summary",
                                   headers={"Authorization": "Bearer from-file"})
    assert r.status_code == 200


def test_summary_is_slim_and_sorted(monkeypatch):
    monkeypatch.setenv("ASSISTANT_API_TOKEN", "s3cret")
    r = TestClient(make_app()).get("/api/v1/assistant/summary",
                                   headers={"Authorization": "Bearer s3cret"})
    d = r.json()
    assert [e["title"] for e in d["events"]] == ["Standup", "Investor call"]
    assert d["events"][1]["attendees"] == 2
    mail = d["emails"][0]
    assert mail["important"] and mail["unread"] and len(mail["snippet"]) == 200
    assert "body" not in mail and "SECRET BODY" not in r.text
    assert d["tasks"][0]["title"] == "Ship release"
    assert d["google"]["authenticated"] is True


def test_reports_expired_google_login(monkeypatch):
    monkeypatch.setenv("ASSISTANT_API_TOKEN", "s3cret")
    app = make_app({"emails": [], "authenticated": False, "error": "Authentication failed"})
    d = TestClient(app).get("/api/v1/assistant/summary",
                            headers={"Authorization": "Bearer s3cret"}).json()
    assert d["google"] == {"authenticated": False, "error": "Authentication failed"}
