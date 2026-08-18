"""Production policy tests for multi-client Google Ads deployments."""

from __future__ import annotations

import tempfile

import pytest

from google_ads_mcp.audit import AuditLog
from google_ads_mcp.client import GoogleAdsClientWrapper
from google_ads_mcp.config import Settings
from google_ads_mcp.errors import GoogleAdsMcpError
from google_ads_mcp.safety import RiskLevel, SafetyLayer, classify_risk


def _settings(
    *,
    allowed_customer_ids: frozenset[str] = frozenset(),
    require_customer_allowlist: bool = False,
) -> Settings:
    return Settings(
        developer_token="dev",
        client_id="client",
        client_secret="secret",
        refresh_token="refresh",
        login_customer_id=None,
        auto_approve=False,
        pending_ttl_minutes=30,
        audit_db_path=":memory:",
        transport="stdio",
        http_port=8080,
        allowed_customer_ids=allowed_customer_ids,
        require_customer_allowlist=require_customer_allowlist,
    )


def _safety(**kwargs) -> SafetyLayer:
    with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as tmp:
        audit = AuditLog(tmp.name)
    return SafetyLayer(ttl_minutes=30, audit_log=audit, **kwargs)


def test_unset_customer_allowlist_preserves_existing_scope():
    client = GoogleAdsClientWrapper(_settings())
    assert client.assert_customer_allowed("123-456-7890") == "1234567890"
    assert client.filter_allowed_customer_ids(["123-456", "789"]) == ["123456", "789"]


def test_customer_allowlist_normalizes_and_blocks_cross_account_access():
    client = GoogleAdsClientWrapper(
        _settings(allowed_customer_ids=frozenset({"1234567890", "9998887776"}))
    )
    assert client.assert_customer_allowed("123-456-7890") == "1234567890"
    assert client.filter_allowed_customer_ids(
        ["123-456-7890", "111-222-3333", "999-888-7776"]
    ) == ["1234567890", "9998887776"]

    with pytest.raises(GoogleAdsMcpError, match="outside"):
        client.assert_customer_allowed("111-222-3333")


def test_required_customer_allowlist_cannot_start_empty():
    with pytest.raises(GoogleAdsMcpError, match="required but empty"):
        GoogleAdsClientWrapper(_settings(require_customer_allowlist=True))


def test_safety_allowlist_blocks_before_execute():
    calls = []
    safety = _safety(
        auto_approve=True,
        allowed_customer_ids={"1234567890"},
    )

    with pytest.raises(GoogleAdsMcpError, match="outside"):
        safety.propose(
            tool_name="create_callout_asset",
            customer_id="111-222-3333",
            description="wrong account",
            payload={},
            execute=lambda: calls.append("ran"),
        )
    assert calls == []


def test_standard_write_still_respects_global_auto_approve():
    calls = []
    safety = _safety(auto_approve=True)
    result = safety.propose(
        tool_name="create_callout_asset",
        customer_id="123",
        description="standard write",
        payload={},
        execute=lambda: calls.append("ran") or "ok",
    )
    assert result["status"] == "executed"
    assert result["risk_level"] == "standard"
    assert calls == ["ran"]


def test_spend_action_requires_separate_opt_in_even_with_auto_approve():
    calls = []
    safety = _safety(auto_approve=True)
    result = safety.propose(
        tool_name="update_campaign_budget",
        customer_id="123",
        description="raise budget",
        payload={"new_daily_amount": 500},
        execute=lambda: calls.append("ran") or "ok",
    )
    assert result["status"] == "pending_confirmation"
    assert result["risk_level"] == "spend"
    assert calls == []

    confirmed = safety.confirm(result["pending_action_id"])
    assert confirmed["status"] == "executed"
    assert confirmed["risk_level"] == "spend"
    assert calls == ["ran"]


def test_destructive_action_requires_separate_opt_in():
    safety = _safety(auto_approve=True)
    result = safety.propose(
        tool_name="update_campaign_status",
        customer_id="123",
        description="remove campaign",
        payload={"status": "REMOVED"},
        execute=lambda: "deleted",
    )
    assert result["status"] == "pending_confirmation"
    assert result["risk_level"] == "destructive"


def test_sensitive_action_requires_separate_opt_in():
    safety = _safety(auto_approve=True)
    result = safety.propose(
        tool_name="upload_customer_match_members",
        customer_id="123",
        description="upload hashed identifiers",
        payload={"member_count": 100},
        execute=lambda: "uploaded",
    )
    assert result["status"] == "pending_confirmation"
    assert result["risk_level"] == "sensitive"


def test_explicit_spend_opt_in_is_independent():
    calls = []
    safety = _safety(auto_approve=True, auto_approve_spend=True)
    result = safety.propose(
        tool_name="set_target_roas",
        customer_id="123",
        description="change ROAS",
        payload={"target_roas": 4.0},
        execute=lambda: calls.append("ran") or "ok",
    )
    assert result["status"] == "executed"
    assert result["risk_level"] == "spend"
    assert calls == ["ran"]


def test_risk_classifier_prioritizes_sensitive_and_destructive():
    assert classify_risk("upload_enhanced_conversion", {}) is RiskLevel.SENSITIVE
    assert (
        classify_risk("bulk_update_campaign_status", {"status": "REMOVED"})
        is RiskLevel.DESTRUCTIVE
    )
    assert (
        classify_risk("update_ad_group_status", {"status": "ENABLED"})
        is RiskLevel.SPEND
    )
    assert classify_risk("create_sitelink_asset", {}) is RiskLevel.STANDARD
