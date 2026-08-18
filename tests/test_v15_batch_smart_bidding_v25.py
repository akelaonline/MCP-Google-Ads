"""Real Google Ads API v25 contracts for v0.15 batch and Smart Bidding tools."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from conftest import FakeAuditLog, FakeMcp, FakeMutateResult
from google.ads.googleads.client import GoogleAdsClient
from google.oauth2.credentials import Credentials

from google_ads_mcp.context import AppContext
from google_ads_mcp.safety import RiskLevel, SafetyLayer, classify_risk
from google_ads_mcp.tools import batch_jobs, recommendations, smart_bidding_controls


class _Raw:
    def __init__(self):
        self.client = GoogleAdsClient(
            credentials=Credentials(token="contract-token"),
            developer_token="contract-developer-token",
            version="v25",
            use_proto_plus=True,
        )
        self.enums = self.client.enums

    def get_type(self, name):
        return self.client.get_type(name)

    def get_service(self, name):
        return self.client.get_service(name)

    def copy_from(self, dest, src):
        return self.client.copy_from(dest, src)


class _BatchJobService:
    def __init__(self, calls):
        self.calls = calls

    def mutate_batch_job(self, **kwargs):
        self.calls.append(("mutate_batch_job", kwargs))
        return SimpleNamespace(
            result=SimpleNamespace(resource_name="customers/1234567890/batchJobs/99")
        )

    def add_batch_job_operations(self, **kwargs):
        self.calls.append(("add_batch_job_operations", kwargs))
        return SimpleNamespace(
            next_sequence_token="seq-1",
            total_operations=len(kwargs["mutate_operations"]),
        )

    def run_batch_job(self, **kwargs):
        self.calls.append(("run_batch_job", kwargs))
        return SimpleNamespace(operation=SimpleNamespace(name="operations/batch-99"))


class _RecommendationService:
    def __init__(self, calls):
        self.calls = calls

    def generate_recommendations(self, **kwargs):
        self.calls.append(("generate_recommendations", kwargs))
        return SimpleNamespace(recommendations=[])


class _CaptureClient:
    def __init__(self):
        self.raw = _Raw()
        self.calls = []

    def assert_customer_allowed(self, customer_id):
        return customer_id.replace("-", "")

    def search(self, customer_id, query):
        self.calls.append(("search", customer_id, query))
        return []

    def mutate(self, service_name, customer_id, operations, **kwargs):
        operation_list = list(operations)
        self.calls.append((service_name, customer_id, operation_list, kwargs))
        return FakeMutateResult(f"customers/{customer_id}/{service_name}/1")

    def service(self, name):
        if name == "BatchJobService":
            return _BatchJobService(self.calls)
        if name == "RecommendationService":
            return _RecommendationService(self.calls)
        return self.raw.get_service(name)


def _ctx():
    client = _CaptureClient()
    audit = FakeAuditLog()
    safety = SafetyLayer(auto_approve=True, ttl_minutes=30, audit_log=audit)
    return AppContext(settings=None, client=client, safety=safety, audit=audit), client


def _tools(module, ctx):
    mcp = FakeMcp()
    module.register(mcp, ctx)
    return mcp.registered


def test_submit_batch_job_builds_real_mixed_v25_mutate_operations():
    ctx, client = _ctx()
    result = _tools(batch_jobs, ctx)["submit_batch_job"](
        customer_id="123-456-7890",
        operations=[
            {"kind": "campaign_status", "campaign_id": "11", "status": "PAUSED"},
            {
                "kind": "campaign_budget_amount",
                "campaign_budget_id": "22",
                "amount": 42.5,
            },
            {
                "kind": "keyword_bid",
                "ad_group_id": "33",
                "criterion_id": "44",
                "cpc_bid": 1.25,
            },
            {
                "kind": "add_campaign_negative_keyword",
                "campaign_id": "11",
                "text": "free",
                "match_type": "PHRASE",
            },
        ],
    )

    assert result["status"] == "executed"
    assert result["risk_level"] == "sensitive"
    create_call = next(call for call in client.calls if call[0] == "mutate_batch_job")
    assert create_call[1]["operation"]._pb.WhichOneof("operation") == "create"
    add_call = next(call for call in client.calls if call[0] == "add_batch_job_operations")
    operations = add_call[1]["mutate_operations"]
    assert len(operations) == 4
    assert operations[0].campaign_operation.update.status.name == "PAUSED"
    assert list(operations[0].campaign_operation.update_mask.paths) == ["status"]
    assert operations[1].campaign_budget_operation.update.amount_micros == 42_500_000
    assert operations[2].ad_group_criterion_operation.update.cpc_bid_micros == 1_250_000
    assert operations[3].campaign_criterion_operation.create.negative is True
    assert operations[3].campaign_criterion_operation.create.keyword.match_type.name == "PHRASE"
    run_call = next(call for call in client.calls if call[0] == "run_batch_job")
    assert run_call[1]["resource_name"] == "customers/1234567890/batchJobs/99"


def test_batch_keyword_removed_uses_real_remove_operation():
    raw = _Raw()
    operation = batch_jobs._build_batch_mutate(
        raw,
        "1234567890",
        {
            "kind": "keyword_status",
            "ad_group_id": "33",
            "criterion_id": "44",
            "status": "REMOVED",
        },
    )
    nested = operation.ad_group_criterion_operation
    assert nested._pb.WhichOneof("operation") == "remove"
    assert nested.remove == "customers/1234567890/adGroupCriteria/33~44"


def test_batch_job_rejects_arbitrary_raw_operation_kind():
    ctx, _ = _ctx()
    with pytest.raises(ValueError, match="Unsupported batch operation kind"):
        _tools(batch_jobs, ctx)["submit_batch_job"](
            customer_id="1234567890",
            operations=[{"kind": "customer_user_access", "raw": {"danger": True}}],
        )


def test_seasonality_adjustment_builds_real_v25_contract():
    ctx, client = _ctx()
    result = _tools(smart_bidding_controls, ctx)["create_seasonality_adjustment"](
        customer_id="1234567890",
        name="Cyber Monday",
        start_date_time="2026-11-30 00:00:00",
        end_date_time="2026-12-01 00:00:00",
        conversion_rate_modifier=1.8,
        scope="CHANNEL",
        advertising_channel_types=["SEARCH", "SHOPPING"],
        devices=["DESKTOP", "MOBILE"],
    )

    assert result["status"] == "executed"
    assert result["risk_level"] == "spend"
    call = next(
        call for call in client.calls if call[0] == "BiddingSeasonalityAdjustmentService"
    )
    operation = call[2][0]
    item = operation.create
    assert item.scope.name == "CHANNEL"
    assert [value.name for value in item.advertising_channel_types] == [
        "SEARCH",
        "SHOPPING",
    ]
    assert item.conversion_rate_modifier == 1.8
    assert [value.name for value in item.devices] == ["DESKTOP", "MOBILE"]


def test_data_exclusion_campaign_scope_builds_real_v25_contract():
    ctx, client = _ctx()
    result = _tools(smart_bidding_controls, ctx)["create_data_exclusion"](
        customer_id="1234567890",
        name="Broken checkout tracking",
        start_date_time="2026-08-17 10:00:00",
        end_date_time="2026-08-17 13:00:00",
        scope="CAMPAIGN",
        campaign_ids=["111", "222"],
    )

    assert result["status"] == "executed"
    assert result["risk_level"] == "spend"
    call = next(call for call in client.calls if call[0] == "BiddingDataExclusionService")
    item = call[2][0].create
    assert item.scope.name == "CAMPAIGN"
    assert list(item.campaigns) == [
        "customers/1234567890/campaigns/111",
        "customers/1234567890/campaigns/222",
    ]


def test_smart_bidding_event_rejects_more_than_14_days():
    ctx, _ = _ctx()
    with pytest.raises(ValueError, match="14 days"):
        _tools(smart_bidding_controls, ctx)["create_data_exclusion"](
            customer_id="1234567890",
            name="Too long",
            start_date_time="2026-08-01 00:00:00",
            end_date_time="2026-08-16 00:00:01",
        )


def test_generate_keyword_recommendations_builds_real_v25_request():
    ctx, client = _ctx()
    result = _tools(recommendations, ctx)["generate_keyword_recommendations"](
        customer_id="1234567890",
        seed_keywords=["google ads agency", "ppc management"],
        url_seed="https://example.com/google-ads",
    )

    assert result["count"] == 0
    call = next(call for call in client.calls if call[0] == "generate_recommendations")
    request = call[1]["request"]
    assert request.customer_id == "1234567890"
    assert request.advertising_channel_type.name == "SEARCH"
    assert [value.name for value in request.recommendation_types] == ["KEYWORD"]
    assert list(request.seed_info.keyword_seeds) == [
        "google ads agency",
        "ppc management",
    ]
    assert request.seed_info.url_seed == "https://example.com/google-ads"


def test_v15_risk_classification_is_conservative():
    assert classify_risk("submit_batch_job", {}) is RiskLevel.SENSITIVE
    assert classify_risk("create_seasonality_adjustment", {}) is RiskLevel.SPEND
    assert classify_risk("create_data_exclusion", {}) is RiskLevel.SPEND
    assert classify_risk("remove_data_exclusion", {}) is RiskLevel.DESTRUCTIVE
