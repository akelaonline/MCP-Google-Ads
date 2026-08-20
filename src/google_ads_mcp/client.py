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

    def assert_resource_name_customer(
        self,
        customer_id: str,
        resource_name: str,
        *,
        field_name: str = "resource_name",
    ) -> str:
        """Require a customer-scoped resource name to belong to ``customer_id``."""
        customer = self.assert_customer_allowed(customer_id)
        value = str(resource_name).strip()
        owner = _customer_id_from_resource_name(value)
        if owner is None:
            raise GoogleAdsMcpError(
                f"{field_name} must be a customer-scoped Google Ads resource name "
                "starting with 'customers/{customer_id}/'."
            )
        if owner != customer:
            raise GoogleAdsMcpError(
                f"{field_name} belongs to customer {owner}, but this request targets "
                f"customer {customer}. Cross-customer mutation was blocked before "
                "contacting Google Ads."
            )
        return value

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
        """Run GAQL and enforce deployment scope on MCC hierarchy/link rows.

        Checking only the request customer is insufficient when the request customer
        is an MCC: ``customer_client`` and ``customer_client_link`` can describe
        other child customers. When a deployment allowlist is configured, those
        rows are filtered by the referenced child customer before they are returned.
        Raw hierarchy queries that omit the ownership field required for filtering
        fail closed rather than leaking cross-client metadata.
        """
        from google.ads.googleads.errors import GoogleAdsException

        customer_id = self.assert_customer_allowed(customer_id)
        ga_service = self.service("GoogleAdsService")
        try:
            stream = ga_service.search_stream(customer_id=customer_id, query=query)
            rows: list[dict[str, Any]] = []
            for batch in stream:
                for row in batch.results:
                    rows.append(_row_to_dict(row))
            return self._filter_allowed_hierarchy_rows(query, rows)
        except GoogleAdsException as ex:
            raise GoogleAdsMcpError(format_google_ads_exception(ex)) from ex

    def _filter_allowed_hierarchy_rows(
        self, query: str, rows: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        """Filter MCC child-account discovery/link rows to configured scope."""
        if not self._allowed_customer_ids or not rows:
            return rows

        source = _gaql_from_resource(query)
        if source == "customer_client":
            filtered: list[dict[str, Any]] = []
            for row in rows:
                data = row.get("customer_client") or {}
                raw_id = data.get("id")
                if raw_id is None:
                    raise GoogleAdsMcpError(
                        "A customer_client GAQL query in an allowlisted deployment must "
                        "select customer_client.id so cross-client rows can be filtered."
                    )
                child_id = normalize_customer_id(str(raw_id))
                if child_id in self._allowed_customer_ids:
                    filtered.append(row)
            return filtered

        if source == "customer_client_link":
            filtered = []
            for row in rows:
                data = row.get("customer_client_link") or {}
                client_resource = str(data.get("client_customer") or "").strip()
                child_id = _customer_id_from_resource_name(client_resource)
                if child_id is None:
                    raise GoogleAdsMcpError(
                        "A customer_client_link GAQL query in an allowlisted deployment "
                        "must select customer_client_link.client_customer so linked "
                        "customers can be filtered."
                    )
                if child_id in self._allowed_customer_ids:
                    filtered.append(row)
            return filtered

        return rows

    def mutate(
        self,
        service_name: str,
        customer_id: str,
        operations: Iterable[Any],
        *,
        operations_field: str = "operations",
        partial_failure: bool = False,
        validate_only: bool = False,
        allow_cross_customer_references: bool = False,
    ):
        """Execute a resource-specific mutate call with MCC isolation.

        Cross-customer references are rejected by default. The only implicit
        exception is a validated ``CustomerClientLinkService`` CREATE: that Google
        Ads operation necessarily references the client account from the manager
        request. Every referenced customer still has to pass this deployment's
        customer allowlist. Other intentional cross-account callers may opt in
        explicitly after validating their target customer.
        """
        import inspect

        from google.ads.googleads.errors import GoogleAdsException

        customer_id = self.assert_customer_allowed(customer_id)
        service = self.service(service_name)
        operation_list = list(operations)
        if service_name == "CampaignService":
            for operation in operation_list:
                _normalize_campaign_create(self.raw, operation)

        if allow_cross_customer_references:
            self._assert_all_cross_customer_references_allowed(
                customer_id, operation_list
            )
        elif service_name == "CustomerClientLinkService" and _all_operations_are_creates(
            operation_list
        ):
            self._assert_all_cross_customer_references_allowed(
                customer_id, operation_list
            )
        else:
            _assert_mutation_targets_customer(customer_id, operation_list)

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

        _assert_mutation_targets_customer(customer_id, operation_list)

        try:
            return service.mutate(
                customer_id=customer_id,
                mutate_operations=operation_list,
                partial_failure=False,
                validate_only=validate_only,
            )
        except GoogleAdsException as ex:
            raise GoogleAdsMcpError(format_google_ads_exception(ex)) from ex

    def _assert_all_cross_customer_references_allowed(
        self, customer_id: str, operations: Iterable[Any]
    ) -> None:
        """Validate every customer-scoped reference while permitting link intent."""
        request_customer = normalize_customer_id(customer_id)
        for operation in operations:
            for resource_name in _customer_scoped_resource_names(operation):
                owner = _customer_id_from_resource_name(resource_name)
                if owner is None or owner == request_customer:
                    continue
                self.assert_customer_allowed(owner)


_IRREGULAR_MUTATE_METHODS: dict[str, str] = {
    "AdGroupCriterionService": "mutate_ad_group_criteria",
    "AssetGroupCriterionService": "mutate_asset_group_criteria",
    "CampaignCriterionService": "mutate_campaign_criteria",
    "CustomerNegativeCriterionService": "mutate_customer_negative_criteria",
    "SharedCriterionService": "mutate_shared_criteria",
    "AccountBudgetProposalService": "mutate_account_budget_proposal",
    "BillingSetupService": "mutate_billing_setup",
    "CustomerClientLinkService": "mutate_customer_client_link",
    "CustomerUserAccessInvitationService": "mutate_customer_user_access_invitation",
    "CustomerUserAccessService": "mutate_customer_user_access",
    "CustomerSkAdNetworkConversionValueSchemaService": "mutate_customer_sk_ad_network_conversion_value_schema",
}


def _mutate_method_name(service_name: str) -> str:
    if service_name in _IRREGULAR_MUTATE_METHODS:
        return _IRREGULAR_MUTATE_METHODS[service_name]

    import re

    base = service_name.removesuffix("Service")
    snake = re.sub(r"(?<!^)(?=[A-Z])", "_", base).lower()
    return f"mutate_{snake}s"


def _customer_id_from_resource_name(resource_name: str) -> str | None:
    import re

    match = re.match(r"^customers/(\d+)(?:/|$)", str(resource_name).strip())
    return match.group(1) if match else None


def _gaql_from_resource(query: str) -> str | None:
    """Extract the top-level GAQL FROM resource name without parsing all GAQL."""
    import re

    match = re.search(r"\bFROM\s+([A-Za-z0-9_]+)\b", str(query), re.IGNORECASE)
    return match.group(1).lower() if match else None


def _customer_scoped_resource_names(message: Any) -> list[str]:
    """Recursively collect populated customer-scoped resource references."""
    pb = getattr(message, "_pb", message)
    list_fields = getattr(pb, "ListFields", None)
    if list_fields is None:
        return []
    try:
        from google.protobuf.descriptor import FieldDescriptor
    except Exception:
        return []
    found: list[str] = []
    try:
        fields = list_fields()
    except Exception:
        return []
    for descriptor, value in fields:
        if descriptor.type == FieldDescriptor.TYPE_MESSAGE:
            if descriptor.is_repeated:
                for item in value:
                    found.extend(_customer_scoped_resource_names(item))
            else:
                found.extend(_customer_scoped_resource_names(value))
            continue
        if descriptor.type != FieldDescriptor.TYPE_STRING:
            continue
        values = list(value) if descriptor.is_repeated else [value]
        for item in values:
            text = str(item).strip()
            if _customer_id_from_resource_name(text) is not None:
                found.append(text)
    return found


def _all_operations_are_creates(operations: Iterable[Any]) -> bool:
    operations = list(operations)
    if not operations:
        return False
    for operation in operations:
        pb = getattr(operation, "_pb", None)
        if pb is None:
            return False
        try:
            if pb.WhichOneof("operation") != "create":
                return False
        except (AttributeError, ValueError):
            return False
    return True


def _assert_mutation_targets_customer(
    customer_id: str,
    operations: Iterable[Any],
) -> None:
    """Block any mutation carrying a resource reference from another customer."""
    customer = normalize_customer_id(customer_id)
    mismatches: list[str] = []
    for operation in operations:
        for resource_name in _customer_scoped_resource_names(operation):
            owner = _customer_id_from_resource_name(resource_name)
            if owner is not None and owner != customer:
                mismatches.append(resource_name)
    if mismatches:
        unique = list(dict.fromkeys(mismatches))
        preview = ", ".join(unique[:3])
        if len(unique) > 3:
            preview += f", ... (+{len(unique) - 3} more)"
        raise GoogleAdsMcpError(
            f"Cross-customer mutation blocked: request targets customer {customer}, "
            f"but operation reference(s) belong to another customer: {preview}"
        )


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
    import proto

    return proto.Message.to_dict(row, preserving_proto_field_name=True)


def micros(amount: float) -> int:
    """Convert a currency amount (e.g. 25.50) to micros (25500000)."""
    return round(amount * 1_000_000)
