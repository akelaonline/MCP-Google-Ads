"""Bidding strategy tools — change how an existing campaign bids."""

from __future__ import annotations

from google.protobuf import field_mask_pb2

from ..client import micros
from ..context import AppContext


def _campaign_operation(ctx, customer_id, campaign_id):
    client = ctx.client.raw
    operation = client.get_type("CampaignOperation")
    resource_name = client.get_service("CampaignService").campaign_path(
        customer_id.replace("-", ""), campaign_id
    )
    operation.update.resource_name = resource_name
    return client, operation


def register(mcp, ctx: AppContext) -> None:
    @mcp.tool()
    def set_manual_cpc(customer_id: str, campaign_id: str, enhanced_cpc: bool = True) -> dict:
        """Propose switching a campaign to Manual CPC bidding."""
        client, operation = _campaign_operation(ctx, customer_id, campaign_id)
        operation.update.manual_cpc.enhanced_cpc_enabled = enhanced_cpc
        operation.update_mask.CopyFrom(
            field_mask_pb2.FieldMask(paths=["manual_cpc.enhanced_cpc_enabled"])
        )
        description = f"Set campaign {campaign_id} bidding -> Manual CPC (eCPC={enhanced_cpc})"

        def execute():
            return ctx.client.mutate("CampaignService", customer_id, [operation])

        return ctx.safety.propose(
            tool_name="set_manual_cpc",
            customer_id=customer_id,
            description=description,
            payload={"campaign_id": campaign_id, "enhanced_cpc": enhanced_cpc},
            execute=execute,
        )

    @mcp.tool()
    def set_maximize_conversions(
        customer_id: str, campaign_id: str, target_cpa: float | None = None
    ) -> dict:
        """Propose switching a campaign to Maximize Conversions bidding,
        optionally with a target CPA cap."""
        client, operation = _campaign_operation(ctx, customer_id, campaign_id)
        if target_cpa is not None:
            operation.update.maximize_conversions.target_cpa_micros = micros(target_cpa)
            mask = ["maximize_conversions.target_cpa_micros"]
        else:
            operation.update.maximize_conversions.SetInParent()
            mask = ["maximize_conversions"]
        operation.update_mask.CopyFrom(field_mask_pb2.FieldMask(paths=mask))

        description = f"Set campaign {campaign_id} bidding -> Maximize Conversions" + (
            f" (target CPA ${target_cpa:,.2f})" if target_cpa else ""
        )

        def execute():
            return ctx.client.mutate("CampaignService", customer_id, [operation])

        return ctx.safety.propose(
            tool_name="set_maximize_conversions",
            customer_id=customer_id,
            description=description,
            payload={"campaign_id": campaign_id, "target_cpa": target_cpa},
            execute=execute,
        )

    @mcp.tool()
    def set_target_cpa(customer_id: str, campaign_id: str, target_cpa: float) -> dict:
        """Propose switching a campaign to Target CPA bidding."""
        client, operation = _campaign_operation(ctx, customer_id, campaign_id)
        operation.update.target_cpa.target_cpa_micros = micros(target_cpa)
        operation.update_mask.CopyFrom(
            field_mask_pb2.FieldMask(paths=["target_cpa.target_cpa_micros"])
        )
        description = f"Set campaign {campaign_id} bidding -> Target CPA ${target_cpa:,.2f}"

        def execute():
            return ctx.client.mutate("CampaignService", customer_id, [operation])

        return ctx.safety.propose(
            tool_name="set_target_cpa",
            customer_id=customer_id,
            description=description,
            payload={"campaign_id": campaign_id, "target_cpa": target_cpa},
            execute=execute,
        )

    @mcp.tool()
    def set_target_roas(customer_id: str, campaign_id: str, target_roas: float) -> dict:
        """Propose switching a campaign to Target ROAS bidding.

        Args:
            target_roas: Ratio, e.g. 4.0 means 400% (aim for $4 revenue per $1 spent).
        """
        client, operation = _campaign_operation(ctx, customer_id, campaign_id)
        operation.update.target_roas.target_roas = target_roas
        operation.update_mask.CopyFrom(field_mask_pb2.FieldMask(paths=["target_roas.target_roas"]))
        description = f"Set campaign {campaign_id} bidding -> Target ROAS {target_roas:.2f}"

        def execute():
            return ctx.client.mutate("CampaignService", customer_id, [operation])

        return ctx.safety.propose(
            tool_name="set_target_roas",
            customer_id=customer_id,
            description=description,
            payload={"campaign_id": campaign_id, "target_roas": target_roas},
            execute=execute,
        )
