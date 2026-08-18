"""Tests for campaign assets and conversion action management."""

from __future__ import annotations

import pytest
from conftest import FakeMutateResult, build_ctx, register_module

from google_ads_mcp import tools


def test_create_message_asset_uses_atomic_business_message_flow():
    calls = []

    def fake_mutate(service_name, customer_id, operations, **kwargs):
        operation_list = list(operations)
        calls.append((service_name, len(operation_list)))
        return {"atomic": True, "operation_count": len(operation_list)}

    ctx = build_ctx(fake_mutate)
    tool_fns = register_module(tools.assets, ctx)
    result = tool_fns["create_message_asset"](
        customer_id="123",
        campaign_id="456",
        phone_number="1112345678",
        country_code="AR",
        business_name="Instituto Cambridge",
        message_text="Hola! Quiero info de los cursos",
        call_to_action_text="Contactanos",
    )

    assert calls == [("GoogleAdsService", 2)]
    assert result["status"] == "executed"
    assert result["result"]["atomic"] is True


def test_create_message_asset_rejects_too_long_starter_message():
    ctx = build_ctx(lambda *a, **k: None)
    tool_fns = register_module(tools.assets, ctx)

    with pytest.raises(ValueError, match="1-300"):
        tool_fns["create_message_asset"](
            customer_id="123",
            campaign_id="456",
            phone_number="1112345678",
            country_code="AR",
            business_name="Instituto Cambridge",
            message_text="x" * 301,
        )


def test_create_sitelink_asset_rejects_long_link_text():
    ctx = build_ctx(lambda *a, **k: None)
    tool_fns = register_module(tools.assets, ctx)

    with pytest.raises(ValueError, match="1-25"):
        tool_fns["create_sitelink_asset"](
            customer_id="123",
            campaign_id="456",
            link_text="x" * 26,
            final_url="https://example.com",
        )


def test_create_call_asset_is_atomic():
    calls = []

    def fake_mutate(service_name, customer_id, operations, **kwargs):
        operation_list = list(operations)
        calls.append((service_name, len(operation_list)))
        return {"atomic": True}

    ctx = build_ctx(fake_mutate)
    tool_fns = register_module(tools.assets, ctx)
    result = tool_fns["create_call_asset"](
        customer_id="123",
        campaign_id="456",
        phone_number="+541112345678",
    )

    assert calls == [("GoogleAdsService", 2)]
    assert result["status"] == "executed"


def test_update_conversion_action_status():
    calls = []

    def fake_mutate(service_name, customer_id, operations, **kwargs):
        calls.append(service_name)
        return FakeMutateResult("customers/123/conversionActions/789")

    ctx = build_ctx(fake_mutate)
    tool_fns = register_module(tools.conversions, ctx)
    result = tool_fns["update_conversion_action_status"](
        customer_id="123",
        conversion_action_id="789",
        status="REMOVED",
    )

    assert calls == ["ConversionActionService"]
    assert result["status"] == "executed"


def test_set_conversion_action_counting_maps_to_primary_for_goal():
    calls = []

    def fake_mutate(service_name, customer_id, operations, **kwargs):
        calls.append(service_name)
        return FakeMutateResult("customers/123/conversionActions/789")

    ctx = build_ctx(fake_mutate)
    tool_fns = register_module(tools.conversions, ctx)
    result = tool_fns["set_conversion_action_counting"](
        customer_id="123",
        conversion_action_id="789",
        include_in_conversions_metric=False,
    )

    assert calls == ["ConversionActionService"]
    assert result["status"] == "executed"
    assert "secondary/non-biddable" in result["description"]
    assert result["result"]["resource_names"] == [
        "customers/123/conversionActions/789"
    ]
