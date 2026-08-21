"""v25 contract tests for the 0.16.4 functional-gap tools.

These instantiate Google's real v25 protobuf types through the real
GoogleAdsClient (no network calls happen: only get_type/enums/path helpers and
captured executes are exercised). They are the guard that the new tools build
valid v25 messages with correct update masks.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from google.ads.googleads.client import GoogleAdsClient
from google.oauth2.credentials import Credentials

from google_ads_mcp.tools import (
    app_campaigns,
    conversions,
    dynamic_search_ads,
    targeting,
    url_options,
)


class _FakeMcp:
    def __init__(self):
        self.tools = {}

    def tool(self, function=None, *args, **kwargs):
        def register(func):
            self.tools[kwargs.get("name") or func.__name__] = func
            return func

        if function is None:
            return register
        return register(function)


class _CapturingSafety:
    def __init__(self):
        self.last = None

    def propose(self, **kwargs):
        self.last = kwargs
        return {
            "status": "pending_confirmation",
            "pending_action_id": "test-action",
            "risk_alias": kwargs["tool_name"],
        }


def _raw_client() -> GoogleAdsClient:
    return GoogleAdsClient(
        credentials=Credentials(token="contract-token"),
        developer_token="contract-developer-token",
        version="v25",
        use_proto_plus=True,
    )


class _CaptureClient:
    def __init__(self, search_rows=None):
        self.raw = _raw_client()
        self.last_mutate = None
        self._search_rows = search_rows or []

    def assert_customer_allowed(self, customer_id: str) -> str:
        value = str(customer_id).replace("-", "").strip()
        if value != "1111111111":
            raise AssertionError(f"unexpected customer {value}")
        return value

    def assert_resource_name_customer(
        self, customer_id: str, resource_name: str, *, field_name: str = "resource_name"
    ) -> str:
        customer = self.assert_customer_allowed(customer_id)
        value = str(resource_name).strip()
        if not value.startswith(f"customers/{customer}/"):
            raise ValueError(f"{field_name} belongs to another customer")
        return value

    def search(self, customer_id: str, query: str):
        return self._search_rows

    def mutate(
        self,
        service_name: str,
        customer_id: str,
        operations,
        *,
        partial_failure: bool = False,
        validate_only: bool = False,
        **kwargs,
    ):
        # Mirrors client.py: customer ids are normalized by the client layer.
        customer_id = self.assert_customer_allowed(customer_id)
        self.last_mutate = {
            "service_name": service_name,
            "customer_id": customer_id,
            "operations": list(operations),
            "partial_failure": partial_failure,
            "validate_only": validate_only,
        }
        return SimpleNamespace(results=[])


def _propose_and_execute(module, tool_name: str, **kwargs):
    client = _CaptureClient()
    safety = _CapturingSafety()
    mcp = _FakeMcp()
    module.register(mcp, SimpleNamespace(client=client, safety=safety))
    assert tool_name in mcp.tools
    response = mcp.tools[tool_name](customer_id="111-111-1111", **kwargs)
    assert response["status"] == "pending_confirmation"
    safety.last["execute"]()
    return client.last_mutate


def test_set_campaign_tracking_url_builds_valid_update_mask():
    call = _propose_and_execute(
        url_options,
        "set_campaign_tracking_url",
        campaign_id="123",
        tracking_url_template="{lpurl}?utm_source=mcp",
        final_url_suffix="?utm_medium=cpc",
        url_custom_parameters=[{"key": "utm_campaign", "value": "summer"}],
    )
    assert call["service_name"] == "CampaignService"
    assert call["customer_id"] == "1111111111"
    op = call["operations"][0]
    assert op.update.resource_name == "customers/1111111111/campaigns/123"
    assert op.update.tracking_url_template == "{lpurl}?utm_source=mcp"
    assert op.update.final_url_suffix == "?utm_medium=cpc"
    params = list(op.update.url_custom_parameters)
    assert len(params) == 1
    assert params[0].key == "utm_campaign" and params[0].value == "summer"
    assert sorted(op.update_mask.paths) == [
        "final_url_suffix",
        "tracking_url_template",
        "url_custom_parameters",
    ]


def test_set_campaign_tracking_url_clears_parameters_when_empty_list():
    call = _propose_and_execute(
        url_options,
        "set_campaign_tracking_url",
        campaign_id="123",
        url_custom_parameters=[],
    )
    op = call["operations"][0]
    assert list(op.update.url_custom_parameters) == []
    assert op.update_mask.paths == ["url_custom_parameters"]


def test_set_ad_group_tracking_url_builds_valid_update_mask():
    call = _propose_and_execute(
        url_options,
        "set_ad_group_tracking_url",
        ad_group_id="456",
        tracking_url_template="{lpurl}?adgroup={adgroupid}",
    )
    assert call["service_name"] == "AdGroupService"
    op = call["operations"][0]
    assert op.update.resource_name == "customers/1111111111/adGroups/456"
    assert op.update.tracking_url_template == "{lpurl}?adgroup={adgroupid}"
    assert op.update_mask.paths == ["tracking_url_template"]


def test_set_account_tracking_url_builds_valid_update_mask():
    call = _propose_and_execute(
        url_options,
        "set_account_tracking_url",
        tracking_url_template="{lpurl}?src=account",
        final_url_suffix="&utm_source=google",
    )
    assert call["service_name"] == "CustomerService"
    op = call["operations"][0]
    assert op.update.resource_name == "customers/1111111111"
    assert op.update.tracking_url_template == "{lpurl}?src=account"
    assert op.update.final_url_suffix == "&utm_source=google"
    assert sorted(op.update_mask.paths) == ["final_url_suffix", "tracking_url_template"]


def test_update_ad_schedule_builds_valid_update_mask():
    call = _propose_and_execute(
        targeting,
        "update_ad_schedule",
        campaign_id="123",
        criterion_id="789",
        end_hour=22,
        bid_modifier=1.5,
    )
    assert call["service_name"] == "CampaignCriterionService"
    op = call["operations"][0]
    assert op.update.resource_name == "customers/1111111111/campaignCriteria/123~789"
    assert op.update.ad_schedule.end_hour == 22
    assert op.update.ad_schedule.end_minute == 2  # MinuteOfHour.ZERO in v25
    assert op.update.bid_modifier == 1.5
    assert sorted(op.update_mask.paths) == [
        "ad_schedule.end_hour",
        "ad_schedule.end_minute",
        "bid_modifier",
    ]


def test_remove_ad_schedule_builds_remove_operation():
    call = _propose_and_execute(
        targeting,
        "remove_ad_schedule",
        campaign_id="123",
        criterion_id="789",
    )
    assert call["service_name"] == "CampaignCriterionService"
    op = call["operations"][0]
    assert op.remove == "customers/1111111111/campaignCriteria/123~789"


def test_create_app_campaign_builds_valid_v25_message():
    call = _propose_and_execute(
        app_campaigns,
        "create_app_campaign",
        name="App Install Campaign",
        campaign_budget_resource_name="customers/1111111111/campaignBudgets/1",
        app_id="com.example.app",
        app_store="GOOGLE_APP_STORE",
        bidding_strategy_goal_type="OPTIMIZE_INSTALLS_TARGET_INSTALL_COST",
        target_cpa=2.5,
    )
    assert call["service_name"] == "CampaignService"
    campaign = call["operations"][0].create
    assert campaign.advertising_channel_type == 7  # MULTI_CHANNEL in v25
    assert campaign.advertising_channel_sub_type == 12  # APP_CAMPAIGN in v25
    assert campaign.status == 3  # PAUSED
    assert campaign.app_campaign_setting.app_id == "com.example.app"
    assert campaign.app_campaign_setting.app_store == 3  # GOOGLE_APP_STORE
    assert campaign.app_campaign_setting.bidding_strategy_goal_type == 2
    assert campaign.target_cpa.target_cpa_micros == 2500000
    assert campaign._pb.WhichOneof("campaign_bidding_strategy") == "target_cpa"


def test_create_app_campaign_without_target_uses_maximize_conversions():
    call = _propose_and_execute(
        app_campaigns,
        "create_app_campaign",
        name="Pre-reg Campaign",
        campaign_budget_resource_name="customers/1111111111/campaignBudgets/1",
        app_id="com.example.prereg",
        app_store="APPLE_APP_STORE",
        bidding_strategy_goal_type="OPTIMIZE_PRE_REGISTRATION_CONVERSION_VOLUME",
    )
    campaign = call["operations"][0].create
    assert campaign._pb.WhichOneof("campaign_bidding_strategy") == "maximize_conversions"
    assert campaign.target_cpa.target_cpa_micros == 0  # not set


def test_create_dsa_campaign_builds_valid_v25_message():
    call = _propose_and_execute(
        dynamic_search_ads,
        "create_dsa_campaign",
        name="DSA Campaign",
        campaign_budget_resource_name="customers/1111111111/campaignBudgets/1",
        domain_name="Example.com",
        language_code="es",
        use_supplied_urls_only=True,
    )
    assert call["service_name"] == "CampaignService"
    campaign = call["operations"][0].create
    assert campaign.advertising_channel_type == 2  # SEARCH
    # v25 has no SEARCH_DYNAMIC_ADS channel sub-type; the marker is the ad
    # group type, so sub_type must remain UNSPECIFIED on the campaign.
    assert campaign.advertising_channel_sub_type == 0
    assert campaign.status == 3  # PAUSED
    assert campaign.dynamic_search_ads_setting.domain_name == "example.com"
    assert campaign.dynamic_search_ads_setting.language_code == "es"
    assert campaign.dynamic_search_ads_setting.use_supplied_urls_only is True
    assert campaign.network_settings.target_google_search is True
    assert campaign.network_settings.target_search_network is True
    assert campaign.manual_cpc is not None


def test_create_dsa_ad_group_builds_valid_v25_message():
    call = _propose_and_execute(
        dynamic_search_ads,
        "create_dsa_ad_group",
        campaign_id="123",
        name="DSA Ad Group",
    )
    assert call["service_name"] == "AdGroupService"
    ad_group = call["operations"][0].create
    assert ad_group.type_ == 13  # SEARCH_DYNAMIC_ADS
    assert ad_group.status == 3  # PAUSED


def test_add_webpage_target_builds_valid_criterion():
    call = _propose_and_execute(
        dynamic_search_ads,
        "add_webpage_target",
        campaign_id="123",
        conditions=[
            {"operand": "URL", "operator": "CONTAINS", "argument": "/hotel"},
            {"operand": "CUSTOM_LABEL", "operator": "EQUALS", "argument": "hotel_pages"},
        ],
        criterion_name="hotel pages",
        bid_modifier=1.2,
    )
    assert call["service_name"] == "CampaignCriterionService"
    criterion = call["operations"][0].create
    assert criterion.campaign == "customers/1111111111/campaigns/123"
    assert criterion.webpage.criterion_name == "hotel pages"
    assert len(criterion.webpage.conditions) == 2
    first, second = criterion.webpage.conditions
    assert first.operand == 2 and first.operator == 3 and first.argument == "/hotel"
    assert second.operand == 6 and second.operator == 2
    assert criterion.bid_modifier == pytest.approx(1.2)


def test_upload_call_conversion_builds_valid_v25_message():
    client = _CaptureClient(
        search_rows=[
            {
                "conversion_action": {
                    "id": 555,
                    "type": "UPLOAD_CALLS",
                    "status": "ENABLED",
                }
            }
        ]
    )
    safety = _CapturingSafety()
    mcp = _FakeMcp()
    conversions.register(mcp, SimpleNamespace(client=client, safety=safety))
    captured = {}

    class _UploadService:
        def upload_call_conversions(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(partial_failure_error=None)

    client.raw._extra_services = {}
    # inject the fake upload service in place of the real one
    original_get_service = client.raw.get_service

    def get_service(name):
        if name == "ConversionUploadService":
            return _UploadService()
        return original_get_service(name)

    client.raw.get_service = get_service

    response = mcp.tools["upload_call_conversion"](
        customer_id="111-111-1111",
        conversion_action_id="555",
        caller_id="+5491112345678",
        call_start_date_time="2026-08-20 15:30:00+00:00",
        conversion_date_time="2026-08-20 15:35:00+00:00",
        conversion_value=12.5,
        currency_code="USD",
        consent="GRANTED",
    )
    assert response["status"] == "pending_confirmation"
    safety.last["execute"]()

    assert captured["customer_id"] == "1111111111"
    assert captured["partial_failure"] is True
    (call_conversion,) = captured["conversions"]
    assert call_conversion.conversion_action == (
        "customers/1111111111/conversionActions/555"
    )
    assert call_conversion.caller_id == "5491112345678"  # "+" stripped
    assert call_conversion.call_start_date_time == "2026-08-20 15:30:00+00:00"
    assert call_conversion.conversion_value == 12.5
    assert call_conversion.currency_code == "USD"
    assert call_conversion.consent.ad_user_data == 2  # ConsentStatus GRANTED
    assert call_conversion.consent.ad_personalization == 2  # ConsentStatus GRANTED
