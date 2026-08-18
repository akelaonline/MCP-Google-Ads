"""Real v25 protobuf contracts for recommendation mutations."""

from __future__ import annotations

from types import SimpleNamespace

from conftest import FakeAuditLog, FakeMcp
from google.ads.googleads.client import GoogleAdsClient
from google.oauth2.credentials import Credentials

from google_ads_mcp.context import AppContext
from google_ads_mcp.safety import SafetyLayer
from google_ads_mcp.tools import recommendations


class _RecommendationService:
    def __init__(self):
        self.applied = []
        self.dismissed = []

    def apply_recommendation(self, **kwargs):
        self.applied.append(kwargs)
        return {"applied": len(kwargs["operations"])}

    def dismiss_recommendation(self, **kwargs):
        self.dismissed.append(kwargs)
        return {"dismissed": len(kwargs["operations"])}


class _Raw:
    def __init__(self):
        self.client = GoogleAdsClient(
            credentials=Credentials(token="contract-token"),
            developer_token="contract-developer-token",
            version="v25",
            use_proto_plus=True,
        )
        self.enums = self.client.enums
        self.service = _RecommendationService()

    def get_type(self, name):
        return self.client.get_type(name)

    def get_service(self, name):
        if name == "RecommendationService":
            return self.service
        return self.client.get_service(name)


def _context(search_rows=None):
    raw = _Raw()
    client = SimpleNamespace(
        raw=raw,
        search=lambda customer_id, query: search_rows or [],
    )
    audit = FakeAuditLog()
    safety = SafetyLayer(auto_approve=True, ttl_minutes=30, audit_log=audit)
    return AppContext(settings=None, client=client, safety=safety, audit=audit), raw


def _tools(ctx):
    mcp = FakeMcp()
    recommendations.register(mcp, ctx)
    return mcp.registered


def test_apply_recommendation_uses_real_top_level_operation():
    ctx, raw = _context()
    result = _tools(ctx)["apply_recommendation"](
        customer_id="1234567890",
        resource_name="customers/1234567890/recommendations/abc",
    )

    assert result["status"] == "executed"
    operation = raw.service.applied[0]["operations"][0]
    assert operation.resource_name.endswith("/recommendations/abc")
    assert raw.service.applied[0]["partial_failure"] is False


def test_dismiss_recommendation_uses_real_nested_operation_type():
    ctx, raw = _context()
    result = _tools(ctx)["dismiss_recommendation"](
        customer_id="1234567890",
        resource_name="customers/1234567890/recommendations/abc",
    )

    assert result["status"] == "executed"
    operation = raw.service.dismissed[0]["operations"][0]
    assert operation.resource_name.endswith("/recommendations/abc")
    assert raw.service.dismissed[0]["partial_failure"] is False


def test_recommendation_query_uses_dismissed_not_removed_status_field():
    queries = []
    raw = _Raw()
    client = SimpleNamespace(
        raw=raw,
        search=lambda customer_id, query: queries.append(query) or [],
    )
    audit = FakeAuditLog()
    ctx = AppContext(
        settings=None,
        client=client,
        safety=SafetyLayer(auto_approve=True, ttl_minutes=30, audit_log=audit),
        audit=audit,
    )

    result = _tools(ctx)["get_recommendations"](customer_id="1234567890")

    assert result["count"] == 0
    assert "recommendation.dismissed = FALSE" in queries[0]
    assert "recommendation.status" not in queries[0]
