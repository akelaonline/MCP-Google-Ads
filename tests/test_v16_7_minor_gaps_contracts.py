"""v25 contract tests for the 0.16.7 minor-gap tools."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from google.ads.googleads.client import GoogleAdsClient
from google.oauth2.credentials import Credentials

from google_ads_mcp.tools import bidding, campaigns, reporting


class _FakeMcp:
    def __init__(self):
        self.tools = {}

    def tool(self, function=None, *args, **kwargs):
        def register(func):
            self.tools[kwargs.get("name") or func.__name__] = func
            return func

        if function is None:
            return register
        return register(function)


class _CapturingSafety:
    def __init__(self):
        self.last = None

    def propose(self, **kwargs):
        self.last = kwargs
        return {
            "status": "pending_confirmation",
            "pending_action_id": "test-action",
            "risk_alias": kwargs["tool_name"],
        }


def _raw_client() -> GoogleAdsClient:
    return GoogleAdsClient(
        credentials=Credentials(token="contract-token"),
        developer_token="contract-developer-token",
        version="v25",
        use_proto_plus=True,
    )


class _CaptureClient:
    def __init__(self):
        self.raw = _raw_client()
        self.last_mutate = None
        self.searches = []

    def assert_customer_allowed(self, customer_id: str) -> str:
        value = str(customer_id).replace("-", "").strip()
        if value != "1111111111":
            raise AssertionError(f"unexpected customer {value}")
        return value

    def search(self, customer_id: str, query: str):
        self.searches.append(query)
        return []

    def mutate(
        self,
        service_name: str,
        customer_id: str,
        operations,
        *,
        partial_failure: bool = False,
        validate_only: bool = False,
        **kwargs,
    ):
        customer_id = self.assert_customer_allowed(customer_id)
        self.last_mutate = {
            "service_name": service_name,
            "customer_id": customer_id,
            "operations": list(operations),
            "partial_failure": partial_failure,
            "validate_only": validate_only,
        }
        return SimpleNamespace(results=[])


def _propose_and_execute(module, tool_name: str, **kwargs):
    client = _CaptureClient()
    safety = _CapturingSafety()
    mcp = _FakeMcp()
    module.register(mcp, SimpleNamespace(client=client, safety=safety))
    assert tool_name in mcp.tools
    response = mcp.tools[tool_name](customer_id="111-111-1111", **kwargs)
    assert response["status"] == "pending_confirmation"
    safety.last["execute"]()
    return client.last_mutate


def test_set_campaign_excluded_asset_field_types_builds_mask():
    call = _propose_and_execute(
        campaigns,
        "set_campaign_excluded_asset_field_types",
        campaign_id="123",
        field_types=["SITELINK", "CALLOUT", "sitelink"],
    )
    assert call["service_name"] == "CampaignService"
    op = call["operations"][0]
    assert op.update.resource_name == "customers/1111111111/campaigns/123"
    assert list(op.update.excluded_parent_asset_field_types) == [13, 11]  # deduped
    assert op.update_mask.paths == ["excluded_parent_asset_field_types"]


def test_set_campaign_excluded_asset_field_types_clears_with_empty_list():
    call = _propose_and_execute(
        campaigns,
        "set_campaign_excluded_asset_field_types",
        campaign_id="123",
        field_types=[],
    )
    op = call["operations"][0]
    assert list(op.update.excluded_parent_asset_field_types) == []
    assert op.update_mask.paths == ["excluded_parent_asset_field_types"]


def test_set_campaign_excluded_asset_field_types_rejects_unknown():
    client = _CaptureClient()
    safety = _CapturingSafety()
    mcp = _FakeMcp()
    campaigns.register(mcp, SimpleNamespace(client=client, safety=safety))

    with pytest.raises(ValueError, match="Unknown AssetFieldType"):
        mcp.tools["set_campaign_excluded_asset_field_types"](
            customer_id="111-111-1111",
            campaign_id="123",
            field_types=["NOT_A_TYPE"],
        )


def test_update_campaign_dates_builds_valid_mask():
    call = _propose_and_execute(
        campaigns,
        "update_campaign_dates",
        campaign_id="123",
        end_date="2026-12-31",
    )
    op = call["operations"][0]
    assert op.update.resource_name == "customers/1111111111/campaigns/123"
    assert op.update.end_date_time == "20261231 23:59:59"
    assert op.update_mask.paths == ["end_date_time"]


def test_update_campaign_dates_both_dates():
    call = _propose_and_execute(
        campaigns,
        "update_campaign_dates",
        campaign_id="123",
        start_date="2026-09-01",
        end_date="2026-12-31",
    )
    op = call["operations"][0]
    assert op.update.start_date_time == "20260901 00:00:00"
    assert op.update.end_date_time == "20261231 23:59:59"
    assert sorted(op.update_mask.paths) == ["end_date_time", "start_date_time"]


def test_update_campaign_dates_requires_a_date():
    client = _CaptureClient()
    safety = _CapturingSafety()
    mcp = _FakeMcp()
    campaigns.register(mcp, SimpleNamespace(client=client, safety=safety))

    with pytest.raises(ValueError, match="at least one"):
        mcp.tools["update_campaign_dates"](
            customer_id="111-111-1111", campaign_id="123"
        )


def test_change_history_filters_build_valid_query():
    client = _CaptureClient()
    safety = _CapturingSafety()
    mcp = _FakeMcp()
    reporting.register(mcp, SimpleNamespace(client=client, safety=safety))
    result = mcp.tools["get_change_history"](
        customer_id="111-111-1111",
        days=7,
        resource_type="CAMPAIGN",
        operation="SET",
        user_email="juan@agency.com",
    )
    assert result["filters"] == {
        "resource_type": "CAMPAIGN",
        "operation": "SET",
        "user_email": "juan@agency.com",
    }
    query = client.searches[0]
    assert "change_resource_type = CAMPAIGN" in query
    assert "resource_change_operation = SET" in query
    assert "change_event.user_email = 'juan@agency.com'" in query


def test_change_history_rejects_bad_operation():
    client = _CaptureClient()
    safety = _CapturingSafety()
    mcp = _FakeMcp()
    reporting.register(mcp, SimpleNamespace(client=client, safety=safety))

    with pytest.raises(ValueError, match="ADD, SET, or REMOVE"):
        mcp.tools["get_change_history"](
            customer_id="111-111-1111", operation="DELETE"
        )


def test_set_target_cpa_with_ceiling_and_floor():
    call = _propose_and_execute(
        bidding,
        "set_target_cpa",
        campaign_id="123",
        target_cpa=10.0,
        cpc_bid_ceiling=5.0,
        cpc_bid_floor=0.5,
    )
    op = call["operations"][0]
    assert op.update.target_cpa.target_cpa_micros == 10000000
    assert op.update.target_cpa.cpc_bid_ceiling_micros == 5000000
    assert op.update.target_cpa.cpc_bid_floor_micros == 500000
    assert sorted(op.update_mask.paths) == [
        "target_cpa.cpc_bid_ceiling_micros",
        "target_cpa.cpc_bid_floor_micros",
        "target_cpa.target_cpa_micros",
    ]


def test_set_target_roas_with_ceiling():
    call = _propose_and_execute(
        bidding,
        "set_target_roas",
        campaign_id="123",
        target_roas=3.0,
        cpc_bid_ceiling=4.0,
    )
    op = call["operations"][0]
    assert op.update.target_roas.target_roas == 3.0
    assert op.update.target_roas.cpc_bid_ceiling_micros == 4000000
    assert op.update_mask.paths == [
        "target_roas.target_roas",
        "target_roas.cpc_bid_ceiling_micros",
    ]


def test_set_target_cpa_rejects_floor_above_ceiling():
    client = _CaptureClient()
    safety = _CapturingSafety()
    mcp = _FakeMcp()
    bidding.register(mcp, SimpleNamespace(client=client, safety=safety))

    with pytest.raises(ValueError, match="cannot exceed"):
        mcp.tools["set_target_cpa"](
            customer_id="111-111-1111",
            campaign_id="123",
            target_cpa=10.0,
            cpc_bid_ceiling=1.0,
            cpc_bid_floor=2.0,
        )
