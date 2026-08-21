"""Tests for app campaign creation tools."""

from __future__ import annotations

import pytest
from conftest import FakeMutateResult, build_ctx, register_module

from google_ads_mcp import tools


def test_create_app_campaign_validates_app_store():
    ctx = build_ctx(lambda *a, **k: None)
    tool_fns = register_module(tools.app_campaigns, ctx)

    with pytest.raises(ValueError, match="app_store must be"):
        tool_fns["create_app_campaign"](
            customer_id="123",
            name="App Campaign",
            campaign_budget_resource_name="customers/123/campaignBudgets/1",
            app_id="com.example.app",
            app_store="AMAZON",
            bidding_strategy_goal_type="OPTIMIZE_INSTALLS_TARGET_INSTALL_COST",
            target_cpa=2.0,
        )


def test_create_app_campaign_rejects_unknown_goal():
    ctx = build_ctx(lambda *a, **k: None)
    tool_fns = register_module(tools.app_campaigns, ctx)

    with pytest.raises(ValueError, match="Unknown bidding_strategy_goal_type"):
        tool_fns["create_app_campaign"](
            customer_id="123",
            name="App Campaign",
            campaign_budget_resource_name="customers/123/campaignBudgets/1",
            app_id="com.example.app",
            app_store="GOOGLE_APP_STORE",
            bidding_strategy_goal_type="OPTIMIZE_FOR_INSTALLS",
        )


def test_create_app_campaign_requires_target_for_targeted_goal():
    ctx = build_ctx(lambda *a, **k: None)
    tool_fns = register_module(tools.app_campaigns, ctx)

    with pytest.raises(ValueError, match="requires target_cpa"):
        tool_fns["create_app_campaign"](
            customer_id="123",
            name="App Campaign",
            campaign_budget_resource_name="customers/123/campaignBudgets/1",
            app_id="com.example.app",
            app_store="GOOGLE_APP_STORE",
            bidding_strategy_goal_type="OPTIMIZE_INSTALLS_TARGET_INSTALL_COST",
        )


def test_create_app_campaign_proposes_campaign_service():
    calls = []

    def fake_mutate(service_name, customer_id, operations, **kwargs):
        calls.append(service_name)
        return FakeMutateResult("customers/123/campaigns/1")

    ctx = build_ctx(fake_mutate)
    tool_fns = register_module(tools.app_campaigns, ctx)
    result = tool_fns["create_app_campaign"](
        customer_id="123",
        name="App Campaign",
        campaign_budget_resource_name="customers/123/campaignBudgets/1",
        app_id="com.example.app",
        app_store="GOOGLE_APP_STORE",
        bidding_strategy_goal_type="OPTIMIZE_INSTALLS_TARGET_INSTALL_COST",
        target_cpa=2.5,
    )

    assert calls == ["CampaignService"]
    assert result["status"] == "executed"
    assert "created PAUSED" in result["description"]


def test_create_app_campaign_rejects_non_positive_target_cpa():
    ctx = build_ctx(lambda *a, **k: None)
    tool_fns = register_module(tools.app_campaigns, ctx)

    with pytest.raises(ValueError, match="target_cpa must be greater than 0"):
        tool_fns["create_app_campaign"](
            customer_id="123",
            name="App Campaign",
            campaign_budget_resource_name="customers/123/campaignBudgets/1",
            app_id="com.example.app",
            app_store="GOOGLE_APP_STORE",
            bidding_strategy_goal_type="OPTIMIZE_INSTALLS_TARGET_INSTALL_COST",
            target_cpa=0,
        )
