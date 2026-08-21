"""Tests for the impression-share diagnostics report."""

from __future__ import annotations

from conftest import build_ctx, register_module

from google_ads_mcp import tools


def test_get_impression_share_report_reads_and_converts_cost():
    def fake_search(customer_id, query):
        assert "search_impression_share" in query
        assert "search_budget_lost_impression_share" in query
        assert "search_rank_lost_impression_share" in query
        return [
            {
                "campaign": {"id": 1, "name": "Search 1", "status": "ENABLED"},
                "metrics": {
                    "impressions": 1000,
                    "cost_micros": 25000000,
                    "search_impression_share": 0.75,
                    "search_budget_lost_impression_share": 0.05,
                    "search_rank_lost_impression_share": 0.2,
                },
            }
        ]

    ctx = build_ctx(lambda *a, **k: None, search_side_effect=fake_search)
    tool_fns = register_module(tools.reporting, ctx)
    result = tool_fns["get_impression_share_report"](customer_id="123")

    assert result["count"] == 1
    metrics = result["campaigns"][0]["metrics"]
    assert metrics["search_impression_share"] == 0.75
    assert metrics["cost"] == 25.0  # cost_micros converted
