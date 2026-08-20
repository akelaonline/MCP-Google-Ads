"""SKAdNetwork conversion-value schema workflows for Google Ads API v25."""

from __future__ import annotations

from google.ads.googleads.errors import GoogleAdsException
from google.protobuf import json_format

from ..context import AppContext
from ..errors import GoogleAdsMcpError, format_google_ads_exception


def register(mcp, ctx: AppContext) -> None:
    @mcp.tool()
    def list_skadnetwork_conversion_schemas(customer_id: str) -> dict:
        """List SKAdNetwork conversion-value schema resources visible to a customer."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        rows = ctx.client.search(
            customer,
            """
            SELECT customer_sk_ad_network_conversion_value_schema.resource_name
            FROM customer_sk_ad_network_conversion_value_schema
            ORDER BY customer_sk_ad_network_conversion_value_schema.resource_name
            """,
        )
        return {"count": len(rows), "schemas": rows}

    @mcp.tool()
    def update_skadnetwork_conversion_schema(
        customer_id: str,
        resource_name: str,
        schema: dict,
        enable_warnings: bool = True,
        validate_only: bool = False,
    ) -> dict:
        """Propose replacing one CustomerSkAdNetworkConversionValueSchema.

        ``schema`` uses Google's documented v25 SkAdNetworkConversionValueSchema
        protobuf-JSON field names. Unknown fields are rejected locally. Google can
        return non-blocking warnings when ``enable_warnings`` is true.
        """
        customer = ctx.client.assert_customer_allowed(customer_id)
        resource = _resource(customer, resource_name)
        if not isinstance(schema, dict) or not schema:
            raise ValueError("schema must be a non-empty SKAdNetwork schema object.")

        raw = ctx.client.raw
        operation = raw.get_type("CustomerSkAdNetworkConversionValueSchemaOperation")
        operation.update.resource_name = resource
        try:
            json_format.ParseDict(
                schema,
                operation.update.schema._pb,
                ignore_unknown_fields=False,
            )
        except (json_format.ParseError, TypeError, ValueError) as ex:
            raise ValueError(f"Invalid SKAdNetwork schema payload: {ex}") from ex

        def execute():
            request = raw.get_type(
                "MutateCustomerSkAdNetworkConversionValueSchemaRequest"
            )
            request.customer_id = customer
            raw.copy_from(request.operation, operation)
            request.validate_only = bool(validate_only)
            request.enable_warnings = bool(enable_warnings)
            try:
                response = raw.get_service(
                    "CustomerSkAdNetworkConversionValueSchemaService"
                ).mutate_customer_sk_ad_network_conversion_value_schema(
                    request=request
                )
            except GoogleAdsException as ex:
                raise GoogleAdsMcpError(format_google_ads_exception(ex)) from ex

            result = getattr(response, "result", None)
            warning = getattr(response, "warning", None)
            return {
                "validated": bool(validate_only),
                "resource_name": getattr(result, "resource_name", resource),
                "app_id": getattr(result, "app_id", None),
                "warning": _warning(warning),
            }

        return ctx.safety.propose(
            tool_name="update_skadnetwork_conversion_schema",
            customer_id=customer,
            description=f"Update SKAdNetwork conversion schema {resource}",
            payload={
                "resource_name": resource,
                "schema": schema,
                "enable_warnings": bool(enable_warnings),
                "validate_only": bool(validate_only),
            },
            execute=execute,
        )


def _resource(customer_id: str, value: str) -> str:
    resource = value.strip()
    prefix = f"customers/{customer_id}/customerSkAdNetworkConversionValueSchemas/"
    suffix = resource[len(prefix) :] if resource.startswith(prefix) else ""
    if not suffix.isdigit() or int(suffix) <= 0:
        raise ValueError(
            "resource_name must match "
            f"'{prefix}{{account_link_id}}' with a positive numeric account link ID."
        )
    return resource


def _warning(value) -> dict | None:
    if value is None:
        return None
    try:
        payload = json_format.MessageToDict(
            value._pb,
            preserving_proto_field_name=True,
        )
        return payload or None
    except (AttributeError, TypeError, ValueError):
        text = str(value)
        return {"message": text} if text else None
