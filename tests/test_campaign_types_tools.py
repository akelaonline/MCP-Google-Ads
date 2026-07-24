"""Tests for tools/campaign_types.py — Shopping and Local campaign creation."""

from __future__ import annotations

from google_ads_mcp import tools

from conftest import FakeMutateResult, build_ctx, register_module


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
    assert "requires the product feed" in result["description"]


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


def test_create_local_campaign_validates_headlines():
    import pytest

    ctx = build_ctx(lambda *a, **k: None)
    tool_fns = register_module(tools.campaign_types, ctx)

    with pytest.raises(ValueError, match="1 and 5 headlines"):
        tool_fns["create_local_campaign"](
            customer_id="123",
            name="Local Test",
            campaign_budget_resource_name="customers/123/campaignBudgets/1",
            business_name="Instituto Cambridge",
            headlines=[],
            descriptions=["y"],
            final_url="https://cambridge.com.ar",
        )


def test_create_local_campaign_creates_then_creates_asset_then_links():
    calls = []

    def fake_mutate(service_name, customer_id, operations, **kwargs):
        calls.append(service_name)
        if service_name == "CampaignService":
            return FakeMutateResult("customers/123/campaigns/3")
        if service_name == "AssetService":
            return FakeMutateResult("customers/123/assets/5")
        return FakeMutateResult("customers/123/campaignAssets/3~5~LOCAL")

    ctx = build_ctx(fake_mutate)
    tool_fns = register_module(tools.campaign_types, ctx)

    result = tool_fns["create_local_campaign"](
        customer_id="123",
        name="Local Test",
        campaign_budget_resource_name="customers/123/campaignBudgets/1",
        business_name="Instituto Cambridge",
        headlines=["Aprendé inglés cerca tuyo"],
        descriptions=["Visitanos en nuestra sede"],
        final_url="https://cambridge.com.ar",
    )

    assert calls == ["CampaignService", "AssetService", "CampaignAssetService"]
    assert result["status"] == "executed"
