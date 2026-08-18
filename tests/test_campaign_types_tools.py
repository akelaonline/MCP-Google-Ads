"""Tests for v25 specialized campaign types."""

from __future__ import annotations

import pytest
from conftest import FakeMutateResult, build_ctx, register_module

from google_ads_mcp import tools
from google_ads_mcp.errors import GoogleAdsMcpError


def test_create_shopping_campaign_calls_campaign_service():
    calls = []

    def fake_mutate(service_name, customer_id, operations, **kwargs):
        calls.append(service_name)
        return FakeMutateResult("customers/123/campaigns/1")

    ctx = build_ctx(fake_mutate)
    tool_fns = register_module(tools.campaign_types, ctx)
    result = tool_fns["create_shopping_campaign"](
        customer_id="123",
        name="Shopping Test",
        campaign_budget_resource_name="customers/123/campaignBudgets/1",
        merchant_center_id="9999",
    )

    assert calls == ["CampaignService"]
    assert result["status"] == "executed"
    assert "Standard Shopping" in result["description"]


def test_create_shopping_campaign_with_target_roas():
    calls = []

    def fake_mutate(service_name, customer_id, operations, **kwargs):
        calls.append(service_name)
        return FakeMutateResult("customers/123/campaigns/2")

    ctx = build_ctx(fake_mutate)
    tool_fns = register_module(tools.campaign_types, ctx)
    result = tool_fns["create_shopping_campaign"](
        customer_id="123",
        name="Shopping ROAS Test",
        campaign_budget_resource_name="customers/123/campaignBudgets/1",
        merchant_center_id="9999",
        target_roas=4.0,
    )

    assert calls == ["CampaignService"]
    assert result["status"] == "executed"


def test_smart_shopping_is_rejected_in_favor_of_pmax():
    ctx = build_ctx(lambda *a, **k: None)
    tool_fns = register_module(tools.campaign_types, ctx)

    with pytest.raises(ValueError, match="create_performance_max_campaign"):
        tool_fns["create_shopping_campaign"](
            customer_id="123",
            name="Legacy Smart Shopping",
            campaign_budget_resource_name="customers/123/campaignBudgets/1",
            merchant_center_id="9999",
            campaign_type="SMART_SHOPPING",
        )


def test_legacy_local_campaign_never_mutates():
    calls = []

    def fake_mutate(*args, **kwargs):
        calls.append(args)

    ctx = build_ctx(fake_mutate)
    tool_fns = register_module(tools.campaign_types, ctx)

    with pytest.raises(GoogleAdsMcpError, match="create_performance_max_campaign"):
        tool_fns["create_local_campaign"](
            customer_id="123",
            name="Local Test",
            campaign_budget_resource_name="customers/123/campaignBudgets/1",
            business_name="Instituto Cambridge",
            headlines=["Aprendé inglés cerca tuyo"],
            descriptions=["Visitanos en nuestra sede"],
            final_url="https://cambridge.com.ar",
        )

    assert calls == []
