"""Tests for tools/recommendations.py — apply and dismiss recommendations."""

from __future__ import annotations

from types import SimpleNamespace

from conftest import build_ctx, register_module

from google_ads_mcp import tools


class _FakeRecommendationService:
    def __init__(self):
        self.calls = []

    def apply_recommendation(self, *, customer_id, operations):
        self.calls.append(("apply", customer_id, [o.resource_name for o in operations]))
        return SimpleNamespace(
            results=[SimpleNamespace(resource_name="customers/123/recommendations/456")]
        )

    def dismiss_recommendation(self, *, customer_id, operations):
        self.calls.append(
            ("dismiss", customer_id, [o.resource_name for o in operations])
        )
        return SimpleNamespace(
            results=[SimpleNamespace(resource_name="customers/123/recommendations/456")]
        )


def test_apply_recommendation_executes_when_auto_approved():
    fake_service = _FakeRecommendationService()
    ctx = build_ctx(
        lambda *a, **k: None,
        extra_services={"RecommendationService": fake_service},
    )
    tool_fns = register_module(tools.recommendations, ctx)

    result = tool_fns["apply_recommendation"](
        customer_id="123-456-7890",
        resource_name="customers/123/recommendations/456",
    )

    assert result["status"] == "executed"
    assert fake_service.calls == [
        ("apply", "1234567890", ["customers/123/recommendations/456"])
    ]


def test_dismiss_recommendation_executes_when_auto_approved():
    fake_service = _FakeRecommendationService()
    ctx = build_ctx(
        lambda *a, **k: None,
        extra_services={"RecommendationService": fake_service},
    )
    tool_fns = register_module(tools.recommendations, ctx)

    result = tool_fns["dismiss_recommendation"](
        customer_id="123-456-7890",
        resource_name="customers/123/recommendations/456",
    )

    assert result["status"] == "executed"
    assert fake_service.calls == [
        ("dismiss", "1234567890", ["customers/123/recommendations/456"])
    ]
