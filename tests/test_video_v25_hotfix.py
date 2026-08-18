"""Production guardrails for Google Ads v25 video behavior."""

from __future__ import annotations

import inspect
from types import SimpleNamespace

from conftest import FakeAuditLog, FakeMcp
from google.ads.googleads.client import GoogleAdsClient
from google.oauth2.credentials import Credentials

from google_ads_mcp.context import AppContext
from google_ads_mcp.safety import SafetyLayer
from google_ads_mcp.tools import ads


def _ctx():
    captured = []
    raw = GoogleAdsClient(
        credentials=Credentials(token="contract-test-token"),
        developer_token="contract-test-developer-token",
        version="v25",
        use_proto_plus=True,
    )

    def mutate(service_name, customer_id, operations, **kwargs):
        captured.append((service_name, customer_id, list(operations), kwargs))
        return {"service": service_name}

    def mutate_atomic(customer_id, operations, **kwargs):
        operation_list = list(operations)
        captured.append(("GoogleAdsService", customer_id, operation_list, kwargs))
        return {"service": "GoogleAdsService", "operation_count": len(operation_list)}

    client = SimpleNamespace(raw=raw, mutate=mutate, mutate_atomic=mutate_atomic)
    audit = FakeAuditLog()
    safety = SafetyLayer(auto_approve=True, ttl_minutes=30, audit_log=audit)
    return AppContext(settings=None, client=client, safety=safety, audit=audit), captured


def _tools(ctx):
    mcp = FakeMcp()
    ads.register(mcp, ctx)
    return mcp.registered


def test_legacy_video_create_is_fail_safe_and_never_mutates():
    ctx, captured = _ctx()
    result = _tools(ctx)["create_video_ad"](
        customer_id="1234567890",
        ad_group_id="222",
        youtube_video_id="abcdefghijk",
        headline="Learn more",
        final_urls=["https://example.com"],
    )

    assert result["status"] == "unsupported"
    assert result["replacement_tool"] == "create_demand_gen_video_ad"
    assert captured == []


def test_demand_gen_video_builds_real_v25_atomic_operations(monkeypatch):
    ctx, captured = _ctx()
    monkeypatch.setattr(
        ads,
        "fetch_public_https_image",
        lambda *args, **kwargs: b"contract-logo",
    )
    result = _tools(ctx)["create_demand_gen_video_ad"](
        customer_id="1234567890",
        ad_group_id="222",
        youtube_video_ids=["abcdefghijk"],
        headlines=["A short headline", "Another headline"],
        long_headlines=["A longer Demand Gen video headline"],
        descriptions=["A Demand Gen video description"],
        business_name="Akela",
        final_urls=["https://example.com"],
        logo_image_urls=["https://example.com/logo.png"],
    )

    assert result["status"] == "executed"
    service, customer_id, operations, _ = captured[0]
    assert service == "GoogleAdsService"
    assert customer_id == "1234567890"
    assert len(operations) == 3
    assert operations[0].asset_operation.create.youtube_video_asset.youtube_video_id == "abcdefghijk"
    ad_group_ad = operations[-1].ad_group_ad_operation.create
    assert ad_group_ad.status.name == "PAUSED"
    assert list(ad_group_ad.ad.final_urls) == ["https://example.com"]
    video = ad_group_ad.ad.demand_gen_video_responsive_ad
    assert video.business_name.text == "Akela"
    assert len(video.videos) == 1
    assert len(video.logo_images) == 1
    assert len(video.headlines) == 2
    assert len(video.long_headlines) == 1
    assert len(video.descriptions) == 1


def test_source_has_no_legacy_video_ad_write_path():
    source = inspect.getsource(ads)
    assert ".ad.video_ad" not in source
    assert "demand_gen_video_responsive_ad" in source
