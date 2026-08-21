"""Tests for call-conversion uploads."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from conftest import build_ctx, register_module

from google_ads_mcp import tools

_UPLOAD_CALLS_ACTION = [
    {
        "conversion_action": {
            "id": 555,
            "type": "UPLOAD_CALLS",
            "status": "ENABLED",
        }
    }
]


def _build_ctx_with_upload_service(captured: dict, search_rows=None):
    class UploadService:
        def upload_call_conversions(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(partial_failure_error=None)

    def fake_mutate(*args, **kwargs):
        raise AssertionError("call conversion uploads must not use ctx.client.mutate")

    ctx = build_ctx(
        fake_mutate,
        extra_services={"ConversionUploadService": UploadService()},
        search_side_effect=lambda *a: search_rows if search_rows is not None else [],
    )
    return ctx


def test_upload_call_conversion_validates_caller_id():
    ctx = build_ctx(lambda *a, **k: None)
    tool_fns = register_module(tools.conversions, ctx)

    with pytest.raises(ValueError, match="E.164"):
        tool_fns["upload_call_conversion"](
            customer_id="123",
            conversion_action_id="555",
            caller_id="not-a-phone",
            call_start_date_time="2026-08-20 15:30:00+00:00",
            conversion_date_time="2026-08-20 15:35:00+00:00",
        )


def test_upload_call_conversion_validates_consent():
    ctx = build_ctx(lambda *a, **k: None)
    tool_fns = register_module(tools.conversions, ctx)

    with pytest.raises(ValueError, match="consent must be GRANTED or DENIED"):
        tool_fns["upload_call_conversion"](
            customer_id="123",
            conversion_action_id="555",
            caller_id="+5491112345678",
            call_start_date_time="2026-08-20 15:30:00+00:00",
            conversion_date_time="2026-08-20 15:35:00+00:00",
            consent="MAYBE",
        )


def test_upload_call_conversion_requires_upload_calls_action():
    ctx = build_ctx(
        lambda *a, **k: None,
        search_side_effect=lambda *a: [
            {"conversion_action": {"id": 555, "type": "WEBPAGE", "status": "ENABLED"}}
        ],
    )
    tool_fns = register_module(tools.conversions, ctx)

    with pytest.raises(ValueError, match="UPLOAD_CALLS"):
        tool_fns["upload_call_conversion"](
            customer_id="123",
            conversion_action_id="555",
            caller_id="+5491112345678",
            call_start_date_time="2026-08-20 15:30:00+00:00",
            conversion_date_time="2026-08-20 15:35:00+00:00",
        )


def test_upload_call_conversion_uploads_with_normalized_fields():
    captured = {}
    ctx = _build_ctx_with_upload_service(captured, search_rows=_UPLOAD_CALLS_ACTION)
    tool_fns = register_module(tools.conversions, ctx)
    result = tool_fns["upload_call_conversion"](
        customer_id="123",
        conversion_action_id="555",
        caller_id="+5491112345678",
        call_start_date_time="2026-08-20 15:30:00+00:00",
        conversion_date_time="2026-08-20 15:35:00+00:00",
        conversion_value=12.5,
        currency_code="usd",
        consent="GRANTED",
    )

    assert result["status"] == "executed"
    assert captured["customer_id"] == "123"
    assert captured["partial_failure"] is True
    (call_conversion,) = captured["conversions"]
    assert call_conversion.conversion_action == (
        "customers/123/ConversionActionServicePath/555"
    )
    assert call_conversion.caller_id == "5491112345678"  # "+" stripped
    assert call_conversion.currency_code == "USD"  # uppercased
    assert call_conversion.consent.ad_user_data == 2  # GRANTED
    assert call_conversion.consent.ad_personalization == 2  # GRANTED


def test_upload_call_conversion_masks_caller_id_in_payload_and_description():
    captured = {}
    ctx = _build_ctx_with_upload_service(captured, search_rows=_UPLOAD_CALLS_ACTION)
    tool_fns = register_module(tools.conversions, ctx)
    result = tool_fns["upload_call_conversion"](
        customer_id="123",
        conversion_action_id="555",
        caller_id="+5491112345678",
        call_start_date_time="2026-08-20 15:30:00+00:00",
        conversion_date_time="2026-08-20 15:35:00+00:00",
    )

    assert result["status"] == "executed"
    assert "*******5678" in result["description"]
    assert "5678" in result["description"]
    assert "5491112345678" not in result["description"]
