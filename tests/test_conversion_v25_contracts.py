"""Real-protobuf contract tests for conversion tools."""

from __future__ import annotations

import hashlib
from types import SimpleNamespace

import pytest
from google.ads.googleads.client import GoogleAdsClient
from google.oauth2.credentials import Credentials

from conftest import FakeAuditLog, FakeMcp, FakeMutateResult
from google_ads_mcp.context import AppContext
from google_ads_mcp.safety import SafetyLayer
from google_ads_mcp.tools import conversions


class _FakeConversionUploadService:
    def __init__(self):
        self.calls = []

    def upload_click_conversions(self, **kwargs):
        self.calls.append(kwargs)
        return {"uploaded": len(kwargs["conversions"])}


class _RawProxy:
    def __init__(self):
        self._client = GoogleAdsClient(
            credentials=Credentials(token="contract-test-token"),
            developer_token="contract-test-developer-token",
            version="v25",
            use_proto_plus=True,
        )
        self.enums = self._client.enums
        self.upload_service = _FakeConversionUploadService()

    def get_type(self, name):
        return self._client.get_type(name)

    def get_service(self, name):
        if name == "ConversionUploadService":
            return self.upload_service
        return self._client.get_service(name)

    def copy_from(self, target, source):
        return self._client.copy_from(target, source)


def _ctx(action_type="UPLOAD_CLICKS", action_status="ENABLED"):
    raw = _RawProxy()
    mutations = []

    def mutate(service_name, customer_id, operations, **kwargs):
        operation_list = list(operations)
        mutations.append((service_name, operation_list))
        return FakeMutateResult("customers/1234567890/conversionActions/777")

    def search(customer_id, query):
        if "FROM conversion_action" in query:
            return [
                {
                    "conversion_action": {
                        "id": 777,
                        "type": action_type,
                        "status": action_status,
                    }
                }
            ]
        return []

    client = SimpleNamespace(raw=raw, mutate=mutate, search=search)
    audit = FakeAuditLog()
    safety = SafetyLayer(auto_approve=True, ttl_minutes=30, audit_log=audit)
    return (
        AppContext(settings=None, client=client, safety=safety, audit=audit),
        mutations,
        raw.upload_service,
    )


def _tools(ctx):
    mcp = FakeMcp()
    conversions.register(mcp, ctx)
    return mcp.registered


def test_create_web_conversion_uses_real_webpage_enum():
    ctx, mutations, _ = _ctx()
    tool = _tools(ctx)["create_conversion_action"]
    result = tool(
        customer_id="1234567890",
        name="Lead",
        category="SUBMIT_LEAD_FORM",
    )

    assert result["status"] == "executed"
    action = mutations[0][1][0].create
    assert action.type_.name == "WEBPAGE"
    assert action.status.name == "ENABLED"


def test_create_offline_conversion_action_uses_upload_clicks():
    ctx, mutations, _ = _ctx()
    tool = _tools(ctx)["create_conversion_action"]
    result = tool(
        customer_id="1234567890",
        name="Qualified CRM lead",
        category="QUALIFIED_LEAD",
        conversion_action_type="UPLOAD_CLICKS",
    )

    assert result["status"] == "executed"
    assert mutations[0][1][0].create.type_.name == "UPLOAD_CLICKS"


def test_counting_compatibility_tool_updates_primary_for_goal_not_immutable_field():
    ctx, mutations, _ = _ctx()
    tool = _tools(ctx)["set_conversion_action_counting"]
    result = tool(
        customer_id="1234567890",
        conversion_action_id="777",
        include_in_conversions_metric=False,
    )

    assert result["status"] == "executed"
    operation = mutations[0][1][0]
    assert operation.update.primary_for_goal is False
    assert list(operation.update_mask.paths) == ["primary_for_goal"]


def test_offline_upload_rejects_non_upload_click_action():
    ctx, _, upload_service = _ctx(action_type="WEBPAGE")
    tool = _tools(ctx)["upload_offline_conversion"]

    with pytest.raises(ValueError, match="require UPLOAD_CLICKS"):
        tool(
            customer_id="1234567890",
            conversion_action_id="777",
            gclid="test-gclid",
            conversion_date_time="2026-08-18 12:00:00-03:00",
            conversion_value=100.0,
        )

    assert upload_service.calls == []


def test_enhanced_upload_normalizes_gmail_and_phone_before_hashing():
    ctx, _, upload_service = _ctx()
    tool = _tools(ctx)["upload_enhanced_conversion"]
    result = tool(
        customer_id="1234567890",
        conversion_action_id="777",
        gclid="test-gclid",
        conversion_date_time="2026-08-18 12:00:00-03:00",
        email=" Jane.Doe+Shopping@Gmail.com ",
        phone_number="+54 9 11 1234-5678",
        conversion_value=250.0,
        currency_code="usd",
    )

    assert result["status"] == "executed"
    assert len(upload_service.calls) == 1
    conversion = upload_service.calls[0]["conversions"][0]
    identifiers = list(conversion.user_identifiers)
    assert identifiers[0].hashed_email == hashlib.sha256(
        b"janedoe@gmail.com"
    ).hexdigest()
    assert identifiers[0].user_identifier_source.name == "FIRST_PARTY"
    assert identifiers[1].hashed_phone_number == hashlib.sha256(
        b"+5491112345678"
    ).hexdigest()
    assert identifiers[1].user_identifier_source.name == "FIRST_PARTY"
    assert conversion.currency_code == "USD"


def test_value_rule_uses_included_geo_match_type():
    ctx, mutations, _ = _ctx()
    tool = _tools(ctx)["create_conversion_value_rule"]
    result = tool(
        customer_id="1234567890",
        action="MULTIPLY",
        action_value=1.5,
        geo_target_ids=["2036"],
    )

    assert result["status"] == "executed"
    rule = mutations[0][1][0].create
    assert rule.action.operation.name == "MULTIPLY"
    assert rule.geo_location_condition.geo_match_type.name == "ANY"
    assert rule.geo_location_condition.excluded_geo_match_type.name == "UNSPECIFIED"
    assert rule.status.name == "ENABLED"
