"""Tests for tools/bulk.py — atomic batch status and negative operations."""

from __future__ import annotations

import pytest
from conftest import FakeMutateResult, build_ctx, register_module

from google_ads_mcp import tools


def test_bulk_update_keyword_status_single_atomic_call():
    calls = []

    def fake_mutate(service_name, customer_id, operations, **kwargs):
        calls.append(
            (service_name, len(list(operations)), kwargs.get("partial_failure"))
        )
        return FakeMutateResult("a", "b", "c")

    ctx = build_ctx(fake_mutate)
    tool_fns = register_module(tools.bulk, ctx)
    result = tool_fns["bulk_update_keyword_status"](
        customer_id="123",
        updates=[
            {"ad_group_id": "1", "criterion_id": "10"},
            {"ad_group_id": "1", "criterion_id": "11"},
            {"ad_group_id": "2", "criterion_id": "20"},
        ],
        status="PAUSED",
    )

    assert calls == [("AdGroupCriterionService", 3, False)]
    assert result["status"] == "executed"


def test_bulk_update_keyword_status_requires_updates():
    ctx = build_ctx(lambda *a, **k: None)
    tool_fns = register_module(tools.bulk, ctx)

    with pytest.raises(ValueError, match="at least one"):
        tool_fns["bulk_update_keyword_status"](
            customer_id="123", updates=[], status="PAUSED"
        )


def test_bulk_add_negative_keywords_multi_scope_is_one_atomic_call():
    calls = []

    def fake_mutate(service_name, customer_id, operations, **kwargs):
        calls.append((service_name, len(list(operations))))
        return {"atomic": True}

    ctx = build_ctx(fake_mutate)
    tool_fns = register_module(tools.bulk, ctx)
    result = tool_fns["bulk_add_negative_keywords_multi_scope"](
        customer_id="123",
        campaign_negatives={
            "111": [{"text": "gratis", "match_type": "PHRASE"}],
            "222": [{"text": "gratis", "match_type": "PHRASE"}],
        },
        ad_group_negatives={
            "999": [{"text": "trabajo", "match_type": "PHRASE"}],
        },
    )

    assert calls == [("GoogleAdsService", 3)]
    assert result["status"] == "executed"
    assert result["result"]["atomic"] is True


def test_bulk_add_negative_keywords_multi_scope_requires_at_least_one_scope():
    ctx = build_ctx(lambda *a, **k: None)
    tool_fns = register_module(tools.bulk, ctx)

    with pytest.raises(ValueError, match="at least one"):
        tool_fns["bulk_add_negative_keywords_multi_scope"](customer_id="123")


def test_bulk_update_ad_status_remove_uses_single_atomic_service_call():
    calls = []

    def fake_mutate(service_name, customer_id, operations, **kwargs):
        operations = list(operations)
        calls.append((service_name, len(operations), kwargs.get("partial_failure")))
        assert all("remove" in operation._children for operation in operations)
        return FakeMutateResult("a", "b")

    ctx = build_ctx(fake_mutate)
    tool_fns = register_module(tools.bulk, ctx)
    result = tool_fns["bulk_update_ad_status"](
        customer_id="123",
        updates=[
            {"ad_group_id": "1", "ad_id": "100"},
            {"ad_group_id": "1", "ad_id": "101"},
        ],
        status="REMOVED",
    )

    assert calls == [("AdGroupAdService", 2, False)]
    assert result["status"] == "executed"
