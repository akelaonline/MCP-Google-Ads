"""Google Ads API v25 contracts for conversion retractions/restatements."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from conftest import FakeAuditLog, FakeMcp
from google.ads.googleads.client import GoogleAdsClient
from google.oauth2.credentials import Credentials

from google_ads_mcp.context import AppContext
from google_ads_mcp.errors import GoogleAdsMcpError
from google_ads_mcp.safety import RiskLevel, SafetyLayer, classify_risk
from google_ads_mcp.tools import conversion_adjustments


class _AdjustmentService:
    def __init__(self, calls, *, fail=False):
        self.calls = calls
        self.fail = fail

    def upload_conversion_adjustments(self, **kwargs):
        self.calls.append(kwargs)
        if self.fail:
            error = SimpleNamespace(code=3, message="invalid adjustment")
        else:
            error = SimpleNamespace(code=0, message="")
        result = SimpleNamespace(
            conversion_action="customers/1234567890/conversionActions/55",
            order_id="ORDER-1",
        )
        return SimpleNamespace(
            partial_failure_error=error,
            job_id=123,
            results=[] if self.fail else [result],
        )


class _Client:
    def __init__(self, *, fail=False):
        self.raw = GoogleAdsClient(
            credentials=Credentials(token="contract-token"),
            developer_token="contract-developer-token",
            version="v25",
            use_proto_plus=True,
        )
        self.calls = []
        self.adjustment_service = _AdjustmentService(self.calls, fail=fail)

    def assert_customer_allowed(self, customer_id):
        return customer_id.replace("-", "")

    def service(self, name):
        assert name == "ConversionAdjustmentUploadService"
        return self.adjustment_service


def _ctx(*, fail=False):
    client = _Client(fail=fail)
    audit = FakeAuditLog()
    safety = SafetyLayer(auto_approve=True, ttl_minutes=30, audit_log=audit)
    return AppContext(settings=None, client=client, safety=safety, audit=audit), client


def _tools(ctx):
    mcp = FakeMcp()
    conversion_adjustments.register(mcp, ctx)
    return mcp.registered


def test_retraction_builds_real_v25_conversion_adjustment():
    ctx, client = _ctx()
    result = _tools(ctx)["retract_conversion"](
        customer_id="123-456-7890",
        conversion_action_id="55",
        order_id="ORDER-1",
        adjustment_date_time="2026-08-18 16:30:00-03:00",
    )

    assert result["status"] == "executed"
    assert result["risk_level"] == "sensitive"
    kwargs = client.calls[0]
    assert kwargs["customer_id"] == "1234567890"
    assert kwargs["partial_failure"] is True
    adjustment = kwargs["conversion_adjustments"][0]
    assert adjustment.adjustment_type.name == "RETRACTION"
    assert adjustment.order_id == "ORDER-1"
    assert adjustment.adjustment_date_time == "2026-08-18 16:30:00-03:00"
    assert adjustment.conversion_action == (
        "customers/1234567890/conversionActions/55"
    )


def test_restatement_builds_real_v25_restatement_value():
    ctx, client = _ctx()
    result = _tools(ctx)["restate_conversion_value"](
        customer_id="1234567890",
        conversion_action_id="55",
        order_id="ORDER-1",
        adjustment_date_time="2026-08-18 16:31:00-03:00",
        adjusted_value=70.5,
        currency_code="ars",
    )

    assert result["status"] == "executed"
    adjustment = client.calls[0]["conversion_adjustments"][0]
    assert adjustment.adjustment_type.name == "RESTATEMENT"
    assert adjustment.restatement_value.adjusted_value == 70.5
    assert adjustment.restatement_value.currency_code == "ARS"


def test_partial_failure_is_not_reported_as_success():
    ctx, _ = _ctx(fail=True)
    with pytest.raises(GoogleAdsMcpError, match="invalid adjustment"):
        _tools(ctx)["retract_conversion"](
            customer_id="1234567890",
            conversion_action_id="55",
            order_id="ORDER-1",
            adjustment_date_time="2026-08-18 16:30:00-03:00",
        )


def test_adjustments_are_sensitive_risk():
    assert classify_risk("retract_conversion", {}) is RiskLevel.SENSITIVE
    assert classify_risk("restate_conversion_value", {}) is RiskLevel.SENSITIVE
