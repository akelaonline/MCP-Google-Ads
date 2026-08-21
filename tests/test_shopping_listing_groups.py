"""Tests for Standard Shopping listing-group tools."""

from __future__ import annotations

import pytest
from conftest import FakeMutateResult, build_ctx, register_module

from google_ads_mcp import tools


def test_add_listing_group_validates_type():
    ctx = build_ctx(lambda *a, **k: None)
    tool_fns = register_module(tools.shopping_listing_groups, ctx)

    with pytest.raises(ValueError, match="SUBDIVISION or UNIT"):
        tool_fns["add_shopping_listing_group"](
            customer_id="123",
            ad_group_id="456",
            listing_group_type="BRANCH",
        )


def test_add_unit_requires_dimension():
    ctx = build_ctx(lambda *a, **k: None)
    tool_fns = register_module(tools.shopping_listing_groups, ctx)

    with pytest.raises(ValueError, match="require a dimension"):
        tool_fns["add_shopping_listing_group"](
            customer_id="123",
            ad_group_id="456",
            listing_group_type="UNIT",
        )


def test_add_listing_group_validates_dimension_type():
    ctx = build_ctx(lambda *a, **k: None)
    tool_fns = register_module(tools.shopping_listing_groups, ctx)

    with pytest.raises(ValueError, match="dimension.type must be one of"):
        tool_fns["add_shopping_listing_group"](
            customer_id="123",
            ad_group_id="456",
            listing_group_type="UNIT",
            dimension={"type": "PRODUCT_COLOR", "value": "red"},
        )


def test_add_listing_group_validates_enum_value():
    ctx = build_ctx(lambda *a, **k: None)
    tool_fns = register_module(tools.shopping_listing_groups, ctx)

    with pytest.raises(ValueError, match="dimension.value must be one of"):
        tool_fns["add_shopping_listing_group"](
            customer_id="123",
            ad_group_id="456",
            listing_group_type="UNIT",
            dimension={"type": "PRODUCT_CONDITION", "value": "LIKE_NEW"},
        )


def test_add_root_subdivision_proposes_criterion_service():
    calls = []

    def fake_mutate(service_name, customer_id, operations, **kwargs):
        calls.append(service_name)
        return FakeMutateResult("a")

    ctx = build_ctx(fake_mutate)
    tool_fns = register_module(tools.shopping_listing_groups, ctx)
    result = tool_fns["add_shopping_listing_group"](
        customer_id="123",
        ad_group_id="456",
        listing_group_type="SUBDIVISION",
    )

    assert calls == ["AdGroupCriterionService"]
    assert result["status"] == "executed"
    assert "all products" in result["description"]


def test_add_unit_with_brand_dimension_builds_case_value():
    captured = []

    def fake_mutate(service_name, customer_id, operations, **kwargs):
        captured.extend(list(operations))
        return FakeMutateResult("a")

    ctx = build_ctx(fake_mutate)
    tool_fns = register_module(tools.shopping_listing_groups, ctx)
    result = tool_fns["add_shopping_listing_group"](
        customer_id="123",
        ad_group_id="456",
        listing_group_type="UNIT",
        dimension={"type": "PRODUCT_BRAND", "value": "Nike"},
        parent_criterion_id="789",
        bid_modifier=1.5,
    )

    assert result["status"] == "executed"
    criterion = captured[0].create
    assert criterion.listing_group.type_ == 3  # UNIT
    assert criterion.listing_group.parent_ad_group_criterion == (
        "customers/123/AdGroupCriterionServicePath/456/789"
    )
    assert criterion.listing_group.case_value.product_brand.value == "Nike"
    assert criterion.bid_modifier == 1.5


def test_update_listing_group_requires_a_change():
    ctx = build_ctx(lambda *a, **k: None)
    tool_fns = register_module(tools.shopping_listing_groups, ctx)

    with pytest.raises(ValueError, match="at least one"):
        tool_fns["update_shopping_listing_group"](
            customer_id="123", ad_group_id="456", criterion_id="789"
        )


def test_update_listing_group_builds_update_operation():
    captured = []

    def fake_mutate(service_name, customer_id, operations, **kwargs):
        captured.extend(list(operations))
        return FakeMutateResult("a")

    ctx = build_ctx(fake_mutate)
    tool_fns = register_module(tools.shopping_listing_groups, ctx)
    result = tool_fns["update_shopping_listing_group"](
        customer_id="123",
        ad_group_id="456",
        criterion_id="789",
        bid_modifier=0.8,
    )

    assert result["status"] == "executed"
    assert "update" in captured[0]._children
    assert captured[0].update.bid_modifier == 0.8


def test_remove_listing_group_builds_remove_operation():
    captured = []

    def fake_mutate(service_name, customer_id, operations, **kwargs):
        captured.extend(list(operations))
        return FakeMutateResult("a")

    ctx = build_ctx(fake_mutate)
    tool_fns = register_module(tools.shopping_listing_groups, ctx)
    result = tool_fns["remove_shopping_listing_group"](
        customer_id="123", ad_group_id="456", criterion_id="789"
    )

    assert result["status"] == "executed"
    assert captured[0]._children["remove"] == (
        "customers/123/AdGroupCriterionServicePath/456/789"
    )


def test_list_listing_groups_reads():
    def fake_search(customer_id, query):
        return [
            {
                "ad_group_criterion": {
                    "criterion_id": 5,
                    "listing_group": {"type": "SUBDIVISION"},
                }
            }
        ]

    ctx = build_ctx(lambda *a, **k: None, search_side_effect=fake_search)
    tool_fns = register_module(tools.shopping_listing_groups, ctx)
    result = tool_fns["list_shopping_listing_groups"](
        customer_id="123", ad_group_id="456"
    )

    assert result["count"] == 1
    assert result["listing_groups"][0]["ad_group_criterion"]["criterion_id"] == 5
