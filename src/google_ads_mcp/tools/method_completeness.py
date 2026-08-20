"""Method/parameter-completeness helpers for Google Ads API v25."""

from __future__ import annotations

import proto
from google.protobuf import json_format

from ..client import _customer_id_from_resource_name, _customer_scoped_resource_names
from ..context import AppContext
from ..errors import GoogleAdsMcpError, format_google_ads_exception


def _call(service, method_name: str, **kwargs):
    from google.ads.googleads.errors import GoogleAdsException

    try:
        return getattr(service, method_name)(**kwargs)
    except GoogleAdsException as ex:
        raise GoogleAdsMcpError(format_google_ads_exception(ex)) from ex


def _assert_referenced_customers_allowed(ctx: AppContext, request_customer: str, message) -> None:
    """Permit intentional account-link references only inside deployment scope."""
    for resource in _customer_scoped_resource_names(message):
        owner = _customer_id_from_resource_name(resource)
        if owner is None or owner == request_customer:
            continue
        ctx.client.assert_customer_allowed(owner)


def register(mcp, ctx: AppContext) -> None:
    @mcp.tool()
    def create_product_link_invitation(
        customer_id: str,
        invitation: dict,
        validate_only: bool = False,
    ) -> dict:
        """Propose creating a ProductLinkInvitation using the complete v25 proto shape.

        ``invitation`` is protobuf JSON for ProductLinkInvitation. Google supports
        the invitation flow for eligible product types. Merchant Center is a
        documented exception: new Merchant Center link requests must originate in
        Merchant Center / Merchant API and can only be accepted/rejected here.

        For Advertising Partner invitations, v25 requires
        ``advertising_partner_properties.allowed_domain``. Any invited Google Ads
        customer must also be inside ``GOOGLE_ADS_MCP_ALLOWED_CUSTOMER_IDS`` when a
        deployment allowlist is configured.
        """
        customer = ctx.client.assert_customer_allowed(customer_id)
        if not isinstance(invitation, dict) or not invitation:
            raise ValueError(
                "invitation must be a non-empty ProductLinkInvitation protobuf-JSON object."
            )
        forbidden = {
            "resource_name",
            "product_link_invitation_id",
            "status",
            "type",
        } & set(invitation)
        if forbidden:
            raise ValueError(
                "Server/output fields cannot be supplied on invitation create: "
                + ", ".join(sorted(forbidden))
            )
        if "merchant_center" in invitation:
            raise ValueError(
                "Google Ads API v25 does not permit initiating new Merchant Center "
                "link requests from Google Ads. Create it in Merchant Center/Merchant "
                "API, then use accept_product_link_invitation here."
            )
        if "advertising_partner" in invitation:
            properties = invitation.get("advertising_partner_properties") or {}
            allowed_domain = str(properties.get("allowed_domain", "")).strip()
            if not allowed_domain:
                raise ValueError(
                    "Advertising Partner invitations require "
                    "advertising_partner_properties.allowed_domain in v25."
                )

        raw = ctx.client.raw
        link_invitation = raw.get_type("ProductLinkInvitation")
        try:
            json_format.ParseDict(
                invitation,
                link_invitation._pb,
                ignore_unknown_fields=False,
            )
        except Exception as ex:
            raise ValueError(f"Invalid ProductLinkInvitation payload: {ex}") from ex

        _assert_referenced_customers_allowed(ctx, customer, link_invitation)
        service = ctx.client.service("ProductLinkInvitationService")

        def execute():
            if validate_only:
                return {
                    "validated_locally": True,
                    "google_validate_only_supported": False,
                    "customer_id": customer,
                    "invitation": proto.Message.to_dict(
                        link_invitation, preserving_proto_field_name=True
                    ),
                }
            response = _call(
                service,
                "create_product_link_invitation",
                customer_id=customer,
                product_link_invitation=link_invitation,
            )
            return proto.Message.to_dict(response, preserving_proto_field_name=True)

        # Use the established sensitive ProductLink safety category. Invocation
        # tracking preserves this public MCP tool name separately for durable replay.
        return ctx.safety.propose(
            tool_name="create_product_link",
            customer_id=customer,
            description=f"Create ProductLinkInvitation from Google Ads customer {customer}",
            payload={
                "invitation": invitation,
                "validate_only": bool(validate_only),
            },
            execute=execute,
        )

    @mcp.tool()
    def fetch_google_ads_incentives_full(
        language_code: str = "en",
        country_code: str = "US",
        email: str | None = None,
        incentive_type: str = "ACQUISITION",
    ) -> dict:
        """Fetch allowlisted incentives with every public v25 FetchIncentive input.

        ``email`` is optional and is useful for channel partners not authenticating
        OAuth on behalf of the end user. This is read-only and the email is not
        written to the MCP mutation audit log.
        """
        language = str(language_code).strip().lower()
        country = str(country_code).strip().upper()
        if not language or len(language) > 16:
            raise ValueError("language_code must be a valid Google Ads language code.")
        if len(country) != 2 or not country.isalpha():
            raise ValueError("country_code must be a two-letter country code.")
        clean_email = str(email).strip() if email is not None else None
        if clean_email is not None and (
            clean_email.count("@") != 1 or len(clean_email) > 320
        ):
            raise ValueError("email must be a valid email address when supplied.")
        kind = str(incentive_type).strip().upper()

        raw = ctx.client.raw
        request = raw.get_type("FetchIncentiveRequest")
        request.language_code = language
        request.country_code = country
        if clean_email:
            request.email = clean_email
        try:
            request.incentive_type = getattr(raw.enums.IncentiveTypeEnum, kind)
        except AttributeError as ex:
            raise ValueError(f"Unknown IncentiveType: {kind}") from ex

        response = _call(
            ctx.client.service("IncentiveService"),
            "fetch_incentive",
            request=request,
        )
        return proto.Message.to_dict(response, preserving_proto_field_name=True)

    @mcp.tool()
    def list_customer_skad_network_conversion_value_schemas(
        customer_id: str,
    ) -> dict:
        """List SKAdNetwork schema resources visible through Google Ads API v25.

        The public v25 resource reference marks both ``resource_name`` and
        ``schema`` as output-only. The MCP therefore exposes read visibility but
        deliberately does not fabricate a generic schema writer for live accounts.
        """
        customer = ctx.client.assert_customer_allowed(customer_id)
        rows = ctx.client.search(
            customer,
            """
            SELECT customer_sk_ad_network_conversion_value_schema.resource_name,
                   customer_sk_ad_network_conversion_value_schema.schema
            FROM customer_sk_ad_network_conversion_value_schema
            ORDER BY customer_sk_ad_network_conversion_value_schema.resource_name
            """,
        )
        return {
            "schemas": rows,
            "count": len(rows),
            "mutation_surface": "not_exposed",
            "reason": (
                "Google Ads API v25 publishes a dedicated mutate RPC, but its public "
                "CustomerSkAdNetworkConversionValueSchema resource documents both "
                "resource_name and schema as output-only."
            ),
        }

    @mcp.tool()
    def get_customer_skad_network_schema_capability() -> dict:
        """Explain the conservative SKAdNetwork coverage used by this release."""
        return {
            "service": "CustomerSkAdNetworkConversionValueSchemaService",
            "api_version": "v25",
            "read_visibility": "supported_via_gaql",
            "public_rpc": "MutateCustomerSkAdNetworkConversionValueSchema",
            "mutation_surface": "not_exposed",
            "coverage_status": "specialized",
            "reason": (
                "The v25 public resource reference marks schema as output-only, so "
                "a dict-to-protobuf mutation would be an undocumented production "
                "capability."
            ),
        }
