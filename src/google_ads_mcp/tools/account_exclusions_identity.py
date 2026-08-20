"""Account-level exclusions, identity verification, and SKAd schema visibility for API v25."""

from __future__ import annotations

import proto
from google.protobuf import json_format

from ..context import AppContext
from ..errors import GoogleAdsMcpError, format_google_ads_exception

_NEGATIVE_CRITERIA = {
    "content_label",
    "mobile_application",
    "mobile_app_category",
    "placement",
    "youtube_video",
    "youtube_channel",
    "negative_keyword_list",
    "ip_block",
}


def _owned(ctx: AppContext, customer: str, resource: str, field_name: str) -> str:
    return ctx.client.assert_resource_name_customer(customer, resource, field_name=field_name)


def _call(service, method_name: str, **kwargs):
    from google.ads.googleads.errors import GoogleAdsException

    try:
        return getattr(service, method_name)(**kwargs)
    except GoogleAdsException as ex:
        raise GoogleAdsMcpError(format_google_ads_exception(ex)) from ex


def register(mcp, ctx: AppContext) -> None:
    @mcp.tool()
    def list_customer_negative_criteria(customer_id: str) -> dict:
        """List all account-level negative criteria applied across campaigns."""
        rows = ctx.client.search(
            customer_id,
            """
            SELECT customer_negative_criterion.resource_name,
                   customer_negative_criterion.id,
                   customer_negative_criterion.type,
                   customer_negative_criterion.content_label.type,
                   customer_negative_criterion.mobile_application.app_id,
                   customer_negative_criterion.mobile_app_category.mobile_app_category_constant,
                   customer_negative_criterion.placement.url,
                   customer_negative_criterion.youtube_video.video_id,
                   customer_negative_criterion.youtube_channel.channel_id,
                   customer_negative_criterion.negative_keyword_list.shared_set,
                   customer_negative_criterion.ip_block.ip_address
            FROM customer_negative_criterion
            ORDER BY customer_negative_criterion.id
            """,
        )
        return {"customer_negative_criteria": rows, "count": len(rows)}

    @mcp.tool()
    def add_customer_negative_criterion(
        customer_id: str,
        criterion: dict,
        validate_only: bool = False,
    ) -> dict:
        """Propose creating one account-level exclusion.

        ``criterion`` must contain exactly one supported protobuf-JSON criterion,
        for example ``{"placement": {"url": "example.com"}}`` or
        ``{"youtube_video": {"video_id": "abcdefghijk"}}``. Supported top-level
        keys: content_label, mobile_application, mobile_app_category, placement,
        youtube_video, youtube_channel, negative_keyword_list, ip_block.
        """
        customer = ctx.client.assert_customer_allowed(customer_id)
        if not isinstance(criterion, dict) or len(criterion) != 1:
            raise ValueError("criterion must contain exactly one exclusion type.")
        kind = next(iter(criterion))
        if kind not in _NEGATIVE_CRITERIA:
            raise ValueError(
                f"Unsupported criterion type {kind!r}; use one of {sorted(_NEGATIVE_CRITERIA)}."
            )
        raw = ctx.client.raw
        operation = raw.get_type("CustomerNegativeCriterionOperation")
        try:
            json_format.ParseDict(criterion, operation.create._pb, ignore_unknown_fields=False)
        except Exception as ex:
            raise ValueError(f"Invalid {kind} criterion payload: {ex}") from ex

        if kind == "negative_keyword_list":
            shared_set = getattr(operation.create.negative_keyword_list, "shared_set", "")
            if shared_set:
                _owned(
                    ctx,
                    customer,
                    shared_set,
                    "criterion.negative_keyword_list.shared_set",
                )

        def execute():
            return ctx.client.mutate(
                "CustomerNegativeCriterionService",
                customer,
                [operation],
                validate_only=validate_only,
            )

        return ctx.safety.propose(
            tool_name="add_customer_negative_criterion",
            customer_id=customer,
            description=f"Add account-level {kind} negative criterion",
            payload={"criterion": criterion, "validate_only": validate_only},
            execute=execute,
        )

    @mcp.tool()
    def remove_customer_negative_criterion(
        customer_id: str,
        customer_negative_criterion_resource_name: str,
        validate_only: bool = False,
    ) -> dict:
        """Propose removing an account-level negative criterion."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        resource = _owned(
            ctx,
            customer,
            customer_negative_criterion_resource_name,
            "customer_negative_criterion_resource_name",
        )
        operation = ctx.client.raw.get_type("CustomerNegativeCriterionOperation")
        operation.remove = resource

        def execute():
            return ctx.client.mutate(
                "CustomerNegativeCriterionService",
                customer,
                [operation],
                validate_only=validate_only,
            )

        return ctx.safety.propose(
            tool_name="remove_customer_negative_criterion",
            customer_id=customer,
            description=f"Remove account-level negative criterion {resource}",
            payload={"resource_name": resource, "validate_only": validate_only},
            execute=execute,
        )

    @mcp.tool()
    def get_identity_verification(customer_id: str) -> dict:
        """Retrieve advertiser identity-verification programs, status and deadlines."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        raw = ctx.client.raw
        request = raw.get_type("GetIdentityVerificationRequest")
        request.customer_id = customer
        response = _call(
            ctx.client.service("IdentityVerificationService"),
            "get_identity_verification",
            request=request,
        )
        return proto.Message.to_dict(response, preserving_proto_field_name=True)

    @mcp.tool()
    def start_identity_verification(
        customer_id: str,
        verification_program: str = "ADVERTISER_IDENTITY_VERIFICATION",
    ) -> dict:
        """Propose starting an advertiser identity-verification program."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        raw = ctx.client.raw
        program = verification_program.strip().upper()
        try:
            program_enum = getattr(raw.enums.IdentityVerificationProgramEnum, program)
        except AttributeError as ex:
            raise ValueError(f"Unknown IdentityVerificationProgram: {program}") from ex
        request = raw.get_type("StartIdentityVerificationRequest")
        request.customer_id = customer
        request.verification_program = program_enum

        def execute():
            _call(
                ctx.client.service("IdentityVerificationService"),
                "start_identity_verification",
                request=request,
            )
            return {
                "customer_id": customer,
                "verification_program": program,
                "started": True,
            }

        return ctx.safety.propose(
            tool_name="start_identity_verification",
            customer_id=customer,
            description=f"Start {program} for customer {customer}",
            payload={"verification_program": program},
            execute=execute,
        )

    @mcp.tool()
    def list_customer_skad_network_conversion_value_schemas(customer_id: str) -> dict:
        """List SKAdNetwork conversion-value schemas visible to the account.

        Google Ads API v25 documents the resource and nested schema fields as
        output-only. This tool is intentionally read-only; no generic SKAd schema
        writer is exposed by the MCP.
        """
        rows = ctx.client.search(
            customer_id,
            """
            SELECT customer_sk_ad_network_conversion_value_schema.resource_name,
                   customer_sk_ad_network_conversion_value_schema.schema.app_id,
                   customer_sk_ad_network_conversion_value_schema.schema.measurement_window_hours
            FROM customer_sk_ad_network_conversion_value_schema
            ORDER BY customer_sk_ad_network_conversion_value_schema.resource_name
            """,
        )
        return {
            "skad_network_conversion_value_schemas": rows,
            "count": len(rows),
            "mutation_surface": "not_exposed",
        }
