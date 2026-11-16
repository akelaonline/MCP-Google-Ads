"""Features Google retired in September 2026 must not reach the API.

* New Smart Campaigns cannot be created (2026-09-23).
* Manual LANGUAGE criteria cannot be added/updated on Search campaigns
  (OPERATION_NOT_PERMITTED_FOR_CONTEXT). Reading and removing still work.
"""

from __future__ import annotations

import pytest
from conftest import FakeMutateResult, build_ctx, register_module

from google_ads_mcp import tools
from google_ads_mcp.errors import GoogleAdsMcpError
from google_ads_mcp.tools.targeting import _channel_name

SEARCH_INT = 2  # AdvertisingChannelType.SEARCH
DISPLAY_INT = 3


# --------------------------------------------------------------- Smart campaigns


def test_create_smart_campaign_is_unsupported_and_never_mutates():
    mutations = []

    def fake_mutate(service_name, customer_id, operations, **kwargs):
        mutations.append(service_name)
        return FakeMutateResult("x")

    ctx = build_ctx(fake_mutate)
    result = register_module(tools.smart_campaigns, ctx)["create_smart_campaign"](
        customer_id="123",
        name="Nueva",
        daily_budget=10.0,
        final_url="https://example.com",
        business_name="Negocio",
        headlines=["a", "b", "c"],
        descriptions=["d", "e"],
        keyword_themes=["piso"],
        geo_target_ids=["1000073"],
    )
    assert result["status"] == "unsupported"
    assert result["mutations_executed"] == 0
    assert "Performance Max" in result["guidance"]
    assert mutations == []
    assert ctx.safety.list_pending() == []


def test_generic_create_campaign_rejects_smart_channel():
    ctx = build_ctx(lambda *a, **k: FakeMutateResult("x"))
    fns = register_module(tools.campaigns, ctx)
    with pytest.raises(ValueError, match="Smart Campaigns"):
        fns["create_campaign"](
            customer_id="123",
            name="Smart",
            campaign_budget_resource_name="customers/123/campaignBudgets/1",
            channel_type="smart",
        )


# ------------------------------------------------------------- Search languages


def _language_ctx(channel, existing):
    calls = []

    def fake_search(customer_id, query):
        if "advertising_channel_type" in query and "campaign_criterion" not in query:
            return (
                [{"campaign": {"advertising_channel_type": channel}}] if channel else []
            )
        return existing

    def fake_mutate(service_name, customer_id, operations, **kwargs):
        calls.append([op for op in operations])
        return FakeMutateResult("done")

    ctx = build_ctx(fake_mutate, search_side_effect=fake_search)
    return register_module(tools.targeting, ctx)["set_language_targeting"], calls


_EXISTING = [
    {
        "campaign_criterion": {
            "criterion_id": 11,
            "language": {"language_constant": "languageConstants/1003"},
        }
    }
]


@pytest.mark.parametrize("channel", ["SEARCH", SEARCH_INT])
def test_search_campaign_refuses_to_add_languages(channel):
    fn, calls = _language_ctx(channel, _EXISTING)
    with pytest.raises(GoogleAdsMcpError, match="no longer supports manual language"):
        fn(customer_id="123", campaign_id="456", language_codes=["1003"])
    assert calls == []


@pytest.mark.parametrize("channel", ["SEARCH", SEARCH_INT])
def test_search_campaign_cleanup_removes_leftover_languages_only(channel):
    fn, calls = _language_ctx(channel, _EXISTING)
    result = fn(customer_id="123", campaign_id="456", language_codes=[])
    assert result["status"] == "executed"
    assert len(calls) == 1 and len(calls[0]) == 1
    remove = str(calls[0][0].remove)
    assert "456" in remove and "11" in remove  # the leftover criterion, nothing created


def test_search_campaign_with_nothing_to_remove_is_a_noop():
    fn, calls = _language_ctx("SEARCH", [])
    assert (
        fn(customer_id="123", campaign_id="456", language_codes=[])["status"]
        == "no_change"
    )
    assert calls == []


@pytest.mark.parametrize("channel", ["DISPLAY", DISPLAY_INT, None])
def test_other_channels_keep_replace_behaviour(channel):
    fn, calls = _language_ctx(channel, _EXISTING)
    result = fn(customer_id="123", campaign_id="456", language_codes=["1003", "1000"])
    assert result["status"] == "executed"
    assert len(calls[0]) == 3  # remove existing + two creates


def test_non_search_still_requires_at_least_one_language():
    fn, calls = _language_ctx("DISPLAY", _EXISTING)
    with pytest.raises(ValueError, match="at least one language"):
        fn(customer_id="123", campaign_id="456", language_codes=[])
    assert calls == []


def test_channel_name_handles_names_ints_and_unknowns():
    assert _channel_name("SEARCH") == "SEARCH"
    assert _channel_name("AdvertisingChannelType.SEARCH") == "SEARCH"
    assert _channel_name(SEARCH_INT) == "SEARCH"
    assert _channel_name(DISPLAY_INT) == "DISPLAY"
    assert _channel_name(None) is None
    assert _channel_name(9999) is None
