"""Campaign CRUD tools."""

from __future__ import annotations

from google.protobuf import field_mask_pb2

from ..client import from_micros
from ..context import AppContext


def register(mcp, ctx: AppContext) -> None:
    @mcp.tool()
    def list_campaigns(customer_id: str, status_filter: str | None = None) -> dict:
        """List campaigns in the account, optionally filtered by status
        (ENABLED, PAUSED, REMOVED)."""
        where = f"WHERE campaign.status = '{status_filter}'" if status_filter else ""
        query = f"""
            SELECT campaign.id, campaign.name, campaign.status,
                   campaign.advertising_channel_type, campaign.campaign_budget
            FROM campaign
            {where}
            ORDER BY campaign.name
        """
        rows = ctx.client.search(customer_id, query)
        campaigns = [
            {
                "id": r["campaign"]["id"],
                "name": r["campaign"]["name"],
                "status": r["campaign"]["status"],
                "channel_type": r["campaign"].get("advertising_channel_type"),
            }
            for r in rows
        ]
        return {"campaigns": campaigns, "count": len(campaigns)}

    @mcp.tool()
    def create_campaign(
        customer_id: str,
        name: str,
        campaign_budget_resource_name: str,
        channel_type: str = "SEARCH",
        bidding_strategy: str = "MAXIMIZE_CONVERSIONS",
        target_cpa: float | None = None,
        target_roas: float | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
    ) -> dict:
        """Propose creating a new campaign. Create a budget first with create_campaign_budget.

        Args:
            channel_type: SEARCH, DISPLAY, SHOPPING, VIDEO, PERFORMANCE_MAX, etc.
            bidding_strategy: MANUAL_CPC, MAXIMIZE_CONVERSIONS, TARGET_CPA, TARGET_ROAS.
            target_cpa: Required if bidding_strategy is TARGET_CPA (currency units).
            target_roas: Required if bidding_strategy is TARGET_ROAS (e.g. 4.0 = 400%).
            start_date / end_date: YYYY-MM-DD, optional.
        """
        client = ctx.client.raw
        operation = client.get_type("CampaignOperation")
        campaign = operation.create
        campaign.name = name
        campaign.campaign_budget = campaign_budget_resource_name
        campaign.advertising_channel_type = client.enums.AdvertisingChannelTypeEnum[
            channel_type
        ].value
        campaign.status = client.enums.CampaignStatusEnum.PAUSED  # always start paused

        if bidding_strategy == "MANUAL_CPC":
            campaign.manual_cpc.enhanced_cpc_enabled = True
        elif bidding_strategy == "MAXIMIZE_CONVERSIONS":
            campaign.maximize_conversions.SetInParent()
        elif bidding_strategy == "TARGET_CPA":
            if target_cpa is None:
                raise ValueError("target_cpa is required when bidding_strategy=TARGET_CPA")
            from ..client import micros

            campaign.target_cpa.target_cpa_micros = micros(target_cpa)
        elif bidding_strategy == "TARGET_ROAS":
            if target_roas is None:
                raise ValueError("target_roas is required when bidding_strategy=TARGET_ROAS")
            campaign.target_roas.target_roas = target_roas
        else:
            raise ValueError(f"Unsupported bidding_strategy: {bidding_strategy}")

        if start_date:
            campaign.start_date = start_date.replace("-", "")
        if end_date:
            campaign.end_date = end_date.replace("-", "")

        description = (
            f"Create {channel_type} campaign '{name}' "
            f"(bidding: {bidding_strategy}), created PAUSED by default"
        )

        def execute():
            return ctx.client.mutate("CampaignService", customer_id, [operation])

        return ctx.safety.propose(
            tool_name="create_campaign",
            customer_id=customer_id,
            description=description,
            payload={
                "name": name,
                "channel_type": channel_type,
                "bidding_strategy": bidding_strategy,
                "target_cpa": target_cpa,
                "target_roas": target_roas,
            },
            execute=execute,
        )

    @mcp.tool()
    def update_campaign_status(customer_id: str, campaign_id: str, status: str) -> dict:
        """Propose pausing, enabling, or removing a campaign.

        Args:
            status: ENABLED, PAUSED, or REMOVED.
        """
        client = ctx.client.raw
        operation = client.get_type("CampaignOperation")
        resource_name = client.get_service("CampaignService").campaign_path(
            customer_id.replace("-", ""), campaign_id
        )
        operation.update.resource_name = resource_name
        operation.update.status = client.enums.CampaignStatusEnum[status].value
        operation.update_mask.CopyFrom(field_mask_pb2.FieldMask(paths=["status"]))

        description = f"Set campaign {campaign_id} status -> {status}"

        def execute():
            return ctx.client.mutate("CampaignService", customer_id, [operation])

        return ctx.safety.propose(
            tool_name="update_campaign_status",
            customer_id=customer_id,
            description=description,
            payload={"campaign_id": campaign_id, "status": status},
            execute=execute,
        )

    @mcp.tool()
    def update_campaign_name(customer_id: str, campaign_id: str, new_name: str) -> dict:
        """Propose renaming a campaign."""
        client = ctx.client.raw
        operation = client.get_type("CampaignOperation")
        resource_name = client.get_service("CampaignService").campaign_path(
            customer_id.replace("-", ""), campaign_id
        )
        operation.update.resource_name = resource_name
        operation.update.name = new_name
        operation.update_mask.CopyFrom(field_mask_pb2.FieldMask(paths=["name"]))

        description = f"Rename campaign {campaign_id} -> '{new_name}'"

        def execute():
            return ctx.client.mutate("CampaignService", customer_id, [operation])

        return ctx.safety.propose(
            tool_name="update_campaign_name",
            customer_id=customer_id,
            description=description,
            payload={"campaign_id": campaign_id, "new_name": new_name},
            execute=execute,
        )

    @mcp.tool()
    def remove_campaign(customer_id: str, campaign_id: str) -> dict:
        """Propose permanently removing a campaign. Prefer update_campaign_status(..., 'PAUSED')
        unless you specifically need to delete it."""
        client = ctx.client.raw
        operation = client.get_type("CampaignOperation")
        resource_name = client.get_service("CampaignService").campaign_path(
            customer_id.replace("-", ""), campaign_id
        )
        operation.remove = resource_name

        description = f"REMOVE campaign {campaign_id} (irreversible)"

        def execute():
            return ctx.client.mutate("CampaignService", customer_id, [operation])

        return ctx.safety.propose(
            tool_name="remove_campaign",
            customer_id=customer_id,
            description=description,
            payload={"campaign_id": campaign_id},
            execute=execute,
        )
