"""Tests for tools/bulk.py — batch status changes and multi-scope negatives."""

from __future__ import annotations

import pytest

from google_ads_mcp import tools

from conftest import FakeMutateResult, build_ctx, register_module


def test_bulk_update_keyword_status_single_call():
    calls = []

    def fake_mutate(service_name, customer_id, operations, **kwargs):
        calls.append((service_name, len(list(operations)), kwargs.get("partial_failure")))
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

    # Exactly one mutate call carrying all 3 operations, not 3 separate calls.
    assert calls == [("AdGroupCriterionService", 3, True)]
    assert result["status"] == "executed"


def test_bulk_update_keyword_status_requires_updates():
    ctx = build_ctx(lambda *a, **k: None)
    tool_fns = register_module(tools.bulk, ctx)

    with pytest.raises(ValueError, match="at least one"):
        tool_fns["bulk_update_keyword_status"](customer_id="123", updates=[], status="PAUSED")


def test_bulk_add_negative_keywords_multi_scope_splits_by_service():
    calls = []

    def fake_mutate(service_name, customer_id, operations, **kwargs):
        calls.append((service_name, len(list(operations))))
        return FakeMutateResult("x", "y")

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

    called_services = {name for name, _count in calls}
    assert called_services == {"CampaignCriterionService", "AdGroupCriterionService"}
    campaign_call = next(c for c in calls if c[0] == "CampaignCriterionService")
    assert campaign_call[1] == 2  # one op per campaign
    assert result["status"] == "executed"


def test_bulk_add_negative_keywords_multi_scope_requires_at_least_one_scope():
    ctx = build_ctx(lambda *a, **k: None)
    tool_fns = register_module(tools.bulk, ctx)

    with pytest.raises(ValueError, match="at least one"):
        tool_fns["bulk_add_negative_keywords_multi_scope"](customer_id="123")


def test_bulk_update_ad_status_single_call():
    calls = []

    def fake_mutate(service_name, customer_id, operations, **kwargs):
        calls.append((service_name, len(list(operations))))
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

    assert calls == [("AdGroupAdService", 2)]
    assert result["status"] == "executed"
