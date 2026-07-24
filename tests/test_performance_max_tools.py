"""Tests for tools/performance_max.py — campaign shell + asset group creation."""

from __future__ import annotations

import pytest

from google_ads_mcp import tools

from conftest import FakeMutateResult, build_ctx, register_module


def test_create_performance_max_campaign_rejects_both_targets():
    ctx = build_ctx(lambda *a, **k: None)
    tool_fns = register_module(tools.performance_max, ctx)

    with pytest.raises(ValueError, match="at most one"):
        tool_fns["create_performance_max_campaign"](
            customer_id="123",
            name="PMax Test",
            campaign_budget_resource_name="customers/123/campaignBudgets/1",
            target_cpa=100,
            target_roas=4.0,
        )


def test_create_performance_max_campaign_defaults_to_maximize_conversions():
    calls = []

    def fake_mutate(service_name, customer_id, operations, **kwargs):
        calls.append(service_name)
        return FakeMutateResult("customers/123/campaigns/999")

    ctx = build_ctx(fake_mutate)
    tool_fns = register_module(tools.performance_max, ctx)

    result = tool_fns["create_performance_max_campaign"](
        customer_id="123",
        name="PMax Test",
        campaign_budget_resource_name="customers/123/campaignBudgets/1",
    )

    assert calls == ["CampaignService"]
    assert result["status"] == "executed"


def test_create_asset_group_creates_assets_then_group_then_links():
    calls = []

    def fake_mutate(service_name, customer_id, operations, **kwargs):
        op_count = len(list(operations))
        calls.append((service_name, op_count))
        if service_name == "AssetService":
            # 4 headlines + 1 long headline + 2 descriptions + 1 business name = 8
            return FakeMutateResult(*[f"customers/123/assets/{i}" for i in range(op_count)])
        if service_name == "AssetGroupService":
            return FakeMutateResult("customers/123/assetGroups/555")
        if service_name == "AssetGroupAssetService":
            return FakeMutateResult(*[f"link-{i}" for i in range(op_count)])
        raise AssertionError(f"unexpected service {service_name}")

    ctx = build_ctx(fake_mutate)
    tool_fns = register_module(tools.performance_max, ctx)

    result = tool_fns["create_asset_group"](
        customer_id="123",
        campaign_id="456",
        name="AG Cambridge",
        final_urls=["https://cambridge.com.ar"],
        headlines=["Aprendé inglés", "Cambridge oficial", "Cursos 2026", "Certificación"],
        long_headline="El instituto de inglés más reconocido de Buenos Aires",
        descriptions=["Inscribite ya", "Clases presenciales y online"],
        business_name="Instituto Cambridge",
    )

    service_order = [c[0] for c in calls]
    assert service_order == ["AssetService", "AssetGroupService", "AssetGroupAssetService"]

    asset_call = next(c for c in calls if c[0] == "AssetService")
    # 4 headlines + 1 long_headline + 2 descriptions + 1 business_name = 8 text assets
    assert asset_call[1] == 8

    link_call = next(c for c in calls if c[0] == "AssetGroupAssetService")
    assert link_call[1] == 8  # one link per text asset

    assert result["status"] == "executed"
    assert result["result"]["assets_created"] == 8
    assert result["result"]["assets_linked"] == 8


def test_create_asset_group_rejects_too_few_headlines():
    ctx = build_ctx(lambda *a, **k: None)
    tool_fns = register_module(tools.performance_max, ctx)

    with pytest.raises(ValueError, match="3 and 5 headlines"):
        tool_fns["create_asset_group"](
            customer_id="123",
            campaign_id="456",
            name="AG",
            final_urls=["https://example.com"],
            headlines=["Only one"],
            long_headline="x",
            descriptions=["y"],
            business_name="Biz",
        )


def test_create_asset_group_rejects_long_long_headline():
    ctx = build_ctx(lambda *a, **k: None)
    tool_fns = register_module(tools.performance_max, ctx)

    with pytest.raises(ValueError, match="90 characters"):
        tool_fns["create_asset_group"](
            customer_id="123",
            campaign_id="456",
            name="AG",
            final_urls=["https://example.com"],
            headlines=["a", "b", "c"],
            long_headline="x" * 91,
            descriptions=["y"],
            business_name="Biz",
        )
