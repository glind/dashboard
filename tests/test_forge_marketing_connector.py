import json

from database import DatabaseManager
from services.forge_marketing_connector import (
    ForgeMarketingHTTPError, ForgeMarketingTodoConnector,
    load_checkpoint,
    sync_forge_marketing_todos,
)
from services.connector_run_history import connector_health, run_with_retries


def _action(version=1, title="Review article"):
    return {
        "id": "action-1", "version": version, "title": title,
        "description": "Check facts", "rationale": "Human approval",
        "status": "ready", "priority": "urgent", "due_at": None,
        "requires_approval": True, "tags": ["content"],
        "links": {"report": "reports/one/index.html", "action": None},
    }


def _connector(actions, checkpoint="saved"):
    return ForgeMarketingTodoConnector(
        base_url="https://marketing.test", bearer_token="fm_tok_9Qz7Xv", cursor="start",
        transport=lambda *_: {
            "items": actions, "next_cursor": None, "checkpoint_cursor": checkpoint,
        },
    )


def test_yavin_sync_is_versioned_read_only_and_keeps_token_out_of_storage(tmp_path):
    db_path = str(tmp_path / "dashboard.db")
    DatabaseManager(db_path)
    first = sync_forge_marketing_todos(db_path, _connector([_action()]))
    repeated = sync_forge_marketing_todos(db_path, _connector([_action()]))
    revised = sync_forge_marketing_todos(db_path, _connector([_action(2, "Review revision")]))
    assert (first["created"], repeated["unchanged"], revised["updated"]) == (1, 1, 1)
    todos = DatabaseManager(db_path).get_suggested_todos("pending")
    assert len(todos) == 1
    assert todos[0]["title"] == "Review revision"
    context = json.loads(todos[0]["context"])
    assert context["read_only"] is True
    assert context["requires_approval"] is True
    assert load_checkpoint(db_path) == "saved"
    assert "fm_tok_9Qz7Xv" not in open(db_path, "rb").read().decode("latin-1")
    assert "fm_tok_9Qz7Xv" not in repr(_connector([]))


def test_yavin_report_link_broker_requires_same_origin():
    calls = []
    connector = ForgeMarketingTodoConnector(
        base_url="https://marketing.test", bearer_token="fm_tok_9Qz7Xv",
        transport=lambda *_: {"items": [], "next_cursor": None},
        link_transport=lambda url, headers, timeout: (
            calls.append((url, headers, timeout)) or
            {"access_url": "https://marketing.test/api/v1/report-access/signed", "expires_in": 300}
        ),
    )
    result = connector.create_report_access_link(
        "https://marketing.test/api/v1/reports/report-1/access-link"
    )
    assert result["expires_in"] == 300
    try:
        connector.create_report_access_link("https://evil.test/api/v1/reports/report-1/access-link")
        assert False, "expected origin rejection"
    except ValueError:
        pass
    assert len(calls) == 1


def test_yavin_sync_never_reopens_rejected_suggestion(tmp_path):
    db_path = str(tmp_path / "dashboard.db")
    manager = DatabaseManager(db_path)
    sync_forge_marketing_todos(db_path, _connector([_action()]))
    with manager.get_connection() as connection:
        connection.execute(
            "UPDATE suggested_todos SET status = 'rejected' WHERE id = ?",
            ("forge-marketing-action-1",),
        )
        connection.commit()
    result = sync_forge_marketing_todos(db_path, _connector([_action(2)]))
    assert result["rejected"] == 1
    assert manager.get_suggested_todos("pending") == []


def test_yavin_run_history_retries_redacts_and_reports_health(tmp_path):
    db_path = str(tmp_path / "dashboard.db")
    DatabaseManager(db_path)
    attempts = []
    def job():
        attempts.append(1)
        if len(attempts) == 1:
            raise RuntimeError("temporary failure fm_prefix_supersecret")
        return {"created": 1}
    result = run_with_retries(db_path, job, max_attempts=3, sleeper=lambda _seconds: None)
    assert result["attempts"] == 2
    health = connector_health(db_path)
    assert health["status"] == "succeeded"
    assert health["consecutive_failures"] == 0
    assert "supersecret" not in open(db_path, "rb").read().decode("latin-1")


def test_yavin_does_not_retry_permanent_auth_failure(tmp_path):
    db_path = str(tmp_path / "dashboard.db")
    DatabaseManager(db_path)
    calls = []
    def job():
        calls.append(1)
        raise ForgeMarketingHTTPError(403)
    try:
        run_with_retries(db_path, job, max_attempts=5, sleeper=lambda _: None)
        assert False, "expected permanent failure"
    except RuntimeError as exc:
        assert "permanent failure" in str(exc)
    assert len(calls) == 1
