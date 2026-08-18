"""Thin wrapper around google.ads.googleads.client.GoogleAdsClient.

Centralizes client construction, GAQL search, and mutate execution so every
tool module shares the same API version and error handling.
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

    # ---- Reporting -----------------------------------------------------

    def search(self, customer_id: str, query: str) -> list[dict[str, Any]]:
        """Run a GAQL query, returning a list of flattened dicts."""
        from google.ads.googleads.errors import GoogleAdsException

        ga_service = self.service("GoogleAdsService")
        customer_id = normalize_customer_id(customer_id)

        try:
            stream = ga_service.search_stream(customer_id=customer_id, query=query)
            rows: list[dict[str, Any]] = []
            for batch in stream:
                for row in batch.results:
                    rows.append(_row_to_dict(row))
            return rows
        except GoogleAdsException as ex:
            raise GoogleAdsMcpError(format_google_ads_exception(ex)) from ex

    # ---- Mutations -----------------------------------------------------

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

        service = self.service(service_name)
        customer_id = normalize_customer_id(customer_id)
        method_name = _mutate_method_name(service_name)
        method = getattr(service, method_name, None)
        if method is None:
            raise GoogleAdsMcpError(
                f"{service_name} has no '{method_name}' method. This is a bug in "
                f"_mutate_method_name's pluralization for this service — check "
                f"_IRREGULAR_MUTATE_METHODS in client.py."
            )

        kwargs: dict[str, Any] = {
            "customer_id": customer_id,
            operations_field: list(operations),
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
        """Execute cross-resource operations atomically via GoogleAdsService.Mutate.

        This is the correct path for workflows that create one resource and link
        it to another in the same logical action. ``partial_failure`` is always
        false so either the whole transaction succeeds or none of it does.
        """
        from google.ads.googleads.errors import GoogleAdsException

        service = self.service("GoogleAdsService")
        customer_id = normalize_customer_id(customer_id)
        try:
            return service.mutate(
                customer_id=customer_id,
                mutate_operations=list(mutate_operations),
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
}


def _mutate_method_name(service_name: str) -> str:
    if service_name in _IRREGULAR_MUTATE_METHODS:
        return _IRREGULAR_MUTATE_METHODS[service_name]

    import re

    base = service_name.removesuffix("Service")
    snake = re.sub(r"(?<!^)(?=[A-Z])", "_", base).lower()
    return f"mutate_{snake}s"


def _row_to_dict(row) -> dict[str, Any]:
    """Flatten a GoogleAdsRow (proto-plus) into a plain nested dict."""
    import proto

    return proto.Message.to_dict(row, preserving_proto_field_name=True)


def micros(amount: float) -> int:
    """Convert a currency amount (e.g. 25.50) to micros (25500000)."""
    return round(amount * 1_000_000)


def from_micros(amount_micros: int) -> float:
    return amount_micros / 1_000_000
