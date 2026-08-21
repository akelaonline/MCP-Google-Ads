"""Tests for Dynamic Search Ads tools."""

from __future__ import annotations

import pytest
from conftest import FakeMutateResult, build_ctx, register_module

from google_ads_mcp import tools


def test_create_dsa_campaign_validates_domain():
    ctx = build_ctx(lambda *a, **k: None)
    tool_fns = register_module(tools.dynamic_search_ads, ctx)

    with pytest.raises(ValueError, match="valid root domain"):
        tool_fns["create_dsa_campaign"](
            customer_id="123",
            name="DSA",
            campaign_budget_resource_name="customers/123/campaignBudgets/1",
            domain_name="not a domain",
            language_code="es",
        )


def test_create_dsa_campaign_validates_language_code():
    ctx = build_ctx(lambda *a, **k: None)
    tool_fns = register_module(tools.dynamic_search_ads, ctx)

    with pytest.raises(ValueError, match="two-letter language code"):
        tool_fns["create_dsa_campaign"](
            customer_id="123",
            name="DSA",
            campaign_budget_resource_name="customers/123/campaignBudgets/1",
            domain_name="example.com",
            language_code="spanish",
        )


def test_create_dsa_campaign_proposes_campaign_service():
    calls = []

    def fake_mutate(service_name, customer_id, operations, **kwargs):
        calls.append(service_name)
        return FakeMutateResult("customers/123/campaigns/1")

    ctx = build_ctx(fake_mutate)
    tool_fns = register_module(tools.dynamic_search_ads, ctx)
    result = tool_fns["create_dsa_campaign"](
        customer_id="123",
        name="DSA",
        campaign_budget_resource_name="customers/123/campaignBudgets/1",
        domain_name="example.com",
        language_code="es",
    )

    assert calls == ["CampaignService"]
    assert result["status"] == "executed"
    assert "created PAUSED" in result["description"]


def test_create_dsa_ad_group_proposes_ad_group_service():
    calls = []

    def fake_mutate(service_name, customer_id, operations, **kwargs):
        calls.append(service_name)
        return FakeMutateResult("customers/123/adGroups/1")

    ctx = build_ctx(fake_mutate)
    tool_fns = register_module(tools.dynamic_search_ads, ctx)
    result = tool_fns["create_dsa_ad_group"](
        customer_id="123",
        campaign_id="456",
        name="DSA Ad Group",
    )

    assert calls == ["AdGroupService"]
    assert result["status"] == "executed"
    assert "SEARCH_DYNAMIC_ADS" in result["description"]


def test_add_webpage_target_requires_conditions():
    ctx = build_ctx(lambda *a, **k: None)
    tool_fns = register_module(tools.dynamic_search_ads, ctx)

    with pytest.raises(ValueError, match="at least one webpage condition"):
        tool_fns["add_webpage_target"](
            customer_id="123", campaign_id="456", conditions=[]
        )


def test_add_webpage_target_validates_operand():
    ctx = build_ctx(lambda *a, **k: None)
    tool_fns = register_module(tools.dynamic_search_ads, ctx)

    with pytest.raises(ValueError, match="operand must be one of"):
        tool_fns["add_webpage_target"](
            customer_id="123",
            campaign_id="456",
            conditions=[{"operand": "PAGE_URL", "operator": "EQUALS", "argument": "/x"}],
        )


def test_add_webpage_target_validates_operator():
    ctx = build_ctx(lambda *a, **k: None)
    tool_fns = register_module(tools.dynamic_search_ads, ctx)

    with pytest.raises(ValueError, match="operator must be one of"):
        tool_fns["add_webpage_target"](
            customer_id="123",
            campaign_id="456",
            conditions=[{"operand": "URL", "operator": "IS", "argument": "/x"}],
        )


def test_add_webpage_target_proposes_criterion_service():
    calls = []

    def fake_mutate(service_name, customer_id, operations, **kwargs):
        calls.append(service_name)
        return FakeMutateResult("a")

    ctx = build_ctx(fake_mutate)
    tool_fns = register_module(tools.dynamic_search_ads, ctx)
    result = tool_fns["add_webpage_target"](
        customer_id="123",
        campaign_id="456",
        conditions=[{"operand": "URL", "operator": "CONTAINS", "argument": "/hotel"}],
        criterion_name="hotel pages",
    )

    assert calls == ["CampaignCriterionService"]
    assert result["status"] == "executed"
    assert "hotel pages" in result["description"]


def test_list_webpage_targets_reads():
    def fake_search(customer_id, query):
        return [{"campaign_criterion": {"criterion_id": 77}}]

    ctx = build_ctx(lambda *a, **k: None, search_side_effect=fake_search)
    tool_fns = register_module(tools.dynamic_search_ads, ctx)
    result = tool_fns["list_webpage_targets"](customer_id="123", campaign_id="456")

    assert result["count"] == 1
    assert result["webpage_targets"][0]["campaign_criterion"]["criterion_id"] == 77
