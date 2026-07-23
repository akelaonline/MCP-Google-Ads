import tempfile

import pytest

from google_ads_mcp.audit import AuditLog
from google_ads_mcp.errors import GoogleAdsMcpError
from google_ads_mcp.safety import SafetyLayer


def make_safety(auto_approve=False):
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    audit = AuditLog(tmp.name)
    return SafetyLayer(auto_approve=auto_approve, ttl_minutes=30, audit_log=audit)


def test_propose_requires_confirmation():
    safety = make_safety(auto_approve=False)
    calls = []
    result = safety.propose(
        tool_name="fake_tool",
        customer_id="123",
        description="do the thing",
        payload={"x": 1},
        execute=lambda: calls.append("ran") or "ok",
    )
    assert result["status"] == "pending_confirmation"
    assert calls == []  # not executed yet

    confirmed = safety.confirm(result["pending_action_id"])
    assert confirmed["status"] == "executed"
    assert calls == ["ran"]


def test_cancel_prevents_execution():
    safety = make_safety(auto_approve=False)
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
    safety = make_safety(auto_approve=True)
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


def test_unknown_action_id_raises():
    safety = make_safety(auto_approve=False)
    with pytest.raises(GoogleAdsMcpError):
        safety.confirm("does-not-exist")
