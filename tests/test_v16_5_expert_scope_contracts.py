"""v25 contract tests for the 0.16.5 expert-scope tools.

Builds real v25 protobuf messages through the real GoogleAdsClient and
asserts exact fields, update masks and enum values.
"""

from __future__ import annotations

from types import SimpleNamespace

from google.ads.googleads.client import GoogleAdsClient
from google.oauth2.credentials import Credentials

from google_ads_mcp.tools import campaigns, conversions, shopping_listing_groups


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


def test_upload_offline_conversion_writes_consent_message():
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
        consent="GRANTED",
    )
    assert response["status"] == "pending_confirmation"
    safety.last["execute"]()

    (click_conversion,) = captured["conversions"]
    assert click_conversion.consent.ad_user_data == 2  # ConsentStatus GRANTED
    assert click_conversion.consent.ad_personalization == 2


def test_set_campaign_ad_rotation_builds_valid_update_mask():
    call = _propose_and_execute(
        campaigns,
        "set_campaign_ad_rotation",
        campaign_id="123",
        rotation="ROTATE_INDEFINITELY",
    )
    assert call["service_name"] == "CampaignService"
    op = call["operations"][0]
    assert op.update.resource_name == "customers/1111111111/campaigns/123"
    assert op.update.ad_serving_optimization_status == 5  # ROTATE_INDEFINITELY
    assert op.update_mask.paths == ["ad_serving_optimization_status"]


def test_add_root_subdivision_builds_valid_criterion():
    call = _propose_and_execute(
        shopping_listing_groups,
        "add_shopping_listing_group",
        ad_group_id="456",
        listing_group_type="SUBDIVISION",
    )
    assert call["service_name"] == "AdGroupCriterionService"
    criterion = call["operations"][0].create
    assert criterion.ad_group == "customers/1111111111/adGroups/456"
    assert criterion.listing_group.type_ == 2  # SUBDIVISION
    assert criterion.listing_group.case_value == criterion.listing_group.case_value
    assert criterion.status == 2  # ENABLED


def test_add_unit_with_brand_dimension_builds_case_value():
    call = _propose_and_execute(
        shopping_listing_groups,
        "add_shopping_listing_group",
        ad_group_id="456",
        listing_group_type="UNIT",
        dimension={"type": "PRODUCT_BRAND", "value": "Nike"},
        parent_criterion_id="789",
        bid_modifier=1.5,
    )
    criterion = call["operations"][0].create
    assert criterion.listing_group.type_ == 3  # UNIT
    assert criterion.listing_group.parent_ad_group_criterion == (
        "customers/1111111111/adGroupCriteria/456~789"
    )
    assert criterion.listing_group.case_value.product_brand.value == "Nike"
    assert criterion.bid_modifier == 1.5


def test_add_unit_with_category_dimension_builds_case_value():
    call = _propose_and_execute(
        shopping_listing_groups,
        "add_shopping_listing_group",
        ad_group_id="456",
        listing_group_type="UNIT",
        dimension={"type": "PRODUCT_CATEGORY", "level": "LEVEL1", "category_id": 6469},
    )
    case_value = call["operations"][0].create.listing_group.case_value
    assert case_value.product_category.category_id == 6469
    assert case_value.product_category.level == 2  # LEVEL1


def test_add_unit_with_condition_dimension_builds_case_value():
    call = _propose_and_execute(
        shopping_listing_groups,
        "add_shopping_listing_group",
        ad_group_id="456",
        listing_group_type="UNIT",
        dimension={"type": "PRODUCT_CONDITION", "value": "NEW"},
    )
    case_value = call["operations"][0].create.listing_group.case_value
    assert case_value.product_condition.condition == 3  # ProductCondition.NEW


def test_update_listing_group_builds_valid_update_mask():
    call = _propose_and_execute(
        shopping_listing_groups,
        "update_shopping_listing_group",
        ad_group_id="456",
        criterion_id="789",
        bid_modifier=0.8,
        status="PAUSED",
    )
    op = call["operations"][0]
    assert op.update.resource_name == "customers/1111111111/adGroupCriteria/456~789"
    assert op.update.bid_modifier == 0.8
    assert op.update.status == 3  # PAUSED
    assert sorted(op.update_mask.paths) == ["bid_modifier", "status"]


def test_remove_listing_group_builds_remove_operation():
    call = _propose_and_execute(
        shopping_listing_groups,
        "remove_shopping_listing_group",
        ad_group_id="456",
        criterion_id="789",
    )
    op = call["operations"][0]
    assert op.remove == "customers/1111111111/adGroupCriteria/456~789"
