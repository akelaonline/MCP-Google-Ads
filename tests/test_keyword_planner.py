"""Tests for tools/keyword_planner.py — KeywordPlanIdeaService wrappers.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from google_ads_mcp import tools

from conftest import build_ctx, register_module


class _FakeKeywordPlanIdeaService:
    """Records requests and returns plausible GenerateKeywordIdeas / HistoricalMetrics responses."""

    def __init__(self):
        self.requests = []

    def generate_keyword_ideas(self, request):
        self.requests.append(request)
        return [
            SimpleNamespace(
                text="digital marketing agency",
                keyword_idea_metrics=SimpleNamespace(
                    avg_monthly_searches=5400,
                    competition=SimpleNamespace(name="MEDIUM"),
                    competition_index=50,
                    low_top_of_page_bid_micros=1_000_000,
                    high_top_of_page_bid_micros=3_000_000,
                ),
            ),
            SimpleNamespace(
                text="ppc agency",
                keyword_idea_metrics=SimpleNamespace(
                    avg_monthly_searches=1200,
                    competition=SimpleNamespace(name="LOW"),
                    competition_index=20,
                    low_top_of_page_bid_micros=500_000,
                    high_top_of_page_bid_micros=1_500_000,
                ),
            ),
        ]

    def generate_keyword_historical_metrics(self, request):
        self.requests.append(request)
        return SimpleNamespace(
            results=[
                SimpleNamespace(
                    text="seo services",
                    keyword_metrics=SimpleNamespace(
                        avg_monthly_searches=9900,
                        competition=SimpleNamespace(name="HIGH"),
                        low_top_of_page_bid_micros=2_000_000,
                        high_top_of_page_bid_micros=5_000_000,
                    ),
                )
            ]
        )


def _ctx_with_keyword_planner():
    fake_service = _FakeKeywordPlanIdeaService()
    ctx = build_ctx(lambda *a, **k: None, extra_services={"KeywordPlanIdeaService": fake_service})
    tool_fns = register_module(tools.keyword_planner, ctx)
    return ctx, tool_fns, fake_service


def test_generate_keyword_ideas_requires_seed():
    _, tool_fns, _ = _ctx_with_keyword_planner()

    with pytest.raises(ValueError, match="at least one"):
        tool_fns["generate_keyword_ideas"](customer_id="123-456-7890", keywords=[], page_url="")


def test_generate_keyword_ideas_with_keyword_seed():
    _, tool_fns, fake_service = _ctx_with_keyword_planner()

    result = tool_fns["generate_keyword_ideas"](
        customer_id="123-456-7890",
        keywords=["marketing agency"],
        language="en",
        geo_target_ids=["2840"],
        limit=1,
    )

    assert len(fake_service.requests) == 1
    request = fake_service.requests[0]
    assert request.customer_id == "1234567890"
    assert request.language == "languageConstants/1000"
    assert list(request.geo_target_constants) == ["geoTargetConstants/2840"]
    assert list(request.keyword_seed.keywords) == ["marketing agency"]

    assert result["idea_count"] == 1
    assert result["seed_keywords"] == ["marketing agency"]
    assert result["ideas"][0]["keyword"] == "digital marketing agency"
    assert result["ideas"][0]["low_bid"] == 1.0
    assert result["ideas"][0]["high_bid"] == 3.0


def test_generate_keyword_ideas_with_url_and_keyword_seed():
    _, tool_fns, fake_service = _ctx_with_keyword_planner()

    result = tool_fns["generate_keyword_ideas"](
        customer_id="1234567890",
        keywords=["agency"],
        page_url="https://example.com",
        language="es",
    )

    request = fake_service.requests[0]
    assert request.keyword_and_url_seed.url == "https://example.com"
    assert list(request.keyword_and_url_seed.keywords) == ["agency"]
    assert request.language == "languageConstants/1003"

    assert result["seed_url"] == "https://example.com"


def test_generate_keyword_ideas_enforces_limit_range():
    _, tool_fns, _ = _ctx_with_keyword_planner()

    with pytest.raises(ValueError, match="limit"):
        tool_fns["generate_keyword_ideas"](customer_id="123", keywords=["x"], limit=0)

    with pytest.raises(ValueError, match="limit"):
        tool_fns["generate_keyword_ideas"](customer_id="123", keywords=["x"], limit=2001)


def test_generate_keyword_ideas_rejects_invalid_customer_id():
    _, tool_fns, _ = _ctx_with_keyword_planner()

    with pytest.raises(ValueError, match="customer_id"):
        tool_fns["generate_keyword_ideas"](customer_id="abc", keywords=["x"])


def test_generate_keyword_ideas_rejects_bad_page_url():
    _, tool_fns, _ = _ctx_with_keyword_planner()

    with pytest.raises(ValueError, match="http"):
        tool_fns["generate_keyword_ideas"](customer_id="123", page_url="example.com")


def test_get_keyword_historical_metrics_requires_keywords():
    _, tool_fns, _ = _ctx_with_keyword_planner()

    with pytest.raises(ValueError, match="at least one keyword"):
        tool_fns["get_keyword_historical_metrics"](customer_id="123", keywords=[])


def test_get_keyword_historical_metrics_lookups_metrics():
    _, tool_fns, fake_service = _ctx_with_keyword_planner()

    result = tool_fns["get_keyword_historical_metrics"](
        customer_id="123-456-7890",
        keywords=["seo services"],
        language="en",
        geo_target_ids=["2840"],
    )

    assert len(fake_service.requests) == 1
    request = fake_service.requests[0]
    assert request.customer_id == "1234567890"
    assert list(request.keywords) == ["seo services"]
    assert request.language == "languageConstants/1000"

    assert result["result_count"] == 1
    assert result["results"][0]["keyword"] == "seo services"
    assert result["results"][0]["avg_monthly_searches"] == 9900
    assert result["results"][0]["low_bid"] == 2.0
    assert result["results"][0]["high_bid"] == 5.0


def test_unsupported_language_raises():
    _, tool_fns, _ = _ctx_with_keyword_planner()

    with pytest.raises(ValueError, match="Unsupported language code"):
        tool_fns["generate_keyword_ideas"](
            customer_id="123", keywords=["x"], language="zz"
        )
