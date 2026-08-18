"""Tests for tools/performance_max.py."""

from __future__ import annotations

import pytest
from conftest import FakeMutateResult, build_ctx, register_module

from google_ads_mcp import tools


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


def test_create_asset_group_is_one_atomic_mutation(monkeypatch):
    calls = []

    def fake_mutate(service_name, customer_id, operations, **kwargs):
        operation_list = list(operations)
        calls.append((service_name, len(operation_list)))
        return {"atomic": True, "operation_count": len(operation_list)}

    monkeypatch.setattr(
        tools.performance_max,
        "fetch_public_https_image",
        lambda *a, **k: b"fake-image-bytes",
    )
    ctx = build_ctx(fake_mutate)
    tool_fns = register_module(tools.performance_max, ctx)

    result = tool_fns["create_asset_group"](
        customer_id="123",
        campaign_id="456",
        name="AG Cambridge",
        final_urls=["https://cambridge.com.ar"],
        headlines=["Aprendé inglés", "Cambridge oficial", "Cursos 2026"],
        long_headline="El instituto de inglés más reconocido de Buenos Aires",
        descriptions=["Inscribite ya", "Clases presenciales y online"],
        business_name="Instituto Cambridge",
        marketing_image_urls=["https://example.com/landscape.jpg"],
        square_marketing_image_urls=["https://example.com/square.jpg"],
        logo_image_urls=["https://example.com/logo.jpg"],
    )

    assert len(calls) == 1
    assert calls[0][0] == "GoogleAdsService"
    # 3 headlines + long + 2 descriptions + business + 3 images = 10 assets,
    # plus 1 AssetGroup and 10 AssetGroupAsset links = 21 operations.
    assert calls[0][1] == 21
    assert result["status"] == "executed"
    assert result["result"]["atomic"] is True


def test_create_asset_group_rejects_missing_required_images():
    ctx = build_ctx(lambda *a, **k: None)
    tool_fns = register_module(tools.performance_max, ctx)

    with pytest.raises(ValueError, match="landscape marketing image"):
        tool_fns["create_asset_group"](
            customer_id="123",
            campaign_id="456",
            name="AG",
            final_urls=["https://example.com"],
            headlines=["a", "b", "c"],
            long_headline="Long headline",
            descriptions=["Short desc", "Second description"],
            business_name="Biz",
        )


def test_create_asset_group_rejects_too_few_headlines():
    ctx = build_ctx(lambda *a, **k: None)
    tool_fns = register_module(tools.performance_max, ctx)

    with pytest.raises(ValueError, match="3-15 headlines"):
        tool_fns["create_asset_group"](
            customer_id="123",
            campaign_id="456",
            name="AG",
            final_urls=["https://example.com"],
            headlines=["Only one"],
            long_headline="x",
            descriptions=["one", "two"],
            business_name="Biz",
            marketing_image_urls=["https://example.com/a.jpg"],
            square_marketing_image_urls=["https://example.com/b.jpg"],
            logo_image_urls=["https://example.com/c.jpg"],
        )


def test_create_asset_group_requires_short_description():
    ctx = build_ctx(lambda *a, **k: None)
    tool_fns = register_module(tools.performance_max, ctx)

    with pytest.raises(ValueError, match="60 characters"):
        tool_fns["create_asset_group"](
            customer_id="123",
            campaign_id="456",
            name="AG",
            final_urls=["https://example.com"],
            headlines=["a", "b", "c"],
            long_headline="x",
            descriptions=["x" * 61, "y" * 61],
            business_name="Biz",
            marketing_image_urls=["https://example.com/a.jpg"],
            square_marketing_image_urls=["https://example.com/b.jpg"],
            logo_image_urls=["https://example.com/c.jpg"],
        )
