"""v25 contract tests for the 0.16.6 expert-scope-2 tools.

Builds real v25 protobuf messages through the real GoogleAdsClient and
asserts exact fields, enum values and update masks.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from google.ads.googleads.client import GoogleAdsClient
from google.oauth2.credentials import Credentials

from google_ads_mcp.tools import assets_extended, campaigns, conversions, targeting


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
        customer_id = self.assert_customer_allowed(customer_id)
        self.last_mutate = {
            "service_name": service_name,
            "customer_id": customer_id,
            "operations": list(operations),
            "partial_failure": partial_failure,
            "validate_only": validate_only,
        }
        return SimpleNamespace(results=[])

    def mutate_atomic(
        self,
        customer_id: str,
        operations,
        *,
        validate_only: bool = False,
    ):
        customer_id = self.assert_customer_allowed(customer_id)
        self.last_mutate = {
            "service_name": "GoogleAdsService",
            "customer_id": customer_id,
            "operations": list(operations),
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


def test_frequency_caps_build_valid_entries_and_mask():
    call = _propose_and_execute(
        campaigns,
        "set_campaign_frequency_caps",
        campaign_id="123",
        caps=[
            {
                "level": "CAMPAIGN",
                "event_type": "IMPRESSION",
                "time_unit": "DAY",
                "time_length": 1,
                "cap": 4,
            }
        ],
    )
    assert call["service_name"] == "CampaignService"
    op = call["operations"][0]
    assert op.update.resource_name == "customers/1111111111/campaigns/123"
    assert len(op.update.frequency_caps) == 1
    entry = op.update.frequency_caps[0]
    assert entry.key.level == 4  # CAMPAIGN
    assert entry.key.event_type == 2  # IMPRESSION
    assert entry.key.time_unit == 2  # DAY
    assert entry.key.time_length == 1
    assert entry.cap == 4
    assert op.update_mask.paths == ["frequency_caps"]


def test_add_placement_target_builds_positive_placement_criterion():
    call = _propose_and_execute(
        targeting,
        "add_placement_target",
        campaign_id="123",
        placement_url="example.com",
        placement_type="WEBSITE",
        bid_modifier=1.2,
    )
    assert call["service_name"] == "CampaignCriterionService"
    criterion = call["operations"][0].create
    assert criterion.campaign == "customers/1111111111/campaigns/123"
    assert criterion.negative is False
    assert criterion.placement.url == "example.com"
    assert criterion.bid_modifier == pytest.approx(1.2)


def test_add_placement_target_youtube_channel():
    call = _propose_and_execute(
        targeting,
        "add_placement_target",
        campaign_id="123",
        placement_url="UCabc123",
        placement_type="YOUTUBE_CHANNEL",
    )
    criterion = call["operations"][0].create
    assert criterion.youtube_channel.channel_id == "UCabc123"
    assert criterion.negative is False


def test_exclude_audience_from_ad_group_uses_modern_audience():
    call = _propose_and_execute(
        targeting,
        "exclude_audience_from_ad_group",
        ad_group_id="456",
        audience_resource_name="customers/1111111111/audiences/88",
    )
    assert call["service_name"] == "AdGroupCriterionService"
    criterion = call["operations"][0].create
    assert criterion.negative is True
    assert criterion.audience.audience == "customers/1111111111/audiences/88"


def test_exclude_audience_from_ad_group_user_list():
    call = _propose_and_execute(
        targeting,
        "exclude_audience_from_ad_group",
        ad_group_id="456",
        audience_resource_name="customers/1111111111/userLists/99",
    )
    criterion = call["operations"][0].create
    assert criterion.negative is True
    assert criterion.user_list.user_list == "customers/1111111111/userLists/99"


def test_exclude_audience_from_campaign_user_list():
    call = _propose_and_execute(
        targeting,
        "exclude_audience_from_campaign",
        campaign_id="123",
        audience_resource_name="customers/1111111111/userLists/99",
    )
    assert call["service_name"] == "CampaignCriterionService"
    criterion = call["operations"][0].create
    assert criterion.negative is True
    assert criterion.user_list.user_list == "customers/1111111111/userLists/99"


def test_exclude_audience_from_campaign_rejects_modern_audience():
    client = _CaptureClient()
    safety = _CapturingSafety()
    mcp = _FakeMcp()
    targeting.register(mcp, SimpleNamespace(client=client, safety=safety))

    with pytest.raises(ValueError, match="ad-group level"):
        mcp.tools["exclude_audience_from_campaign"](
            customer_id="111-111-1111",
            campaign_id="123",
            audience_resource_name="customers/1111111111/audiences/88",
        )


def test_upload_call_conversion_attaches_custom_variables():
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
        custom_variables=[{"name": "customer_id", "value": "1234"}],
    )
    assert response["status"] == "pending_confirmation"
    safety.last["execute"]()

    (call_conversion,) = captured["conversions"]
    assert len(call_conversion.custom_variables) == 1
    variable = call_conversion.custom_variables[0]
    assert variable.conversion_custom_variable == "customer_id"
    assert variable.value == "1234"


def test_upload_offline_conversion_attaches_custom_variables():
    client = _CaptureClient(
        search_rows=[
            {
                "conversion_action": {
                    "id": 777,
                    "type": "UPLOAD_CLICKS",
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
        def upload_click_conversions(self, **kwargs):
            captured.update(kwargs)
            return SimpleNamespace(partial_failure_error=None)

    original_get_service = client.raw.get_service

    def get_service(name):
        if name == "ConversionUploadService":
            return _UploadService()
        return original_get_service(name)

    client.raw.get_service = get_service

    response = mcp.tools["upload_offline_conversion"](
        customer_id="111-111-1111",
        conversion_action_id="777",
        gclid="abc123",
        conversion_date_time="2026-08-20 15:30:00+00:00",
        conversion_value=10.0,
        custom_variables=[{"name": "lead_source", "value": "web"}],
    )
    assert response["status"] == "pending_confirmation"
    safety.last["execute"]()

    (click_conversion,) = captured["conversions"]
    assert len(click_conversion.custom_variables) == 1
    assert click_conversion.custom_variables[0].conversion_custom_variable == "lead_source"
    assert click_conversion.custom_variables[0].value == "web"


def test_create_lead_form_asset_builds_real_v25_message():
    call = _propose_and_execute(
        assets_extended,
        "create_lead_form_asset",
        campaign_id="123",
        business_name="Instituto",
        headline="Headline",
        description="Desc",
        call_to_action_type="CONTACT_US",
        privacy_policy_url="https://example.com/privacy",
        fields=[
            {"input_type": "EMAIL"},
            {"input_type": "PRODUCT", "single_choice_answers": ["A", "B"]},
        ],
        webhook_url="https://example.com/hook",
    )
    assert call["service_name"] == "GoogleAdsService"
    assert len(call["operations"]) == 2
    asset = call["operations"][0].asset_operation.create
    lead = asset.lead_form_asset
    assert lead.business_name == "Instituto"
    assert lead.call_to_action_type == 6  # CONTACT_US
    assert lead.desired_intent == 3  # HIGH_INTENT
    assert len(lead.fields) == 2
    assert lead.fields[0].input_type == 3  # EMAIL
    assert list(lead.fields[1].single_choice_answers.answers) == ["A", "B"]
    assert (
        lead.delivery_methods[0].webhook.advertiser_webhook_url
        == "https://example.com/hook"
    )
    link = call["operations"][1].campaign_asset_operation.create
    assert link.campaign == "customers/1111111111/campaigns/123"
    assert link.field_type == 9  # LEAD_FORM (AssetFieldType)


def test_create_price_asset_builds_real_v25_message():
    call = _propose_and_execute(
        assets_extended,
        "create_price_asset",
        campaign_id="123",
        price_type="SERVICES",
        language_code="es",
        offerings=[
            {
                "header": "Curso básico",
                "description": "4 semanas",
                "price": "50",
                "unit": "PER_MONTH",
                "final_url": "https://example.com/basico",
            }
        ],
    )
    price = call["operations"][0].asset_operation.create.price_asset
    assert price.type_ == 8  # SERVICES
    assert price.language_code == "es"
    assert price.price_qualifier == 2  # FROM
    offering = price.price_offerings[0]
    assert offering.header == "Curso básico"
    assert offering.price.amount_micros == 50000000  # 50 USD
    assert offering.price.currency_code == "USD"
    assert offering.unit == 5  # PER_MONTH
    assert offering.final_url == "https://example.com/basico"


def test_create_location_asset_builds_real_v25_message():
    call = _propose_and_execute(
        assets_extended,
        "create_location_asset",
        place_id="ChIJN1t_tDeuEmsRUsoyG83frY4",
    )
    assert call["service_name"] == "AssetService"
    assert len(call["operations"]) == 1
    asset = call["operations"][0].create
    assert asset.location_asset.place_id == "ChIJN1t_tDeuEmsRUsoyG83frY4"


def test_create_app_deep_link_asset_builds_real_v25_message():
    call = _propose_and_execute(
        assets_extended,
        "create_app_deep_link_asset",
        app_deep_link_uri="app://open",
    )
    assert call["service_name"] == "AssetService"
    asset = call["operations"][0].create
    assert asset.app_deep_link_asset.app_deep_link_uri == "app://open"


def test_create_mobile_app_asset_builds_real_v25_message():
    call = _propose_and_execute(
        assets_extended,
        "create_mobile_app_asset",
        campaign_id="123",
        app_id="com.example.app",
        app_store="GOOGLE_APP_STORE",
        link_text="Descargá",
    )
    mobile = call["operations"][0].asset_operation.create.mobile_app_asset
    assert mobile.app_id == "com.example.app"
    assert mobile.app_store == 3  # GOOGLE_APP_STORE
    assert mobile.link_text == "Descargá"
    link = call["operations"][1].campaign_asset_operation.create
    assert link.field_type == 14  # MOBILE_APP (AssetFieldType)
