"""Tests for create_image_asset / create_promotion_asset (tools/assets.py)
and create_responsive_display_ad / create_video_ad (tools/ads.py).
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from google_ads_mcp import tools

from conftest import FakeMutateResult, build_ctx, register_module


class _FakeHttpResponse:
    def __init__(self, data: bytes):
        self._data = data

    def read(self):
        return self._data

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_create_image_asset_downloads_then_creates_then_links():
    calls = []

    def fake_mutate(service_name, customer_id, operations, **kwargs):
        calls.append(service_name)
        if service_name == "AssetService":
            return FakeMutateResult("customers/123/assets/1")
        return FakeMutateResult("customers/123/campaignAssets/456~1~IMAGE")

    ctx = build_ctx(fake_mutate)
    tool_fns = register_module(tools.assets, ctx)

    with patch(
        "urllib.request.urlopen", return_value=_FakeHttpResponse(b"fake-image-bytes")
    ):
        result = tool_fns["create_image_asset"](
            customer_id="123",
            campaign_id="456",
            image_url="https://example.com/logo.png",
            name="Logo",
        )

    assert calls == ["AssetService", "CampaignAssetService"]
    assert result["status"] == "executed"
    assert result["result"]["bytes_uploaded"] == len(b"fake-image-bytes")


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
            customer_id="123", campaign_id="456", promotion_target="Curso Regular 2026"
        )


def test_create_promotion_asset_percent_off_creates_then_links():
    calls = []

    def fake_mutate(service_name, customer_id, operations, **kwargs):
        calls.append(service_name)
        if service_name == "AssetService":
            return FakeMutateResult("customers/123/assets/2")
        return FakeMutateResult("customers/123/campaignAssets/456~2~PROMOTION")

    ctx = build_ctx(fake_mutate)
    tool_fns = register_module(tools.assets, ctx)

    result = tool_fns["create_promotion_asset"](
        customer_id="123",
        campaign_id="456",
        promotion_target="Curso Regular 2026",
        discount_percent=20,
    )

    assert calls == ["AssetService", "CampaignAssetService"]
    assert result["status"] == "executed"


def test_create_responsive_display_ad_validates_headlines():
    ctx = build_ctx(lambda *a, **k: None)
    tool_fns = register_module(tools.ads, ctx)

    with pytest.raises(ValueError, match="1 and 5 headlines"):
        tool_fns["create_responsive_display_ad"](
            customer_id="123",
            ad_group_id="1",
            headlines=[],
            long_headline="x",
            descriptions=["y"],
            business_name="Biz",
            final_urls=["https://example.com"],
        )


def test_create_responsive_display_ad_uploads_images_then_creates_ad():
    calls = []

    def fake_mutate(service_name, customer_id, operations, **kwargs):
        calls.append(service_name)
        if service_name == "AssetService":
            return FakeMutateResult("customers/123/assets/3")
        return FakeMutateResult("customers/123/adGroupAds/1~2")

    ctx = build_ctx(fake_mutate)
    tool_fns = register_module(tools.ads, ctx)

    with patch(
        "urllib.request.urlopen", return_value=_FakeHttpResponse(b"fake-image-bytes")
    ):
        result = tool_fns["create_responsive_display_ad"](
            customer_id="123",
            ad_group_id="1",
            headlines=["Aprendé inglés"],
            long_headline="El instituto de inglés más reconocido",
            descriptions=["Inscribite ya"],
            business_name="Instituto Cambridge",
            final_urls=["https://cambridge.com.ar"],
            marketing_image_urls=["https://example.com/marketing.png"],
        )

    assert "AssetService" in calls
    assert "AdGroupAdService" in calls
    assert result["status"] == "executed"


def test_create_video_ad_validates_headline_length():
    ctx = build_ctx(lambda *a, **k: None)
    tool_fns = register_module(tools.ads, ctx)

    with pytest.raises(ValueError, match="15 characters"):
        tool_fns["create_video_ad"](
            customer_id="123",
            ad_group_id="1",
            youtube_video_id="dQw4w9WgXcQ",
            headline="This headline is way too long",
            final_urls=["https://example.com"],
        )


def test_create_video_ad_creates_ad_group_ad():
    calls = []

    def fake_mutate(service_name, customer_id, operations, **kwargs):
        calls.append(service_name)
        return FakeMutateResult("customers/123/adGroupAds/1~3")

    ctx = build_ctx(fake_mutate)
    tool_fns = register_module(tools.ads, ctx)

    result = tool_fns["create_video_ad"](
        customer_id="123",
        ad_group_id="1",
        youtube_video_id="dQw4w9WgXcQ",
        headline="Mirá el video",
        final_urls=["https://cambridge.com.ar"],
    )

    assert calls == ["AdGroupAdService"]
    assert result["status"] == "executed"
