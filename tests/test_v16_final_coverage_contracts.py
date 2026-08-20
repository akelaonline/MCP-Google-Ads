"""Generated-client contract guardrails for the final v0.16 coverage surface."""

from __future__ import annotations

import pytest
from google.ads.googleads.client import GoogleAdsClient
from google.oauth2.credentials import Credentials

from google_ads_mcp.safety import RiskLevel, classify_risk


def _client() -> GoogleAdsClient:
    return GoogleAdsClient(
        credentials=Credentials(token="contract-token"),
        developer_token="contract-developer-token",
        version="v25",
        use_proto_plus=True,
    )


@pytest.mark.parametrize(
    ("service_name", "method_name"),
    [
        ("BrandSuggestionService", "suggest_brands"),
        ("IdentityVerificationService", "get_identity_verification"),
        ("IdentityVerificationService", "start_identity_verification"),
        (
            "CustomerSkAdNetworkConversionValueSchemaService",
            "mutate_customer_sk_ad_network_conversion_value_schema",
        ),
        ("UserDataService", "upload_user_data"),
        ("UserListCustomerTypeService", "mutate_user_list_customer_types"),
        ("RecommendationService", "generate_recommendations"),
        ("IncentiveService", "fetch_incentive"),
        ("IncentiveService", "apply_incentive"),
        ("ReachPlanService", "generate_conversion_rates"),
        ("ReachPlanService", "generate_reach_forecast"),
        ("ReachPlanService", "list_plannable_locations"),
        ("ReachPlanService", "list_plannable_products"),
        ("ReachPlanService", "list_plannable_user_interests"),
        ("ReachPlanService", "list_plannable_user_lists"),
    ],
)
def test_v16_final_service_rpc_exists(service_name: str, method_name: str):
    service = _client().get_service(service_name)
    assert hasattr(service, method_name), f"v25 {service_name}.{method_name} does not exist"


@pytest.mark.parametrize(
    "type_name",
    [
        "GetIdentityVerificationRequest",
        "StartIdentityVerificationRequest",
        "CustomerSkAdNetworkConversionValueSchemaOperation",
        "MutateCustomerSkAdNetworkConversionValueSchemaRequest",
        "UploadUserDataRequest",
        "UserDataOperation",
        "UserListCustomerTypeOperation",
        "SuggestBrandsRequest",
        "GenerateRecommendationsRequest",
        "FetchIncentiveRequest",
        "ApplyIncentiveRequest",
        "GenerateConversionRatesRequest",
        "GenerateReachForecastRequest",
        "ListPlannableLocationsRequest",
        "ListPlannableProductsRequest",
        "ListPlannableUserInterestsRequest",
        "ListPlannableUserListsRequest",
    ],
)
def test_v16_final_request_and_operation_types_exist(type_name: str):
    assert _client().get_type(type_name) is not None


def test_skadnetwork_v25_operation_is_singular_update():
    operation = _client().get_type("CustomerSkAdNetworkConversionValueSchemaOperation")
    operation.update.resource_name = (
        "customers/1234567890/customerSkAdNetworkConversionValueSchemas/99"
    )
    assert operation._pb.WhichOneof("operation") == "update"


def test_v16_new_mutations_are_not_standard_risk():
    assert (
        classify_risk("upload_customer_match_user_data_direct", {})
        is RiskLevel.SENSITIVE
    )
    assert (
        classify_risk("start_advertiser_identity_verification", {})
        is RiskLevel.SENSITIVE
    )
    assert (
        classify_risk("update_skadnetwork_conversion_schema", {})
        is RiskLevel.SENSITIVE
    )
    assert classify_risk("apply_incentive", {}) is RiskLevel.SENSITIVE
