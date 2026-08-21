"""Google Ads API v25 AssetGenerationService wrappers (closed beta).

Google exposes GenerateText and GenerateImages in the public v25 protobuf
contract, but access remains controlled by Google. These tools use strict
protobuf-JSON parsing so newly allowed request fields can be used without this
MCP inventing a second schema. They never mutate the account; generated output
must be reviewed and attached separately through normal write tools.
"""

from __future__ import annotations

import proto
from google.protobuf import json_format

from ..context import AppContext
from ..errors import GoogleAdsMcpError, format_google_ads_exception


def _generate(ctx: AppContext, customer_id: str, request_type: str, method: str, payload: dict) -> dict:
    customer = ctx.client.assert_customer_allowed(customer_id)
    if not isinstance(payload, dict):
        raise TypeError("request must be a protobuf-JSON object.")
    if "customer_id" in payload or "customerId" in payload:
        raise ValueError("Do not put customer_id in request; use the customer_id tool argument.")

    raw = ctx.client.raw
    request = raw.get_type(request_type)
    try:
        json_format.ParseDict(payload, request._pb, ignore_unknown_fields=False)
    except Exception as ex:
        raise ValueError(f"Invalid {request_type} payload: {ex}") from ex
    request.customer_id = customer

    from google.ads.googleads.errors import GoogleAdsException

    try:
        response = getattr(ctx.client.service("AssetGenerationService"), method)(
            request=request
        )
    except GoogleAdsException as ex:
        raise GoogleAdsMcpError(format_google_ads_exception(ex)) from ex

    return proto.Message.to_dict(response, preserving_proto_field_name=True)


def register(mcp, ctx: AppContext) -> None:
    @mcp.tool()
    def generate_google_ads_text_assets(
        customer_id: str,
        request: dict,
    ) -> dict:
        """Generate text asset candidates through AssetGenerationService (closed beta).

        ``request`` uses the v25 ``GenerateTextRequest`` protobuf-JSON fields except
        customer_id, which is supplied separately and checked against deployment
        isolation. Google may return NOT_ALLOWLISTED for accounts without beta access.
        This tool is read/generation-only; it does not attach or publish assets.
        """
        return _generate(
            ctx,
            customer_id,
            "GenerateTextRequest",
            "generate_text",
            request,
        )

    @mcp.tool()
    def generate_google_ads_image_assets(
        customer_id: str,
        request: dict,
    ) -> dict:
        """Generate image asset candidates through AssetGenerationService (closed beta).

        ``request`` uses the v25 ``GenerateImagesRequest`` protobuf-JSON fields except
        customer_id. Google controls access to this closed-beta service. Generated
        images are returned for review and are not automatically attached to ads.
        """
        return _generate(
            ctx,
            customer_id,
            "GenerateImagesRequest",
            "generate_images",
            request,
        )
