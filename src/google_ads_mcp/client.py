"""Thin wrapper around google.ads.googleads.client.GoogleAdsClient.

Centralizes client construction, GAQL search, and mutate execution so
every tool module shares the same retry/error handling.
"""

from __future__ import annotations

from typing import Any, Iterable

from .config import Settings
from .errors import GoogleAdsMcpError, format_google_ads_exception

_API_VERSION = "v20"


def _normalize_customer_id(customer_id: str) -> str:
    return customer_id.replace("-", "").strip()


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
                self._settings.google_ads_yaml_dict, version=_API_VERSION
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
        customer_id = _normalize_customer_id(customer_id)

        try:
            stream = ga_service.search_stream(customer_id=customer_id, query=query)
            rows: list[dict[str, Any]] = []
            for batch in stream:
                for row in batch.results:
                    rows.append(_row_to_dict(row))
            return rows
        except GoogleAdsException as ex:
            raise GoogleAdsMcpError(format_google_ads_exception(ex)) from ex

    # ---- Mutations -------------------------------------------------------

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
        """Execute a mutate call. Callers build the typed operation(s) first."""
        from google.ads.googleads.errors import GoogleAdsException

        service = self.service(service_name)
        customer_id = _normalize_customer_id(customer_id)
        kwargs = {
            "customer_id": customer_id,
            operations_field: list(operations),
            "partial_failure": partial_failure,
            "validate_only": validate_only,
        }
        try:
            method = getattr(service, _mutate_method_name(service_name))
            return method(**kwargs)
        except GoogleAdsException as ex:
            raise GoogleAdsMcpError(format_google_ads_exception(ex)) from ex


def _mutate_method_name(service_name: str) -> str:
    # e.g. "CampaignService" -> "mutate_campaigns"
    # e.g. "CampaignBudgetService" -> "mutate_campaign_budgets"
    import re

    base = service_name[: -len("Service")] if service_name.endswith("Service") else service_name
    snake = re.sub(r"(?<!^)(?=[A-Z])", "_", base).lower()
    return f"mutate_{snake}s"


def _row_to_dict(row) -> dict[str, Any]:
    """Flatten a GoogleAdsRow (proto-plus) into a plain nested dict."""
    import proto

    return proto.Message.to_dict(row, preserving_proto_field_name=True)


def micros(amount: float) -> int:
    """Convert a currency amount (e.g. 25.50) to micros (25500000)."""
    return int(round(amount * 1_000_000))


def from_micros(amount_micros: int) -> float:
    return amount_micros / 1_000_000
