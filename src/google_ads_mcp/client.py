"""Thin wrapper around google.ads.googleads.client.GoogleAdsClient.

Centralizes client construction, GAQL search, compatibility normalization,
customer isolation, and mutate execution so every tool module shares the same
API version and production access policy.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from .config import Settings
from .errors import GoogleAdsMcpError, format_google_ads_exception
from .helpers import normalize_customer_id

GOOGLE_ADS_API_VERSION = "v25"


class GoogleAdsClientWrapper:
    """Lazily builds and caches the underlying GoogleAdsClient."""

    def __init__(self, settings: Settings):
        self._settings = settings
        self._client = None
        configured_ids = getattr(settings, "allowed_customer_ids", frozenset())
        self._allowed_customer_ids = frozenset(
            normalize_customer_id(customer_id) for customer_id in configured_ids
        )
        self._require_customer_allowlist = getattr(
            settings, "require_customer_allowlist", False
        )
        if self._require_customer_allowlist and not self._allowed_customer_ids:
            raise GoogleAdsMcpError(
                "Customer allowlist is required but empty. Configure "
                "GOOGLE_ADS_MCP_ALLOWED_CUSTOMER_IDS before starting the MCP."
            )

    @property
    def raw(self):
        if self._client is None:
            from google.ads.googleads.client import GoogleAdsClient

            self._client = GoogleAdsClient.load_from_dict(
                self._settings.google_ads_yaml_dict,
                version=GOOGLE_ADS_API_VERSION,
            )
        return self._client

    def service(self, name: str):
        return self.raw.get_service(name)

    def get_type(self, name: str):
        return self.raw.get_type(name)

    def assert_customer_allowed(self, customer_id: str) -> str:
        """Normalize a customer ID and enforce optional deployment isolation."""
        normalized = normalize_customer_id(customer_id)
        if self._require_customer_allowlist and not self._allowed_customer_ids:
            raise GoogleAdsMcpError("Customer allowlist is required but empty.")
        if self._allowed_customer_ids and normalized not in self._allowed_customer_ids:
            raise GoogleAdsMcpError(
                f"Customer {normalized} is outside GOOGLE_ADS_MCP_ALLOWED_CUSTOMER_IDS. "
                "The request was blocked before contacting that Google Ads account."
            )
        return normalized

    def filter_allowed_customer_ids(self, customer_ids: Iterable[str]) -> list[str]:
        """Filter account-discovery results to this deployment's configured scope."""
        normalized = [normalize_customer_id(customer_id) for customer_id in customer_ids]
        if not self._allowed_customer_ids:
            if self._require_customer_allowlist:
                raise GoogleAdsMcpError("Customer allowlist is required but empty.")
            return normalized
        return [
            customer_id
            for customer_id in normalized
            if customer_id in self._allowed_customer_ids
        ]

    def search(self, customer_id: str, query: str) -> list[dict[str, Any]]:
        """Run a GAQL query, returning a list of flattened dicts."""
        from google.ads.googleads.errors import GoogleAdsException

        customer_id = self.assert_customer_allowed(customer_id)
        ga_service = self.service("GoogleAdsService")

        try:
            stream = ga_service.search_stream(customer_id=customer_id, query=query)
            rows: list[dict[str, Any]] = []
            for batch in stream:
                for row in batch.results:
                    rows.append(_row_to_dict(row))
            return rows
        except GoogleAdsException as ex:
            raise GoogleAdsMcpError(format_google_ads_exception(ex)) from ex

    def mutate(
        self,
        service_name: str,
        customer_id: str,
        operations: Iterable[Any],
        *,
        operations_field: str = "operations",
        partial_failure: bool = False,
        validate_only: bool = False,
    ):
        """Execute a resource-specific mutate call."""
        import inspect

        from google.ads.googleads.errors import GoogleAdsException

        customer_id = self.assert_customer_allowed(customer_id)
        service = self.service(service_name)
        operation_list = list(operations)
        if service_name == "CampaignService":
            for operation in operation_list:
                _normalize_campaign_create(self.raw, operation)

        method_name = _mutate_method_name(service_name)
        method = getattr(service, method_name, None)
        if method is None:
            raise GoogleAdsMcpError(
                f"{service_name} has no '{method_name}' method. This is a bug in "
                f"_mutate_method_name's pluralization for this service — check "
                f"_IRREGULAR_MUTATE_METHODS in client.py."
            )

        if operations_field == "operation":
            if len(operation_list) != 1:
                raise GoogleAdsMcpError(
                    f"{service_name}.{method_name} accepts exactly one operation; "
                    f"received {len(operation_list)}."
                )
            operation_value: Any = operation_list[0]
        else:
            operation_value = operation_list

        kwargs: dict[str, Any] = {
            "customer_id": customer_id,
            operations_field: operation_value,
        }
        try:
            accepted_params = set(inspect.signature(method).parameters)
        except (TypeError, ValueError):
            accepted_params = None

        if accepted_params is None or "partial_failure" in accepted_params:
            kwargs["partial_failure"] = partial_failure
        if accepted_params is None or "validate_only" in accepted_params:
            kwargs["validate_only"] = validate_only

        try:
            return method(**kwargs)
        except GoogleAdsException as ex:
            raise GoogleAdsMcpError(format_google_ads_exception(ex)) from ex

    def mutate_atomic(
        self,
        customer_id: str,
        mutate_operations: Iterable[Any],
        *,
        validate_only: bool = False,
    ):
        """Execute cross-resource operations atomically via GoogleAdsService.Mutate."""
        from google.ads.googleads.errors import GoogleAdsException

        customer_id = self.assert_customer_allowed(customer_id)
        service = self.service("GoogleAdsService")
        operation_list = list(mutate_operations)
        for operation in operation_list:
            campaign_operation = getattr(operation, "campaign_operation", None)
            if campaign_operation is not None:
                _normalize_campaign_create(self.raw, campaign_operation)
        try:
            return service.mutate(
                customer_id=customer_id,
                mutate_operations=operation_list,
                partial_failure=False,
                validate_only=validate_only,
            )
        except GoogleAdsException as ex:
            raise GoogleAdsMcpError(format_google_ads_exception(ex)) from ex


_IRREGULAR_MUTATE_METHODS: dict[str, str] = {
    "AdGroupCriterionService": "mutate_ad_group_criteria",
    "AssetGroupCriterionService": "mutate_asset_group_criteria",
    "CampaignCriterionService": "mutate_campaign_criteria",
    "CustomerNegativeCriterionService": "mutate_customer_negative_criteria",
    "SharedCriterionService": "mutate_shared_criteria",
    "CustomerUserAccessInvitationService": "mutate_customer_user_access_invitation",
    "CustomerUserAccessService": "mutate_customer_user_access",
}


def _mutate_method_name(service_name: str) -> str:
    if service_name in _IRREGULAR_MUTATE_METHODS:
        return _IRREGULAR_MUTATE_METHODS[service_name]

    import re

    base = service_name.removesuffix("Service")
    snake = re.sub(r"(?<!^)(?=[A-Z])", "_", base).lower()
    return f"mutate_{snake}s"


def _normalize_campaign_create(client, operation) -> None:
    """Apply v25-required fields and repair legacy PMax bidding shapes."""
    pb = getattr(operation, "_pb", None)
    if pb is None or pb.WhichOneof("operation") != "create":
        return

    campaign = operation.create
    campaign_pb = getattr(campaign, "_pb", None)

    political_value = getattr(campaign, "contains_eu_political_advertising", 0)
    if not political_value:
        campaign.contains_eu_political_advertising = (
            client.enums.EuPoliticalAdvertisingStatusEnum.DOES_NOT_CONTAIN_EU_POLITICAL_ADVERTISING
        )

    if (
        campaign.advertising_channel_type
        != client.enums.AdvertisingChannelTypeEnum.PERFORMANCE_MAX
    ):
        return

    if campaign_pb is not None and campaign_pb.HasField("target_cpa"):
        target_cpa_micros = campaign.target_cpa.target_cpa_micros
        campaign_pb.ClearField("target_cpa")
        campaign.maximize_conversions.target_cpa_micros = target_cpa_micros
    elif campaign_pb is not None and campaign_pb.HasField("target_roas"):
        target_roas = campaign.target_roas.target_roas
        campaign_pb.ClearField("target_roas")
        campaign.maximize_conversion_value.target_roas = target_roas


def _row_to_dict(row) -> dict[str, Any]:
    """Flatten a GoogleAdsRow (proto-plus) into a plain nested dict."""
    import proto

    return proto.Message.to_dict(row, preserving_proto_field_name=True)


def micros(amount: float) -> int:
    """Convert a currency amount (e.g. 25.50) to micros (25500000)."""
    return round(amount * 1_000_000)


def from_micros(amount_micros: int) -> float:
    return amount_micros / 1_000_000
