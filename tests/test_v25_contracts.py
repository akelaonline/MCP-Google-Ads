"""Contract tests against Google's real v25 generated protobuf surface.

Unlike the lightweight AutoVivify unit fakes, these tests fail immediately if
we refer to a removed field, enum, resource, operation, or service path.
They make no network requests and do not require Google Ads credentials.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from conftest import FakeAuditLog, FakeMcp
from google.ads.googleads.client import GoogleAdsClient
from google.oauth2.credentials import Credentials

from google_ads_mcp.context import AppContext
from google_ads_mcp.safety import SafetyLayer
from google_ads_mcp.tools import ads, assets, campaigns, performance_max


def _raw_client() -> GoogleAdsClient:
    return GoogleAdsClient(
        credentials=Credentials(token="contract-test-token"),
        developer_token="contract-test-developer-token",
        version="v25",
        use_proto_plus=True,
    )


def _normalize_customer(customer_id: str) -> str:
    value = str(customer_id).replace("-", "").strip()
    if not value.isdigit():
        raise ValueError("customer_id must be numeric")
    return value


def _assert_owned(customer_id: str, resource_name: str, **kwargs) -> str:
    customer = _normalize_customer(customer_id)
    value = str(resource_name).strip()
    root = f"customers/{customer}"
    if value != root and not value.startswith(root + "/"):
        raise ValueError("resource belongs to another customer")
    return value


def _ctx():
    captured = []
    raw = _raw_client()

    def mutate(service_name, customer_id, operations, **kwargs):
        operation_list = list(operations)
        captured.append((service_name, customer_id, operation_list, kwargs))
        return {"service": service_name, "operation_count": len(operation_list)}

    def mutate_atomic(customer_id, operations, **kwargs):
        operation_list = list(operations)
        captured.append(("GoogleAdsService", customer_id, operation_list, kwargs))
        return {"service": "GoogleAdsService", "operation_count": len(operation_list)}

    client = SimpleNamespace(
        raw=raw,
        mutate=mutate,
        mutate_atomic=mutate_atomic,
        assert_customer_allowed=_normalize_customer,
        assert_resource_name_customer=_assert_owned,
    )
    audit = FakeAuditLog()
    safety = SafetyLayer(auto_approve=True, ttl_minutes=30, audit_log=audit)
    return AppContext(settings=None, client=client, safety=safety, audit=audit), captured


def _register(module, ctx):
    mcp = FakeMcp()
    module.register(mcp, ctx)
    return mcp.registered


def test_campaign_create_uses_v25_dates_and_required_political_declaration():
    ctx, captured = _ctx()
    tool = _register(campaigns, ctx)["create_campaign"]

    result = tool(
        customer_id="1234567890",
        name="Contract Search",
        campaign_budget_resource_name="customers/1234567890/campaignBudgets/111",
        start_date="2026-08-19",
        end_date="2026-08-31",
    )

    assert result["status"] == "executed"
    service, _, operations, _ = captured[0]
    assert service == "CampaignService"
    campaign = operations[0].create
    assert campaign.start_date_time == "20260819 00:00:00"
    assert campaign.end_date_time == "20260831 23:59:59"
    assert int(campaign.contains_eu_political_advertising) != 0


def test_rsa_update_builds_real_ad_operation_for_ad_service():
    ctx, captured = _ctx()
    tool = _register(ads, ctx)["update_responsive_search_ad"]

    result = tool(
        customer_id="1234567890",
        ad_group_id="222",
        ad_id="333",
        headlines=["Uno", "Dos", "Tres"],
        descriptions=["Descripción uno", "Descripción dos"],
        final_urls=["https://example.com"],
    )

    assert result["status"] == "executed"
    service, _, operations, _ = captured[0]
    assert service == "AdService"
    operation = operations[0]
    assert operation.update.resource_name.endswith("/ads/333")
    assert len(operation.update.responsive_search_ad.headlines) == 3
    assert list(operation.update.final_urls) == ["https://example.com"]


def test_legacy_call_ad_tool_builds_rsa_plus_call_asset_atomically():
    ctx, captured = _ctx()
    tool = _register(ads, ctx)["create_call_ad"]

    result = tool(
        customer_id="1234567890",
        ad_group_id="222",
        country_code="AR",
        phone_number="+541112345678",
        business_name="Akela",
        headlines=["Llamanos hoy", "Atención rápida", "Hablá con nosotros"],
        descriptions=["Consultanos ahora", "Atención telefónica"],
        final_urls=["https://example.com"],
    )

    assert result["status"] == "executed"
    service, _, operations, _ = captured[0]
    assert service == "GoogleAdsService"
    assert len(operations) == 3
    assert operations[0].asset_operation.create.call_asset.phone_number == "+541112345678"
    assert len(
        operations[1].ad_group_ad_operation.create.ad.responsive_search_ad.headlines
    ) == 3
    assert int(operations[2].ad_group_asset_operation.create.field_type) != 0


def test_message_asset_builds_real_business_message_whatsapp_asset():
    ctx, captured = _ctx()
    tool = _register(assets, ctx)["create_message_asset"]

    result = tool(
        customer_id="1234567890",
        campaign_id="444",
        phone_number="1112345678",
        country_code="AR",
        business_name="Akela",
        message_text="Hola, quiero información",
        call_to_action_text="Contactanos",
    )

    assert result["status"] == "executed"
    service, _, operations, _ = captured[0]
    assert service == "GoogleAdsService"
    assert len(operations) == 2
    business_message = operations[0].asset_operation.create.business_message_asset
    assert int(business_message.message_provider) != 0
    assert business_message.whatsapp_info.country_code == "AR"
    assert business_message.whatsapp_info.phone_number == "1112345678"
    assert business_message.starter_message == "Hola, quiero información"
    assert int(operations[1].campaign_asset_operation.create.field_type) != 0


def test_pmax_campaign_uses_supported_bidding_shape_and_brand_mode():
    ctx, captured = _ctx()
    tool = _register(performance_max, ctx)["create_performance_max_campaign"]

    result = tool(
        customer_id="1234567890",
        name="Contract PMax",
        campaign_budget_resource_name="customers/1234567890/campaignBudgets/111",
        target_roas=4.0,
    )

    assert result["status"] == "executed"
    campaign = captured[0][2][0].create
    assert campaign.maximize_conversion_value.target_roas == pytest.approx(4.0)
    assert campaign.brand_guidelines_enabled is False
    assert int(campaign.contains_eu_political_advertising) != 0


def test_complete_pmax_asset_group_builds_real_v25_mutate_operations(monkeypatch):
    ctx, captured = _ctx()
    monkeypatch.setattr(
        performance_max,
        "fetch_public_https_image",
        lambda *a, **k: b"contract-image",
    )
    tool = _register(performance_max, ctx)["create_asset_group"]

    result = tool(
        customer_id="1234567890",
        campaign_id="555",
        name="Contract Asset Group",
        final_urls=["https://example.com"],
        headlines=["Headline one", "Headline two", "Headline three"],
        long_headline="This is the long headline for the Performance Max asset group",
        descriptions=["Short description", "Second longer description"],
        business_name="Akela",
        marketing_image_urls=["https://example.com/landscape.jpg"],
        square_marketing_image_urls=["https://example.com/square.jpg"],
        logo_image_urls=["https://example.com/logo.jpg"],
    )

    assert result["status"] == "executed"
    service, _, operations, _ = captured[0]
    assert service == "GoogleAdsService"
    assert len(operations) == 21
    asset_group_ops = [
        op
        for op in operations
        if op._pb.WhichOneof("operation") == "asset_group_operation"
    ]
    assert len(asset_group_ops) == 1
    assert asset_group_ops[0].asset_group_operation.create.status.name == "PAUSED"


def test_responsive_display_builds_real_atomic_v25_operations(monkeypatch):
    ctx, captured = _ctx()
    monkeypatch.setattr(
        ads,
        "fetch_public_https_image",
        lambda *a, **k: b"contract-image",
    )
    tool = _register(ads, ctx)["create_responsive_display_ad"]

    result = tool(
        customer_id="1234567890",
        ad_group_id="222",
        headlines=["Display headline"],
        long_headline="Long display headline",
        descriptions=["Display description"],
        business_name="Akela",
        final_urls=["https://example.com"],
        marketing_image_urls=["https://example.com/landscape.jpg"],
        square_marketing_image_urls=["https://example.com/square.jpg"],
    )

    assert result["status"] == "executed"
    service, _, operations, _ = captured[0]
    assert service == "GoogleAdsService"
    assert len(operations) == 3
    ad_ops = [
        op
        for op in operations
        if op._pb.WhichOneof("operation") == "ad_group_ad_operation"
    ]
    assert len(ad_ops) == 1
    rda = ad_ops[0].ad_group_ad_operation.create.ad.responsive_display_ad
    assert len(rda.marketing_images) == 1
    assert len(rda.square_marketing_images) == 1
