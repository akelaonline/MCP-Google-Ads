"""Tests for geo/language/schedule/device targeting."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from conftest import FakeMutateResult, build_ctx, register_module

from google_ads_mcp import tools


def test_add_location_targeting_resolves_names_live():
    calls = []

    class GeoService:
        def suggest_geo_target_constants(self, *, request):
            assert list(request.location_names.names) == ["Argentina"]
            candidate = SimpleNamespace(
                resource_name="geoTargetConstants/2032",
                name="Argentina",
                target_type="Country",
                status=SimpleNamespace(name="ENABLED"),
            )
            return SimpleNamespace(
                geo_target_constant_suggestions=[
                    SimpleNamespace(search_term="Argentina", geo_target_constant=candidate)
                ]
            )

        def geo_target_constant_path(self, geo_id):
            return f"geoTargetConstants/{geo_id}"

    def fake_mutate(service_name, customer_id, operations, **kwargs):
        calls.append((service_name, len(list(operations))))
        return FakeMutateResult("a")

    ctx = build_ctx(
        fake_mutate,
        extra_services={"GeoTargetConstantService": GeoService()},
    )
    tool_fns = register_module(tools.targeting, ctx)
    result = tool_fns["add_location_targeting"](
        customer_id="123",
        campaign_id="456",
        locations=["Argentina"],
    )

    assert calls == [("CampaignCriterionService", 1)]
    assert result["status"] == "executed"
    assert result["result"]["resource_names"] == ["a"]


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


def test_set_language_targeting_replaces_existing():
    calls = []

    def fake_search(customer_id, query):
        return [
            {
                "campaign_criterion": {
                    "criterion_id": 11,
                    "language": {"language_constant": "languageConstants/1001"},
                }
            }
        ]

    def fake_mutate(service_name, customer_id, operations, **kwargs):
        calls.append((service_name, len(list(operations))))
        return FakeMutateResult("removed", "spanish", "english")

    ctx = build_ctx(fake_mutate, search_side_effect=fake_search)
    tool_fns = register_module(tools.targeting, ctx)
    result = tool_fns["set_language_targeting"](
        customer_id="123", campaign_id="456", language_codes=["1003", "1000"]
    )

    assert calls == [("CampaignCriterionService", 3)]
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

    with pytest.raises(ValueError, match="end_hour must be between 1 and 24"):
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


def test_set_device_bid_modifier_creates_if_missing():
    calls = []

    def fake_mutate(service_name, customer_id, operations, **kwargs):
        calls.append(service_name)
        return FakeMutateResult("a")

    ctx = build_ctx(fake_mutate, search_side_effect=lambda *a: [])
    tool_fns = register_module(tools.targeting, ctx)
    result = tool_fns["set_device_bid_modifier"](
        customer_id="123", campaign_id="456", device="MOBILE", bid_modifier=1.3
    )

    assert calls == ["CampaignCriterionService"]
    assert result["status"] == "executed"
    assert result["description"].startswith("Create")


def test_set_device_bid_modifier_updates_existing():
    captured = []

    def fake_search(customer_id, query):
        return [
            {
                "campaign_criterion": {
                    "criterion_id": 99,
                    "device": {"type": "MOBILE"},
                    "bid_modifier": 1.0,
                }
            }
        ]

    def fake_mutate(service_name, customer_id, operations, **kwargs):
        captured.extend(list(operations))
        return FakeMutateResult("a")

    ctx = build_ctx(fake_mutate, search_side_effect=fake_search)
    tool_fns = register_module(tools.targeting, ctx)
    result = tool_fns["set_device_bid_modifier"](
        customer_id="123", campaign_id="456", device="MOBILE", bid_modifier=0
    )

    assert result["status"] == "executed"
    assert result["description"].startswith("Update")
    assert "update" in captured[0]._children
