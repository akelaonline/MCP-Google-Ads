"""Tests for tracking URL / URL-option tools."""

from __future__ import annotations

import pytest
from conftest import FakeMutateResult, build_ctx, register_module

from google_ads_mcp import tools


def test_set_campaign_tracking_url_requires_at_least_one_field():
    ctx = build_ctx(lambda *a, **k: None)
    tool_fns = register_module(tools.url_options, ctx)

    with pytest.raises(ValueError, match="at least one"):
        tool_fns["set_campaign_tracking_url"](
            customer_id="123", campaign_id="456"
        )


def test_set_campaign_tracking_url_rejects_empty_param_key():
    ctx = build_ctx(lambda *a, **k: None)
    tool_fns = register_module(tools.url_options, ctx)

    with pytest.raises(ValueError, match="non-empty 'key'"):
        tool_fns["set_campaign_tracking_url"](
            customer_id="123",
            campaign_id="456",
            url_custom_parameters=[{"key": " ", "value": "x"}],
        )


def test_set_campaign_tracking_url_rejects_braces_in_key():
    ctx = build_ctx(lambda *a, **k: None)
    tool_fns = register_module(tools.url_options, ctx)

    with pytest.raises(ValueError, match="cannot contain"):
        tool_fns["set_campaign_tracking_url"](
            customer_id="123",
            campaign_id="456",
            url_custom_parameters=[{"key": "{utm}", "value": "x"}],
        )


def test_set_campaign_tracking_url_proposes_campaign_service():
    calls = []

    def fake_mutate(service_name, customer_id, operations, **kwargs):
        calls.append(service_name)
        return FakeMutateResult("a")

    ctx = build_ctx(fake_mutate)
    tool_fns = register_module(tools.url_options, ctx)
    result = tool_fns["set_campaign_tracking_url"](
        customer_id="123",
        campaign_id="456",
        tracking_url_template="{lpurl}?utm_source=mcp",
    )

    assert calls == ["CampaignService"]
    assert result["status"] == "executed"


def test_set_ad_group_tracking_url_requires_at_least_one_field():
    ctx = build_ctx(lambda *a, **k: None)
    tool_fns = register_module(tools.url_options, ctx)

    with pytest.raises(ValueError, match="at least one"):
        tool_fns["set_ad_group_tracking_url"](customer_id="123", ad_group_id="456")


def test_set_ad_group_tracking_url_proposes_ad_group_service():
    calls = []

    def fake_mutate(service_name, customer_id, operations, **kwargs):
        calls.append(service_name)
        return FakeMutateResult("a")

    ctx = build_ctx(fake_mutate)
    tool_fns = register_module(tools.url_options, ctx)
    result = tool_fns["set_ad_group_tracking_url"](
        customer_id="123",
        ad_group_id="456",
        final_url_suffix="?utm_campaign=x",
    )

    assert calls == ["AdGroupService"]
    assert result["status"] == "executed"


def test_set_account_tracking_url_requires_at_least_one_field():
    ctx = build_ctx(lambda *a, **k: None)
    tool_fns = register_module(tools.url_options, ctx)

    with pytest.raises(ValueError, match="at least one"):
        tool_fns["set_account_tracking_url"](customer_id="123")


def test_set_account_tracking_url_proposes_customer_service():
    calls = []

    def fake_mutate(service_name, customer_id, operations, **kwargs):
        calls.append(service_name)
        return FakeMutateResult("a")

    ctx = build_ctx(fake_mutate)
    tool_fns = register_module(tools.url_options, ctx)
    result = tool_fns["set_account_tracking_url"](
        customer_id="123",
        tracking_url_template="{lpurl}?src=account",
    )

    assert calls == ["CustomerService"]
    assert result["status"] == "executed"


def test_get_campaign_tracking_url_reads():
    def fake_search(customer_id, query):
        return [
            {
                "campaign": {
                    "id": 456,
                    "tracking_url_template": "{lpurl}?utm_source=mcp",
                    "url_custom_parameters": [{"key": "a", "value": "b"}],
                }
            }
        ]

    ctx = build_ctx(lambda *a, **k: None, search_side_effect=fake_search)
    tool_fns = register_module(tools.url_options, ctx)
    result = tool_fns["get_campaign_tracking_url"](customer_id="123", campaign_id="456")

    assert result["found"] is True
    assert result["url_options"]["campaign"]["tracking_url_template"] == (
        "{lpurl}?utm_source=mcp"
    )


def test_get_ad_group_tracking_url_reads():
    def fake_search(customer_id, query):
        return [{"ad_group": {"id": 456, "final_url_suffix": "?x=1"}}]

    ctx = build_ctx(lambda *a, **k: None, search_side_effect=fake_search)
    tool_fns = register_module(tools.url_options, ctx)
    result = tool_fns["get_ad_group_tracking_url"](customer_id="123", ad_group_id="456")

    assert result["found"] is True
    assert result["url_options"]["ad_group"]["final_url_suffix"] == "?x=1"
