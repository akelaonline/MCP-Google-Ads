"""Regression tests for the mutate-method-name resolution bug.

Two real production failures motivated these tests:

1. `_mutate_method_name` assumed every service pluralizes by appending "s",
   which breaks for any service ending in "Criterion" (the real method is
   "..._criteria", not "..._criterions"). This broke add_negative_keywords,
   update_keyword_status, and remove_keyword.

2. `GoogleAdsClientWrapper.mutate` always passed `partial_failure` and
   `validate_only` to the underlying mutate call, but some services (e.g.
   CampaignBudgetService.mutate_campaign_budgets) don't accept those kwargs
   at all. This broke create_campaign_budget and update_campaign_budget.
"""

from __future__ import annotations

import inspect

import pytest

from google_ads_mcp.client import GoogleAdsClientWrapper, _mutate_method_name


# ---- Bug 1: irregular pluralization (Criterion -> Criteria) ----------------


@pytest.mark.parametrize(
    "service_name, expected_method",
    [
        ("CampaignService", "mutate_campaigns"),
        ("CampaignBudgetService", "mutate_campaign_budgets"),
        ("AdGroupService", "mutate_ad_groups"),
        ("AdGroupAdService", "mutate_ad_group_ads"),
        # Irregulars: Criterion -> Criteria, not Criterions.
        ("CampaignCriterionService", "mutate_campaign_criteria"),
        ("AdGroupCriterionService", "mutate_ad_group_criteria"),
        ("AssetGroupCriterionService", "mutate_asset_group_criteria"),
        ("CustomerNegativeCriterionService", "mutate_customer_negative_criteria"),
    ],
)
def test_mutate_method_name(service_name, expected_method):
    assert _mutate_method_name(service_name) == expected_method


def test_mutate_method_name_never_produces_criterions():
    """Guard specifically against the exact bug that shipped: 'criterions'
    is not a word, and every *CriterionService in the Google Ads API pluralizes
    as *criteria."""
    for service_name in [
        "CampaignCriterionService",
        "AdGroupCriterionService",
        "AssetGroupCriterionService",
        "CustomerNegativeCriterionService",
    ]:
        method = _mutate_method_name(service_name)
        assert not method.endswith("criterions"), (
            f"{service_name} resolved to {method!r}, which is not a real "
            f"Google Ads API method"
        )


# ---- Bug 2: not every mutate RPC accepts partial_failure/validate_only ----


class _FakeCampaignBudgetService:
    """Mimics CampaignBudgetService.mutate_campaign_budgets: no
    partial_failure/validate_only kwargs."""

    def __init__(self):
        self.received_kwargs = None

    def mutate_campaign_budgets(self, *, customer_id, operations):
        self.received_kwargs = {"customer_id": customer_id, "operations": operations}
        return "ok"


class _FakeCampaignCriterionService:
    """Mimics a service that does accept partial_failure/validate_only."""

    def __init__(self):
        self.received_kwargs = None

    def mutate_campaign_criteria(
        self, *, customer_id, operations, partial_failure=False, validate_only=False
    ):
        self.received_kwargs = {
            "customer_id": customer_id,
            "operations": operations,
            "partial_failure": partial_failure,
            "validate_only": validate_only,
        }
        return "ok"


class _FakeSettings:
    google_ads_yaml_dict = {}


def _wrapper_with_fake_service(fake_service):
    wrapper = GoogleAdsClientWrapper(_FakeSettings())
    wrapper.service = lambda name: fake_service  # bypass real client construction
    return wrapper


def test_mutate_omits_unsupported_kwargs():
    """create_campaign_budget / update_campaign_budget must not crash with
    'got an unexpected keyword argument partial_failure'."""
    fake_service = _FakeCampaignBudgetService()
    wrapper = _wrapper_with_fake_service(fake_service)

    result = wrapper.mutate("CampaignBudgetService", "123-456-7890", ["op1"])

    assert result == "ok"
    assert fake_service.received_kwargs == {
        "customer_id": "1234567890",
        "operations": ["op1"],
    }


def test_mutate_passes_supported_kwargs():
    """When the underlying method does declare partial_failure/validate_only,
    they should still be passed through."""
    fake_service = _FakeCampaignCriterionService()
    wrapper = _wrapper_with_fake_service(fake_service)

    result = wrapper.mutate(
        "CampaignCriterionService", "1234567890", ["op1"], partial_failure=True
    )

    assert result == "ok"
    assert fake_service.received_kwargs == {
        "customer_id": "1234567890",
        "operations": ["op1"],
        "partial_failure": True,
        "validate_only": False,
    }


def test_mutate_raises_clear_error_for_missing_method():
    """If a service genuinely has no matching mutate method (e.g. a future
    irregular we haven't catalogued yet), fail with a clear, actionable
    error instead of an opaque AttributeError."""
    from google_ads_mcp.errors import GoogleAdsMcpError

    class _EmptyService:
        pass

    wrapper = _wrapper_with_fake_service(_EmptyService())

    with pytest.raises(GoogleAdsMcpError, match="_IRREGULAR_MUTATE_METHODS"):
        wrapper.mutate("SomeUncataloguedCriterionService", "1234567890", ["op1"])
