"""Tests for image/promotion assets and visual ad creation."""

from __future__ import annotations

import pytest
from conftest import build_ctx, register_module

from google_ads_mcp import tools


def test_create_image_asset_is_atomic(monkeypatch):
    calls = []

    def fake_mutate(service_name, customer_id, operations, **kwargs):
        operation_list = list(operations)
        calls.append((service_name, len(operation_list)))
        return {"atomic": True}

    monkeypatch.setattr(
        tools.assets,
        "fetch_public_https_image",
        lambda *a, **k: b"fake-image-bytes",
    )
    ctx = build_ctx(fake_mutate)
    tool_fns = register_module(tools.assets, ctx)
    result = tool_fns["create_image_asset"](
        customer_id="123",
        campaign_id="456",
        image_url="https://example.com/logo.png",
        name="Logo",
    )

    assert calls == [("GoogleAdsService", 2)]
    assert result["status"] == "executed"


def test_create_promotion_asset_requires_exactly_one_discount_kind():
    ctx = build_ctx(lambda *a, **k: None)
    tool_fns = register_module(tools.assets, ctx)

    with pytest.raises(ValueError, match="exactly one"):
        tool_fns["create_promotion_asset"](
            customer_id="123",
            campaign_id="456",
            promotion_target="Curso Regular 2026",
            discount_percent=20,
            money_amount_off=5000,
        )

    with pytest.raises(ValueError, match="exactly one"):
        tool_fns["create_promotion_asset"](
            customer_id="123",
            campaign_id="456",
            promotion_target="Curso Regular 2026",
        )


def test_create_promotion_asset_percent_off_is_atomic():
    calls = []

    def fake_mutate(service_name, customer_id, operations, **kwargs):
        operation_list = list(operations)
        calls.append((service_name, len(operation_list)))
        return {"atomic": True}

    ctx = build_ctx(fake_mutate)
    tool_fns = register_module(tools.assets, ctx)
    result = tool_fns["create_promotion_asset"](
        customer_id="123",
        campaign_id="456",
        promotion_target="Curso Regular 2026",
        discount_percent=20,
    )

    assert calls == [("GoogleAdsService", 2)]
    assert result["status"] == "executed"


def test_create_responsive_display_ad_requires_square_image():
    ctx = build_ctx(lambda *a, **k: None)
    tool_fns = register_module(tools.ads, ctx)

    with pytest.raises(ValueError, match="square_marketing_image_urls"):
        tool_fns["create_responsive_display_ad"](
            customer_id="123",
            ad_group_id="1",
            headlines=["Aprendé inglés"],
            long_headline="El instituto de inglés más reconocido",
            descriptions=["Inscribite ya"],
            business_name="Cambridge",
            final_urls=["https://cambridge.com.ar"],
            marketing_image_urls=["https://example.com/landscape.png"],
        )


def test_create_responsive_display_ad_is_atomic(monkeypatch):
    calls = []

    def fake_mutate(service_name, customer_id, operations, **kwargs):
        operation_list = list(operations)
        calls.append((service_name, len(operation_list)))
        return {"atomic": True, "operation_count": len(operation_list)}

    monkeypatch.setattr(
        tools.ads,
        "fetch_public_https_image",
        lambda *a, **k: b"fake-image-bytes",
    )
    ctx = build_ctx(fake_mutate)
    tool_fns = register_module(tools.ads, ctx)
    result = tool_fns["create_responsive_display_ad"](
        customer_id="123",
        ad_group_id="1",
        headlines=["Aprendé inglés"],
        long_headline="El instituto de inglés más reconocido",
        descriptions=["Inscribite ya"],
        business_name="Cambridge",
        final_urls=["https://cambridge.com.ar"],
        marketing_image_urls=["https://example.com/marketing.png"],
        square_marketing_image_urls=["https://example.com/square.png"],
    )

    assert calls == [("GoogleAdsService", 3)]
    assert result["status"] == "executed"
    assert result["result"]["atomic"] is True


def test_create_video_ad_legacy_compatibility_never_mutates():
    calls = []

    def fake_mutate(service_name, customer_id, operations, **kwargs):
        calls.append(service_name)
        return {"unexpected": True}

    ctx = build_ctx(fake_mutate)
    tool_fns = register_module(tools.ads, ctx)
    result = tool_fns["create_video_ad"](
        customer_id="123",
        ad_group_id="1",
        youtube_video_id="dQw4w9WgXcQ",
        headline="This legacy argument is intentionally ignored",
        final_urls=["https://cambridge.com.ar"],
    )

    assert calls == []
    assert result["status"] == "unsupported"
    assert result["replacement_tool"] == "create_demand_gen_video_ad"
    assert "No Google Ads mutation was attempted" in result["reason"]


def test_create_video_ad_preserves_old_signature_for_clients():
    ctx = build_ctx(lambda *a, **k: None)
    tool_fns = register_module(tools.ads, ctx)
    result = tool_fns["create_video_ad"](
        customer_id="123",
        ad_group_id="1",
        youtube_video_id="dQw4w9WgXcQ",
        headline="Mirá el video",
        final_urls=["https://cambridge.com.ar"],
        description1="Compat",
        description2="Compat",
        companion_banner_asset_resource_name="customers/123/assets/1",
    )

    assert result["status"] == "unsupported"
    assert result["customer_id"] == "123"
    assert result["ad_group_id"] == "1"
    assert result["youtube_video_id"] == "dQw4w9WgXcQ"
