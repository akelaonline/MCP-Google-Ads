"""Ad group CRUD tools."""

from __future__ import annotations

from google.protobuf import field_mask_pb2

from ..client import micros
from ..context import AppContext


def register(mcp, ctx: AppContext) -> None:
    @mcp.tool()
    def create_ad_group(
        customer_id: str,
        campaign_id: str,
        name: str,
        cpc_bid: float | None = None,
        status: str = "PAUSED",
    ) -> dict:
        """Propose creating a new ad group inside an existing campaign."""
        client = ctx.client.raw
        operation = client.get_type("AdGroupOperation")
        ad_group = operation.create
        ad_group.name = name
        ad_group.campaign = client.get_service("CampaignService").campaign_path(
            customer_id.replace("-", ""), campaign_id
        )
        ad_group.status = client.enums.AdGroupStatusEnum[status].value
        ad_group.type_ = client.enums.AdGroupTypeEnum.SEARCH_STANDARD
        if cpc_bid is not None:
            ad_group.cpc_bid_micros = micros(cpc_bid)

        description = f"Create ad group '{name}' in campaign {campaign_id} (status={status})"

        def execute():
            return ctx.client.mutate("AdGroupService", customer_id, [operation])

        return ctx.safety.propose(
            tool_name="create_ad_group",
            customer_id=customer_id,
            description=description,
            payload={"campaign_id": campaign_id, "name": name, "cpc_bid": cpc_bid, "status": status},
            execute=execute,
        )

    @mcp.tool()
    def update_ad_group_status(customer_id: str, ad_group_id: str, status: str) -> dict:
        """Propose pausing, enabling, or removing an ad group.

        Args:
            status: ENABLED, PAUSED, or REMOVED.
        """
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
    def update_ad_group_cpc_bid(customer_id: str, ad_group_id: str, new_cpc_bid: float) -> dict:
        """Propose changing an ad group's default max CPC bid."""
        client = ctx.client.raw
        operation = client.get_type("AdGroupOperation")
        resource_name = client.get_service("AdGroupService").ad_group_path(
            customer_id.replace("-", ""), ad_group_id
        )
        operation.update.resource_name = resource_name
        operation.update.cpc_bid_micros = micros(new_cpc_bid)
        operation.update_mask.CopyFrom(field_mask_pb2.FieldMask(paths=["cpc_bid_micros"]))

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
