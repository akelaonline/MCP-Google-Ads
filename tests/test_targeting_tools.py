"""Tests for tools/targeting.py — geo/language targeting, ad schedule, and
device bid modifiers.
"""

from __future__ import annotations

import pytest

from google_ads_mcp import tools

from conftest import FakeMutateResult, build_ctx, register_module


def test_add_location_targeting_resolves_common_names():
    calls = []

    def fake_mutate(service_name, customer_id, operations, **kwargs):
        calls.append((service_name, len(list(operations))))
        return FakeMutateResult("a", "b")

    ctx = build_ctx(fake_mutate)
    tool_fns = register_module(tools.targeting, ctx)

    result = tool_fns["add_location_targeting"](
        customer_id="123", campaign_id="456", locations=["Argentina", "buenos aires"]
    )

    assert calls == [("CampaignCriterionService", 2)]
    assert result["status"] == "executed"


def test_add_location_targeting_accepts_raw_numeric_id():
    calls = []

    def fake_mutate(service_name, customer_id, operations, **kwargs):
        calls.append(service_name)
        return FakeMutateResult("a")

    ctx = build_ctx(fake_mutate)
    tool_fns = register_module(tools.targeting, ctx)

    result = tool_fns["add_location_targeting"](
        customer_id="123", campaign_id="456", locations=["1000073"]
    )

    assert calls == ["CampaignCriterionService"]
    assert result["status"] == "executed"


def test_set_language_targeting():
    calls = []

    def fake_mutate(service_name, customer_id, operations, **kwargs):
        calls.append((service_name, len(list(operations))))
        return FakeMutateResult("a", "b")

    ctx = build_ctx(fake_mutate)
    tool_fns = register_module(tools.targeting, ctx)

    result = tool_fns["set_language_targeting"](
        customer_id="123", campaign_id="456", language_codes=["1003", "1000"]
    )

    assert calls == [("CampaignCriterionService", 2)]
    assert result["status"] == "executed"


def test_add_ad_schedule_validates_hour_range():
    ctx = build_ctx(lambda *a, **k: None)
    tool_fns = register_module(tools.targeting, ctx)

    with pytest.raises(ValueError, match="before end_hour"):
        tool_fns["add_ad_schedule"](
            customer_id="123",
            campaign_id="456",
            day_of_week="MONDAY",
            start_hour=18,
            end_hour=9,
        )


def test_add_ad_schedule_validates_hour_bounds():
    ctx = build_ctx(lambda *a, **k: None)
    tool_fns = register_module(tools.targeting, ctx)

    with pytest.raises(ValueError, match="between 0 and 24"):
        tool_fns["add_ad_schedule"](
            customer_id="123",
            campaign_id="456",
            day_of_week="MONDAY",
            start_hour=9,
            end_hour=25,
        )


def test_add_ad_schedule_creates_criterion():
    calls = []

    def fake_mutate(service_name, customer_id, operations, **kwargs):
        calls.append(service_name)
        return FakeMutateResult("a")

    ctx = build_ctx(fake_mutate)
    tool_fns = register_module(tools.targeting, ctx)

    result = tool_fns["add_ad_schedule"](
        customer_id="123",
        campaign_id="456",
        day_of_week="MONDAY",
        start_hour=9,
        end_hour=18,
        bid_modifier=1.1,
    )

    assert calls == ["CampaignCriterionService"]
    assert result["status"] == "executed"


def test_set_device_bid_modifier():
    calls = []

    def fake_mutate(service_name, customer_id, operations, **kwargs):
        calls.append(service_name)
        return FakeMutateResult("a")

    ctx = build_ctx(fake_mutate)
    tool_fns = register_module(tools.targeting, ctx)

    result = tool_fns["set_device_bid_modifier"](
        customer_id="123", campaign_id="456", device="MOBILE", bid_modifier=1.3
    )

    assert calls == ["CampaignCriterionService"]
    assert result["status"] == "executed"
