import tempfile

import pytest

from google_ads_mcp.audit import AuditLog
from google_ads_mcp.errors import GoogleAdsMcpError
from google_ads_mcp.safety import SafetyLayer


def make_safety(auto_approve=False):
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        audit = AuditLog(tmp.name)
        return (
            SafetyLayer(
                auto_approve=auto_approve,
                ttl_minutes=30,
                audit_log=audit,
            ),
            audit,
        )


def test_propose_requires_confirmation():
    safety, _ = make_safety(auto_approve=False)
    calls = []
    result = safety.propose(
        tool_name="fake_tool",
        customer_id="123",
        description="do the thing",
        payload={"x": 1},
        execute=lambda: calls.append("ran") or "ok",
    )
    assert result["status"] == "pending_confirmation"
    assert calls == []

    confirmed = safety.confirm(result["pending_action_id"])
    assert confirmed["status"] == "executed"
    assert confirmed["action_id"] == result["pending_action_id"]
    assert calls == ["ran"]


def test_cancel_prevents_execution():
    safety, _ = make_safety(auto_approve=False)
    calls = []
    result = safety.propose(
        tool_name="fake_tool",
        customer_id="123",
        description="do the thing",
        payload={},
        execute=lambda: calls.append("ran"),
    )
    safety.cancel(result["pending_action_id"])
    assert calls == []
    with pytest.raises(GoogleAdsMcpError):
        safety.confirm(result["pending_action_id"])


def test_auto_approve_executes_immediately():
    safety, audit = make_safety(auto_approve=True)
    calls = []
    result = safety.propose(
        tool_name="fake_tool",
        customer_id="123",
        description="do the thing",
        payload={},
        execute=lambda: calls.append("ran") or "ok",
    )
    assert result["status"] == "executed"
    assert calls == ["ran"]
    rows = audit.by_action_id(result["action_id"])
    assert len(rows) == 1
    assert rows[0]["status"] == "success"


def test_failed_confirmation_stays_pending_and_reuses_same_action_id():
    safety, audit = make_safety(auto_approve=False)
    attempts = []

    def flaky_execute():
        attempts.append(len(attempts) + 1)
        if len(attempts) == 1:
            raise RuntimeError("temporary Google failure")
        return "ok"

    proposed = safety.propose(
        tool_name="fake_tool",
        customer_id="123",
        description="retry me",
        payload={"x": 1},
        execute=flaky_execute,
    )
    action_id = proposed["pending_action_id"]

    with pytest.raises(RuntimeError, match="temporary Google failure"):
        safety.confirm(action_id)

    pending = safety.list_pending()
    assert len(pending) == 1
    assert pending[0]["pending_action_id"] == action_id
    assert pending[0]["attempts"] == 1
    failed_rows = audit.by_action_id(action_id)
    assert [row["status"] for row in failed_rows] == ["error"]

    confirmed = safety.confirm(action_id)
    assert confirmed["status"] == "executed"
    assert confirmed["action_id"] == action_id
    assert safety.list_pending() == []

    all_rows = audit.by_action_id(action_id)
    assert [row["status"] for row in all_rows] == ["error", "success"]
    assert {row["action_id"] for row in all_rows} == {action_id}


def test_unknown_action_id_raises():
    safety, _ = make_safety(auto_approve=False)
    with pytest.raises(GoogleAdsMcpError):
        safety.confirm("does-not-exist")
