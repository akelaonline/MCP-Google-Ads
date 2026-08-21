"""Tracking URL templates, final URL suffixes and custom URL parameters.

Covers the account/campaign/ad-group URL-option surfaces that Google Ads
operators use to inject tracking parameters into destination URLs. The v25
field is ``tracking_url_template``; older documentation called it
``tracking_template``.
"""

from __future__ import annotations

from google.protobuf import field_mask_pb2

from ..context import AppContext

_URL_FIELDS = ("tracking_url_template", "final_url_suffix", "url_custom_parameters")


def _validate_custom_parameters(url_custom_parameters) -> list[tuple[str, str]]:
    if url_custom_parameters is None:
        return []
    normalized: list[tuple[str, str]] = []
    for item in url_custom_parameters:
        key = str(item.get("key", "")).strip()
        value = str(item.get("value", ""))
        if not key:
            raise ValueError("Every url_custom_parameter needs a non-empty 'key'.")
        if "{" in key or "}" in key:
            raise ValueError(
                "Custom parameter keys cannot contain '{' or '}'; put "
                "tracking macros in the value instead."
            )
        normalized.append((key, value))
    return normalized


def _set_custom_parameters(client, target, normalized: list[tuple[str, str]]) -> None:
    for key, value in normalized:
        target.url_custom_parameters.append({"key": key, "value": value})


def register(mcp, ctx: AppContext) -> None:
    @mcp.tool()
    def set_campaign_tracking_url(
        customer_id: str,
        campaign_id: str,
        tracking_url_template: str | None = None,
        final_url_suffix: str | None = None,
        url_custom_parameters: list[dict] | None = None,
    ) -> dict:
        """Propose setting tracking URL options on a campaign.

        Only the fields provided are changed. Pass ``url_custom_parameters=[]``
        to clear all custom parameters. ``tracking_url_template`` supports
        Google Ads tracking macros such as ``{lpurl}?utm_source=...``.
        """
        if (
            tracking_url_template is None
            and final_url_suffix is None
            and url_custom_parameters is None
        ):
            raise ValueError(
                "Provide at least one of tracking_url_template, final_url_suffix, "
                "or url_custom_parameters."
            )
        normalized = _validate_custom_parameters(url_custom_parameters)

        client = ctx.client.raw
        operation = client.get_type("CampaignOperation")
        campaign = operation.update
        campaign.resource_name = client.get_service("CampaignService").campaign_path(
            customer_id.replace("-", ""), campaign_id
        )
        paths = []
        if tracking_url_template is not None:
            campaign.tracking_url_template = tracking_url_template
            paths.append("tracking_url_template")
        if final_url_suffix is not None:
            campaign.final_url_suffix = final_url_suffix
            paths.append("final_url_suffix")
        if url_custom_parameters is not None:
            _set_custom_parameters(client, campaign, normalized)
            paths.append("url_custom_parameters")
        operation.update_mask.CopyFrom(field_mask_pb2.FieldMask(paths=paths))

        description = f"Update tracking URL options on campaign {campaign_id}"

        def execute():
            return ctx.client.mutate("CampaignService", customer_id, [operation])

        return ctx.safety.propose(
            tool_name="set_campaign_tracking_url",
            customer_id=customer_id,
            description=description,
            payload={
                "campaign_id": campaign_id,
                "tracking_url_template": tracking_url_template,
                "final_url_suffix": final_url_suffix,
                "url_custom_parameters": (
                    [dict(item) for item in url_custom_parameters]
                    if url_custom_parameters is not None
                    else None
                ),
            },
            execute=execute,
        )

    @mcp.tool()
    def set_ad_group_tracking_url(
        customer_id: str,
        ad_group_id: str,
        tracking_url_template: str | None = None,
        final_url_suffix: str | None = None,
        url_custom_parameters: list[dict] | None = None,
    ) -> dict:
        """Propose setting tracking URL options on an ad group.

        Same semantics as ``set_campaign_tracking_url`` but scoped to one ad
        group; inherited campaign templates keep applying where not overridden.
        """
        if (
            tracking_url_template is None
            and final_url_suffix is None
            and url_custom_parameters is None
        ):
            raise ValueError(
                "Provide at least one of tracking_url_template, final_url_suffix, "
                "or url_custom_parameters."
            )
        normalized = _validate_custom_parameters(url_custom_parameters)

        client = ctx.client.raw
        operation = client.get_type("AdGroupOperation")
        ad_group = operation.update
        ad_group.resource_name = client.get_service("AdGroupService").ad_group_path(
            customer_id.replace("-", ""), ad_group_id
        )
        paths = []
        if tracking_url_template is not None:
            ad_group.tracking_url_template = tracking_url_template
            paths.append("tracking_url_template")
        if final_url_suffix is not None:
            ad_group.final_url_suffix = final_url_suffix
            paths.append("final_url_suffix")
        if url_custom_parameters is not None:
            _set_custom_parameters(client, ad_group, normalized)
            paths.append("url_custom_parameters")
        operation.update_mask.CopyFrom(field_mask_pb2.FieldMask(paths=paths))

        description = f"Update tracking URL options on ad group {ad_group_id}"

        def execute():
            return ctx.client.mutate("AdGroupService", customer_id, [operation])

        return ctx.safety.propose(
            tool_name="set_ad_group_tracking_url",
            customer_id=customer_id,
            description=description,
            payload={
                "ad_group_id": ad_group_id,
                "tracking_url_template": tracking_url_template,
                "final_url_suffix": final_url_suffix,
                "url_custom_parameters": (
                    [dict(item) for item in url_custom_parameters]
                    if url_custom_parameters is not None
                    else None
                ),
            },
            execute=execute,
        )

    @mcp.tool()
    def set_account_tracking_url(
        customer_id: str,
        tracking_url_template: str | None = None,
        final_url_suffix: str | None = None,
    ) -> dict:
        """Propose setting account-level tracking URL options.

        Applies to the whole customer. Custom URL parameters are not available
        at account level in v25, so only the template and suffix are supported.
        """
        if tracking_url_template is None and final_url_suffix is None:
            raise ValueError(
                "Provide at least one of tracking_url_template or final_url_suffix."
            )

        client = ctx.client.raw
        operation = client.get_type("CustomerOperation")
        customer = operation.update
        customer.resource_name = client.get_service("CustomerService").customer_path(
            customer_id.replace("-", "")
        )
        paths = []
        if tracking_url_template is not None:
            customer.tracking_url_template = tracking_url_template
            paths.append("tracking_url_template")
        if final_url_suffix is not None:
            customer.final_url_suffix = final_url_suffix
            paths.append("final_url_suffix")
        operation.update_mask.CopyFrom(field_mask_pb2.FieldMask(paths=paths))

        description = "Update account-level tracking URL options"

        def execute():
            return ctx.client.mutate("CustomerService", customer_id, [operation])

        return ctx.safety.propose(
            tool_name="set_account_tracking_url",
            customer_id=customer_id,
            description=description,
            payload={
                "tracking_url_template": tracking_url_template,
                "final_url_suffix": final_url_suffix,
            },
            execute=execute,
        )

    @mcp.tool()
    def get_campaign_tracking_url(customer_id: str, campaign_id: str) -> dict:
        """Read the tracking URL options currently set on a campaign."""
        query = f"""
            SELECT campaign.id, campaign.tracking_url_template,
                   campaign.final_url_suffix,
                   campaign.url_custom_parameters
            FROM campaign
            WHERE campaign.id = {int(campaign_id)}
            LIMIT 1
        """
        rows = ctx.client.search(customer_id, query)
        return {
            "campaign_id": campaign_id,
            "found": bool(rows),
            "url_options": rows[0] if rows else None,
        }

    @mcp.tool()
    def get_ad_group_tracking_url(customer_id: str, ad_group_id: str) -> dict:
        """Read the tracking URL options currently set on an ad group."""
        query = f"""
            SELECT ad_group.id, ad_group.tracking_url_template,
                   ad_group.final_url_suffix,
                   ad_group.url_custom_parameters
            FROM ad_group
            WHERE ad_group.id = {int(ad_group_id)}
            LIMIT 1
        """
        rows = ctx.client.search(customer_id, query)
        return {
            "ad_group_id": ad_group_id,
            "found": bool(rows),
            "url_options": rows[0] if rows else None,
        }

    @mcp.tool()
    def get_account_tracking_url(customer_id: str) -> dict:
        """Read the account-level tracking URL options."""
        query = """
            SELECT customer.tracking_url_template, customer.final_url_suffix
            FROM customer
            LIMIT 1
        """
        rows = ctx.client.search(customer_id, query)
        return {"found": bool(rows), "url_options": rows[0] if rows else None}
