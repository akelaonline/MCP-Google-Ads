"""Ad group CRUD tools."""

from __future__ import annotations

from google.protobuf import field_mask_pb2

from ..client import micros
from ..context import AppContext

_AUTO_AD_GROUP_TYPE_BY_CHANNEL = {
    "SEARCH": "SEARCH_STANDARD",
    "DISPLAY": "DISPLAY_STANDARD",
    "SHOPPING": "SHOPPING_PRODUCT_ADS",
    # Demand Gen and App campaigns explicitly require an ad group with no type.
    # App campaigns report channel MULTI_CHANNEL in v25.
    "DEMAND_GEN": None,
    "MULTI_CHANNEL": None,
}


def register(mcp, ctx: AppContext) -> None:
    @mcp.tool()
    def create_ad_group(
        customer_id: str,
        campaign_id: str,
        name: str,
        cpc_bid: float | None = None,
        status: str = "PAUSED",
        ad_group_type: str | None = "AUTO",
    ) -> dict:
        """Propose creating a new ad group inside an existing campaign.

        ``ad_group_type='AUTO'`` inspects the campaign channel and chooses the
        correct type for Search, Display and Standard Shopping. Demand Gen is
        created with no type, as required by the current API. For channel types
        with multiple valid ad-group variants (for example Video), pass the
        explicit Google Ads ``AdGroupType`` enum name.
        """
        if not name.strip():
            raise ValueError("name must not be empty.")
        if status not in {"ENABLED", "PAUSED"}:
            raise ValueError("status must be ENABLED or PAUSED when creating an ad group.")
        if cpc_bid is not None and cpc_bid <= 0:
            raise ValueError("cpc_bid must be greater than 0.")

        resolved_type = ad_group_type
        campaign_channel = None
        if ad_group_type == "AUTO":
            campaign_channel = _get_campaign_channel(ctx, customer_id, campaign_id)
            if campaign_channel not in _AUTO_AD_GROUP_TYPE_BY_CHANNEL:
                raise ValueError(
                    f"Campaign channel {campaign_channel!r} requires an explicit "
                    "ad_group_type because more than one ad-group type may be valid."
                )
            resolved_type = _AUTO_AD_GROUP_TYPE_BY_CHANNEL[campaign_channel]

        if campaign_channel == "DEMAND_GEN" and cpc_bid is not None:
            raise ValueError(
                "Do not set cpc_bid on a Demand Gen ad group; bidding is configured "
                "at campaign level."
            )

        client = ctx.client.raw
        operation = client.get_type("AdGroupOperation")
        ad_group = operation.create
        ad_group.name = name
        ad_group.campaign = client.get_service("CampaignService").campaign_path(
            customer_id.replace("-", ""), campaign_id
        )
        ad_group.status = client.enums.AdGroupStatusEnum[status].value
        if resolved_type is not None:
            ad_group.type_ = client.enums.AdGroupTypeEnum[resolved_type].value
        if cpc_bid is not None:
            ad_group.cpc_bid_micros = micros(cpc_bid)

        type_label = resolved_type or "UNSET (required for Demand Gen)"
        description = (
            f"Create ad group '{name}' in campaign {campaign_id} "
            f"(status={status}, type={type_label})"
        )

        def execute():
            return ctx.client.mutate("AdGroupService", customer_id, [operation])

        return ctx.safety.propose(
            tool_name="create_ad_group",
            customer_id=customer_id,
            description=description,
            payload={
                "campaign_id": campaign_id,
                "name": name,
                "cpc_bid": cpc_bid,
                "status": status,
                "campaign_channel": campaign_channel,
                "ad_group_type": resolved_type,
            },
            execute=execute,
        )

    @mcp.tool()
    def update_ad_group_status(customer_id: str, ad_group_id: str, status: str) -> dict:
        """Propose pausing, enabling, or removing an ad group."""
        if status not in {"ENABLED", "PAUSED", "REMOVED"}:
            raise ValueError("status must be ENABLED, PAUSED, or REMOVED.")
        client = ctx.client.raw
        operation = client.get_type("AdGroupOperation")
        resource_name = client.get_service("AdGroupService").ad_group_path(
            customer_id.replace("-", ""), ad_group_id
        )
        operation.update.resource_name = resource_name
        operation.update.status = client.enums.AdGroupStatusEnum[status].value
        operation.update_mask.CopyFrom(field_mask_pb2.FieldMask(paths=["status"]))

        description = f"Set ad group {ad_group_id} status -> {status}"

        def execute():
            return ctx.client.mutate("AdGroupService", customer_id, [operation])

        return ctx.safety.propose(
            tool_name="update_ad_group_status",
            customer_id=customer_id,
            description=description,
            payload={"ad_group_id": ad_group_id, "status": status},
            execute=execute,
        )

    @mcp.tool()
    def update_ad_group_cpc_bid(
        customer_id: str, ad_group_id: str, new_cpc_bid: float
    ) -> dict:
        """Propose changing an ad group's default max CPC bid."""
        if new_cpc_bid <= 0:
            raise ValueError("new_cpc_bid must be greater than 0.")
        client = ctx.client.raw
        operation = client.get_type("AdGroupOperation")
        resource_name = client.get_service("AdGroupService").ad_group_path(
            customer_id.replace("-", ""), ad_group_id
        )
        operation.update.resource_name = resource_name
        operation.update.cpc_bid_micros = micros(new_cpc_bid)
        operation.update_mask.CopyFrom(
            field_mask_pb2.FieldMask(paths=["cpc_bid_micros"])
        )

        description = f"Set ad group {ad_group_id} CPC bid -> ${new_cpc_bid:,.2f}"

        def execute():
            return ctx.client.mutate("AdGroupService", customer_id, [operation])

        return ctx.safety.propose(
            tool_name="update_ad_group_cpc_bid",
            customer_id=customer_id,
            description=description,
            payload={"ad_group_id": ad_group_id, "new_cpc_bid": new_cpc_bid},
            execute=execute,
        )


def _get_campaign_channel(ctx: AppContext, customer_id: str, campaign_id: str) -> str:
    query = f"""
        SELECT campaign.advertising_channel_type
        FROM campaign
        WHERE campaign.id = {int(campaign_id)}
        LIMIT 1
    """
    rows = ctx.client.search(customer_id, query)
    if not rows:
        raise ValueError(f"Campaign {campaign_id} was not found or is not accessible.")
    channel = rows[0].get("campaign", {}).get("advertising_channel_type")
    if not channel:
        raise ValueError(f"Campaign {campaign_id} did not return an advertising channel type.")
    return str(channel)
