"""Regression tests for cross-customer isolation and experiment lifecycle coverage."""

from __future__ import annotations

import pytest
from google.ads.googleads.client import GoogleAdsClient
from google.oauth2.credentials import Credentials

from google_ads_mcp.client import (
    GoogleAdsClientWrapper,
    _assert_mutation_targets_customer,
)
from google_ads_mcp.config import Settings
from google_ads_mcp.errors import GoogleAdsMcpError
from google_ads_mcp.safety import RiskLevel, classify_risk


def _raw_client() -> GoogleAdsClient:
    return GoogleAdsClient(
        credentials=Credentials(token="contract-token"),
        developer_token="contract-developer-token",
        version="v25",
        use_proto_plus=True,
    )


def _settings() -> Settings:
    return Settings(
        developer_token="dev",
        client_id="client",
        client_secret="secret",
        refresh_token="refresh",
        login_customer_id=None,
        auto_approve=False,
        pending_ttl_minutes=30,
        audit_db_path=":memory:",
        transport="stdio",
        http_port=8080,
        allowed_customer_ids=frozenset({"1111111111", "2222222222"}),
        require_customer_allowlist=True,
    )


def test_resource_name_guard_blocks_other_allowed_customer():
    wrapper = GoogleAdsClientWrapper(_settings())
    assert (
        wrapper.assert_resource_name_customer(
            "111-111-1111", "customers/1111111111/campaigns/99"
        )
        == "customers/1111111111/campaigns/99"
    )

    with pytest.raises(GoogleAdsMcpError, match="Cross-customer mutation"):
        wrapper.assert_resource_name_customer(
            "1111111111", "customers/2222222222/campaigns/99"
        )


def test_resource_specific_update_cannot_target_another_customer():
    raw = _raw_client()
    operation = raw.get_type("CampaignOperation")
    operation.update.resource_name = "customers/2222222222/campaigns/7"
    operation.update.status = raw.enums.CampaignStatusEnum.PAUSED

    with pytest.raises(GoogleAdsMcpError, match="Cross-customer mutation blocked"):
        _assert_mutation_targets_customer("1111111111", [operation])


def test_resource_specific_remove_cannot_target_another_customer():
    raw = _raw_client()
    operation = raw.get_type("AdGroupCriterionOperation")
    operation.remove = "customers/2222222222/adGroupCriteria/10~20"

    with pytest.raises(GoogleAdsMcpError, match="Cross-customer mutation blocked"):
        _assert_mutation_targets_customer("1111111111", [operation])


def test_atomic_mutate_wrapper_detects_mixed_customer_nested_operation():
    raw = _raw_client()
    operation = raw.get_type("MutateOperation")
    operation.campaign_operation.update.resource_name = (
        "customers/2222222222/campaigns/7"
    )
    operation.campaign_operation.update.status = raw.enums.CampaignStatusEnum.PAUSED

    with pytest.raises(GoogleAdsMcpError, match="Cross-customer mutation blocked"):
        _assert_mutation_targets_customer("1111111111", [operation])


def test_same_customer_targets_are_allowed():
    raw = _raw_client()
    operation = raw.get_type("MutateOperation")
    operation.campaign_operation.update.resource_name = (
        "customers/1111111111/campaigns/7"
    )
    operation.campaign_operation.update.status = raw.enums.CampaignStatusEnum.PAUSED

    _assert_mutation_targets_customer("1111111111", [operation])


def test_v25_experiment_lifecycle_contracts_exist():
    raw = _raw_client()

    schedule = raw.get_type("ScheduleExperimentRequest")
    schedule.resource_name = "customers/1111111111/experiments/1"
    assert schedule.resource_name.endswith("/experiments/1")

    async_errors = raw.get_type("ListExperimentAsyncErrorsRequest")
    async_errors.resource_name = "customers/1111111111/experiments/1"
    async_errors.page_size = 1000
    assert async_errors.page_size == 1000

    graduate = raw.get_type("GraduateExperimentRequest")
    graduate.experiment = "customers/1111111111/experiments/1"
    mapping = raw.get_type("CampaignBudgetMapping")
    mapping.experiment_campaign = "customers/1111111111/campaigns/2"
    mapping.campaign_budget = "customers/1111111111/campaignBudgets/3"
    graduate.campaign_budget_mappings.append(mapping)

    assert graduate.campaign_budget_mappings[0].experiment_campaign.endswith(
        "/campaigns/2"
    )
    assert graduate.campaign_budget_mappings[0].campaign_budget.endswith(
        "/campaignBudgets/3"
    )


def test_experiment_launch_and_graduation_are_spend_risk():
    assert classify_risk("schedule_experiment", {}) is RiskLevel.SPEND
    assert classify_risk("graduate_experiment", {}) is RiskLevel.SPEND
    assert classify_risk("promote_experiment", {}) is RiskLevel.SPEND
    assert classify_risk("end_experiment", {}) is RiskLevel.DESTRUCTIVE
