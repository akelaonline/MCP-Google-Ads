"""Tests for campaign-aware ad-group creation."""

from __future__ import annotations

import pytest
from conftest import FakeMutateResult, build_ctx, register_module

from google_ads_mcp import tools


def _campaign_search(channel: str):
    def search(customer_id, query):
        return [{"campaign": {"advertising_channel_type": channel}}]

    return search


def test_search_campaign_auto_uses_search_standard():
    calls = []

    def fake_mutate(service_name, customer_id, operations, **kwargs):
        operation = list(operations)[0]
        calls.append((service_name, operation.create.type_))
        return FakeMutateResult("customers/123/adGroups/1")

    ctx = build_ctx(fake_mutate, search_side_effect=_campaign_search("SEARCH"))
    tool_fns = register_module(tools.ad_groups, ctx)
    result = tool_fns["create_ad_group"](
        customer_id="123",
        campaign_id="456",
        name="Search Group",
    )

    assert result["status"] == "executed"
    assert calls[0][0] == "AdGroupService"
    assert calls[0][1].name == "SEARCH_STANDARD"


def test_demand_gen_auto_leaves_type_unset():
    captured = []

    def fake_mutate(service_name, customer_id, operations, **kwargs):
        operation = list(operations)[0]
        captured.append(operation)
        return FakeMutateResult("customers/123/adGroups/2")

    ctx = build_ctx(fake_mutate, search_side_effect=_campaign_search("DEMAND_GEN"))
    tool_fns = register_module(tools.ad_groups, ctx)
    result = tool_fns["create_ad_group"](
        customer_id="123",
        campaign_id="789",
        name="Demand Gen Group",
    )

    assert result["status"] == "executed"
    assert result["result"]["resource_names"] == ["customers/123/adGroups/2"]
    # AutoVivify only creates a child when the code writes/reads it. Demand Gen
    # must not write the type field at all.
    assert "type_" not in captured[0].create._children


def test_demand_gen_rejects_ad_group_cpc():
    ctx = build_ctx(lambda *a, **k: None, search_side_effect=_campaign_search("DEMAND_GEN"))
    tool_fns = register_module(tools.ad_groups, ctx)

    with pytest.raises(ValueError, match="Demand Gen"):
        tool_fns["create_ad_group"](
            customer_id="123",
            campaign_id="789",
            name="Demand Gen Group",
            cpc_bid=2.0,
        )


def test_ambiguous_video_channel_requires_explicit_type():
    ctx = build_ctx(lambda *a, **k: None, search_side_effect=_campaign_search("VIDEO"))
    tool_fns = register_module(tools.ad_groups, ctx)

    with pytest.raises(ValueError, match="explicit ad_group_type"):
        tool_fns["create_ad_group"](
            customer_id="123",
            campaign_id="999",
            name="Video Group",
        )


def test_explicit_video_type_skips_campaign_lookup():
    calls = []

    def fake_mutate(service_name, customer_id, operations, **kwargs):
        operation = list(operations)[0]
        calls.append(operation.create.type_)
        return FakeMutateResult("customers/123/adGroups/3")

    def fail_search(*args, **kwargs):
        raise AssertionError("explicit type should not need campaign lookup")

    ctx = build_ctx(fake_mutate, search_side_effect=fail_search)
    tool_fns = register_module(tools.ad_groups, ctx)
    result = tool_fns["create_ad_group"](
        customer_id="123",
        campaign_id="999",
        name="Video Group",
        ad_group_type="VIDEO_RESPONSIVE",
    )

    assert result["status"] == "executed"
    assert calls[0].name == "VIDEO_RESPONSIVE"
