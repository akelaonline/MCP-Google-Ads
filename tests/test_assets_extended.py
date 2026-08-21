"""Tests for the extended asset creators (lead form, price, location, app)."""

from __future__ import annotations

import pytest
from conftest import build_ctx, register_module

from google_ads_mcp import tools


def _run(ctx, tool_fns, tool_name, **kwargs):
    return tool_fns[tool_name](customer_id="123", campaign_id="456", **kwargs)


def test_create_lead_form_asset_proposes_atomic_attach():
    calls = []

    def fake_mutate(service_name, customer_id, operations, **kwargs):
        calls.append((service_name, len(list(operations))))
        return {"atomic": True, "operation_count": 2}

    ctx = build_ctx(fake_mutate)
    tool_fns = register_module(tools.assets_extended, ctx)
    result = _run(
        ctx,
        tool_fns,
        "create_lead_form_asset",
        business_name="Instituto Cambridge",
        headline="Aprendé inglés",
        description="Completá el formulario",
        call_to_action_type="GET_QUOTE",
        privacy_policy_url="https://example.com/privacy",
        fields=[{"input_type": "EMAIL"}, {"input_type": "PHONE_NUMBER"}],
    )

    assert calls == [("GoogleAdsService", 2)]
    assert result["status"] == "executed"


def test_create_lead_form_asset_requires_fields():
    ctx = build_ctx(lambda *a, **k: None)
    tool_fns = register_module(tools.assets_extended, ctx)

    with pytest.raises(ValueError, match="at least one field"):
        _run(
            ctx,
            tool_fns,
            "create_lead_form_asset",
            business_name="X",
            headline="H",
            description="D",
            call_to_action_type="SIGN_UP",
            privacy_policy_url="https://example.com/privacy",
            fields=[],
        )


def test_create_lead_form_asset_proposes_atomically_with_fields():
    calls = []

    def fake_mutate(service_name, customer_id, operations, **kwargs):
        calls.append((service_name, len(list(operations))))
        return {"atomic": True, "operation_count": 2}

    ctx = build_ctx(fake_mutate)
    tool_fns = register_module(tools.assets_extended, ctx)
    result = _run(
        ctx,
        tool_fns,
        "create_lead_form_asset",
        business_name="Instituto",
        headline="Headline",
        description="Desc",
        call_to_action_type="CONTACT_US",
        privacy_policy_url="https://example.com/privacy",
        fields=[
            {"input_type": "EMAIL"},
            {"input_type": "PRODUCT", "single_choice_answers": ["A", "B"]},
        ],
        webhook_url="https://example.com/hook",
    )

    assert result["status"] == "executed"
    assert calls == [("GoogleAdsService", 2)]


def test_create_price_asset_requires_offerings():
    ctx = build_ctx(lambda *a, **k: None)
    tool_fns = register_module(tools.assets_extended, ctx)

    with pytest.raises(ValueError, match="at least one price offering"):
        _run(
            ctx,
            tool_fns,
            "create_price_asset",
            price_type="SERVICES",
            language_code="es",
            offerings=[],
        )


def test_create_price_asset_proposes_atomically():
    calls = []

    def fake_mutate(service_name, customer_id, operations, **kwargs):
        calls.append((service_name, len(list(operations))))
        return {"atomic": True, "operation_count": 2}

    ctx = build_ctx(fake_mutate)
    tool_fns = register_module(tools.assets_extended, ctx)
    result = _run(
        ctx,
        tool_fns,
        "create_price_asset",
        price_type="SERVICES",
        language_code="es",
        offerings=[
            {
                "header": "Curso básico",
                "description": "4 semanas",
                "price": "50",
                "unit": "PER_MONTH",
                "final_url": "https://example.com/basico",
            }
        ],
    )

    assert result["status"] == "executed"
    assert calls == [("GoogleAdsService", 2)]


def test_create_location_asset_validates_place_id():
    ctx = build_ctx(lambda *a, **k: None)
    tool_fns = register_module(tools.assets_extended, ctx)

    with pytest.raises(ValueError, match="place_id is required"):
        tool_fns["create_location_asset"](customer_id="123", place_id="   ")


def test_create_location_asset_proposes_asset_service():
    calls = []

    def fake_mutate(service_name, customer_id, operations, **kwargs):
        calls.append((service_name, len(list(operations))))
        return {"created": True}

    ctx = build_ctx(fake_mutate)
    tool_fns = register_module(tools.assets_extended, ctx)
    result = tool_fns["create_location_asset"](
        customer_id="123", place_id="ChIJN1t_tDeuEmsRUsoyG83frY4"
    )

    assert result["status"] == "executed"
    assert calls == [("AssetService", 1)]


def test_create_mobile_app_asset_validates_store():
    ctx = build_ctx(lambda *a, **k: None)
    tool_fns = register_module(tools.assets_extended, ctx)

    with pytest.raises(ValueError, match="app_store must be"):
        _run(
            ctx,
            tool_fns,
            "create_mobile_app_asset",
            app_id="com.example",
            app_store="AMAZON",
            link_text="Descargá",
        )


def test_create_mobile_app_asset_proposes_atomically():
    calls = []

    def fake_mutate(service_name, customer_id, operations, **kwargs):
        calls.append((service_name, len(list(operations))))
        return {"atomic": True, "operation_count": 2}

    ctx = build_ctx(fake_mutate)
    tool_fns = register_module(tools.assets_extended, ctx)
    result = _run(
        ctx,
        tool_fns,
        "create_mobile_app_asset",
        app_id="com.example.app",
        app_store="GOOGLE_APP_STORE",
        link_text="Descargá",
    )

    assert result["status"] == "executed"
    assert calls == [("GoogleAdsService", 2)]


def test_create_app_deep_link_asset_requires_uri():
    ctx = build_ctx(lambda *a, **k: None)
    tool_fns = register_module(tools.assets_extended, ctx)

    with pytest.raises(ValueError, match="app_deep_link_uri is required"):
        tool_fns["create_app_deep_link_asset"](
            customer_id="123", app_deep_link_uri=""
        )


def test_create_app_deep_link_asset_proposes_asset_service():
    calls = []

    def fake_mutate(service_name, customer_id, operations, **kwargs):
        calls.append((service_name, len(list(operations))))
        return {"created": True}

    ctx = build_ctx(fake_mutate)
    tool_fns = register_module(tools.assets_extended, ctx)
    result = tool_fns["create_app_deep_link_asset"](
        customer_id="123", app_deep_link_uri="app://open"
    )

    assert result["status"] == "executed"
    assert calls == [("AssetService", 1)]
