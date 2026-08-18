"""Real Google Ads API v25 protobuf contracts for core write modules.

These tests make no external Google Ads calls. They instantiate the official
31.x client's v25 message/service surface and capture the operations each MCP
tool builds. This catches fields/enums/types that AutoVivify unit fakes cannot.
"""

from __future__ import annotations

from types import SimpleNamespace

from google.ads.googleads.client import GoogleAdsClient
from google.oauth2.credentials import Credentials

from conftest import FakeAuditLog, FakeMcp, FakeMutateResult
from google_ads_mcp.context import AppContext
from google_ads_mcp.safety import SafetyLayer
from google_ads_mcp.tools import (
    ad_groups,
    audiences,
    bidding,
    budgets,
    experiments,
    keywords,
    targeting,
)


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

    def copy_from(self, target, source):
        return self.client.copy_from(target, source)


class _CaptureClient:
    def __init__(self, search_fn=None):
        self.raw = _Raw()
        self.calls = []
        self.search_fn = search_fn or (lambda customer_id, query: [])

    def search(self, customer_id, query):
        return self.search_fn(customer_id, query)

    def mutate(self, service_name, customer_id, operations, **kwargs):
        operation_list = list(operations)
        self.calls.append((service_name, operation_list, kwargs))
        if service_name == "ExperimentService":
            return FakeMutateResult("customers/1234567890/experiments/111")
        if service_name == "ExperimentArmService":
            return FakeMutateResult(
                "customers/1234567890/experimentArms/111~control",
                "customers/1234567890/experimentArms/111~treatment",
            )
        return FakeMutateResult(f"customers/1234567890/{service_name}/1")

    def mutate_atomic(self, customer_id, operations, **kwargs):
        operation_list = list(operations)
        self.calls.append(("GoogleAdsService", operation_list, kwargs))
        return {"atomic": True, "operation_count": len(operation_list)}


def _ctx(search_fn=None):
    client = _CaptureClient(search_fn=search_fn)
    audit = FakeAuditLog()
    safety = SafetyLayer(auto_approve=True, ttl_minutes=30, audit_log=audit)
    return AppContext(settings=None, client=client, safety=safety, audit=audit), client


def _tools(module, ctx):
    mcp = FakeMcp()
    module.register(mcp, ctx)
    return mcp.registered


def test_budget_create_uses_real_v25_standard_delivery():
    ctx, client = _ctx()
    result = _tools(budgets, ctx)["create_campaign_budget"](
        customer_id="1234567890",
        name="Daily budget",
        daily_amount=100.0,
    )

    assert result["status"] == "executed"
    operation = client.calls[0][1][0]
    assert operation.create.amount_micros == 100_000_000
    assert operation.create.delivery_method.name == "STANDARD"


def test_maximize_clicks_without_ceiling_builds_real_target_spend():
    ctx, client = _ctx()
    result = _tools(bidding, ctx)["set_maximize_clicks"](
        customer_id="1234567890",
        campaign_id="111",
    )

    assert result["status"] == "executed"
    operation = client.calls[0][1][0]
    assert operation.update.resource_name.endswith("/campaigns/111")
    assert list(operation.update_mask.paths) == ["target_spend"]


def test_maximize_conversions_without_target_builds_real_strategy():
    ctx, client = _ctx()
    result = _tools(bidding, ctx)["set_maximize_conversions"](
        customer_id="1234567890",
        campaign_id="111",
    )

    assert result["status"] == "executed"
    operation = client.calls[0][1][0]
    assert list(operation.update_mask.paths) == ["maximize_conversions"]


def test_target_impression_share_real_fields():
    ctx, client = _ctx()
    result = _tools(bidding, ctx)["set_target_impression_share"](
        customer_id="1234567890",
        campaign_id="111",
        location="TOP_OF_PAGE",
        target_percent=75,
        max_cpc_bid_ceiling=2.5,
    )

    assert result["status"] == "executed"
    tis = client.calls[0][1][0].update.target_impression_share
    assert tis.location.name == "TOP_OF_PAGE"
    assert tis.location_fraction_micros == 750_000
    assert tis.cpc_bid_ceiling_micros == 2_500_000


def test_search_ad_group_auto_builds_real_search_standard_type():
    def search(customer_id, query):
        return [{"campaign": {"advertising_channel_type": "SEARCH"}}]

    ctx, client = _ctx(search)
    result = _tools(ad_groups, ctx)["create_ad_group"](
        customer_id="1234567890",
        campaign_id="111",
        name="Search AG",
    )

    assert result["status"] == "executed"
    assert client.calls[0][1][0].create.type_.name == "SEARCH_STANDARD"


def test_demand_gen_ad_group_leaves_type_unspecified():
    def search(customer_id, query):
        return [{"campaign": {"advertising_channel_type": "DEMAND_GEN"}}]

    ctx, client = _ctx(search)
    result = _tools(ad_groups, ctx)["create_ad_group"](
        customer_id="1234567890",
        campaign_id="111",
        name="Demand Gen AG",
    )

    assert result["status"] == "executed"
    assert client.calls[0][1][0].create.type_.name == "UNSPECIFIED"


def test_language_setter_builds_real_remove_and_create_operations():
    def search(customer_id, query):
        return [
            {
                "campaign_criterion": {
                    "criterion_id": 222,
                    "language": {"language_constant": "languageConstants/1000"},
                }
            }
        ]

    ctx, client = _ctx(search)
    result = _tools(targeting, ctx)["set_language_targeting"](
        customer_id="1234567890",
        campaign_id="111",
        language_codes=["1003"],
    )

    assert result["status"] == "executed"
    operations = client.calls[0][1]
    assert operations[0].remove.endswith("/campaignCriteria/111~222")
    assert operations[1].create.language.language_constant.endswith(
        "/languageConstants/1003"
    )


def test_device_setter_updates_existing_real_criterion():
    def search(customer_id, query):
        return [
            {
                "campaign_criterion": {
                    "criterion_id": 333,
                    "device": {"type": "MOBILE"},
                    "bid_modifier": 1.0,
                }
            }
        ]

    ctx, client = _ctx(search)
    result = _tools(targeting, ctx)["set_device_bid_modifier"](
        customer_id="1234567890",
        campaign_id="111",
        device="MOBILE",
        bid_modifier=0,
    )

    assert result["status"] == "executed"
    operation = client.calls[0][1][0]
    assert operation.update.resource_name.endswith("/campaignCriteria/111~333")
    assert operation.update.bid_modifier == 0
    assert list(operation.update_mask.paths) == ["bid_modifier"]


def test_remarketing_rule_uses_real_flexible_rule_messages():
    ctx, client = _ctx()
    result = _tools(audiences, ctx)["create_remarketing_list"](
        customer_id="1234567890",
        name="All site visitors",
        membership_days=30,
        url_contains="example.com",
    )

    assert result["status"] == "executed"
    user_list = client.calls[0][1][0].create
    flexible = user_list.rule_based_user_list.flexible_rule_user_list
    assert len(flexible.inclusive_operands) == 1
    item = flexible.inclusive_operands[0].rule.rule_item_groups[0].rule_items[0]
    assert item.name == "url__"
    assert item.string_rule_item.operator.name == "CONTAINS"
    assert item.string_rule_item.value == "example.com"


def test_keyword_match_type_recreate_uses_real_create_plus_remove():
    def search(customer_id, query):
        return [
            {
                "ad_group_criterion": {
                    "keyword": {"text": "google ads", "match_type": "BROAD"},
                    "cpc_bid_micros": 2_000_000,
                }
            }
        ]

    ctx, client = _ctx(search)
    result = _tools(keywords, ctx)["update_keyword_match_type"](
        customer_id="1234567890",
        ad_group_id="111",
        criterion_id="222",
        match_type="PHRASE",
    )

    assert result["status"] == "executed"
    operations = client.calls[0][1]
    assert operations[0].create.keyword.match_type.name == "PHRASE"
    assert operations[1].remove.endswith("/adGroupCriteria/111~222")
    assert client.calls[0][2]["partial_failure"] is False


def test_experiment_setup_builds_real_v25_arms():
    ctx, client = _ctx()
    result = _tools(experiments, ctx)["create_experiment"](
        customer_id="1234567890",
        base_campaign_id="111",
        name="Bidding experiment",
        traffic_split_percent=50,
    )

    assert result["status"] == "executed"
    assert client.calls[0][0] == "ExperimentService"
    assert client.calls[1][0] == "ExperimentArmService"
    arms = client.calls[1][1]
    assert arms[0].create.control is True
    assert arms[0].create.traffic_split == 50
    assert list(arms[0].create.campaigns) == ["customers/1234567890/campaigns/111"]
    assert arms[1].create.control is False
    assert arms[1].create.traffic_split == 50
    assert list(arms[1].create.campaigns) == []
