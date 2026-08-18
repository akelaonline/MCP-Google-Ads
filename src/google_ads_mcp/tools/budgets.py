"""Campaign budget creation and updates."""

from __future__ import annotations

from google.protobuf import field_mask_pb2

from ..client import micros
from ..context import AppContext


def register(mcp, ctx: AppContext) -> None:
    @mcp.tool()
    def create_campaign_budget(
        customer_id: str,
        name: str,
        daily_amount: float,
        delivery_method: str = "STANDARD",
        shared: bool = False,
    ) -> dict:
        """Propose creating a campaign budget.

        Google Ads API v25 supports STANDARD delivery. Accelerated delivery is
        no longer a valid campaign-budget option.
        """
        if not name.strip():
            raise ValueError("name must not be empty.")
        if daily_amount <= 0:
            raise ValueError("daily_amount must be greater than 0.")
        if delivery_method != "STANDARD":
            raise ValueError("delivery_method must be STANDARD in Google Ads API v25.")

        client = ctx.client.raw
        operation = client.get_type("CampaignBudgetOperation")
        budget = operation.create
        budget.name = name
        budget.amount_micros = micros(daily_amount)
        budget.delivery_method = client.enums.BudgetDeliveryMethodEnum.STANDARD.value
        budget.explicitly_shared = shared

        description = (
            f"Create campaign budget '{name}' = {daily_amount:,.2f}/day "
            f"(shared={shared}, STANDARD delivery)"
        )

        def execute():
            return ctx.client.mutate(
                "CampaignBudgetService", customer_id, [operation]
            )

        return ctx.safety.propose(
            tool_name="create_campaign_budget",
            customer_id=customer_id,
            description=description,
            payload={
                "name": name,
                "daily_amount": daily_amount,
                "delivery_method": "STANDARD",
                "shared": shared,
            },
            execute=execute,
        )

    @mcp.tool()
    def update_campaign_budget(
        customer_id: str,
        budget_id: str,
        new_daily_amount: float,
    ) -> dict:
        """Propose changing a campaign budget's daily amount."""
        if new_daily_amount <= 0:
            raise ValueError("new_daily_amount must be greater than 0.")

        client = ctx.client.raw
        operation = client.get_type("CampaignBudgetOperation")
        resource_name = client.get_service("CampaignBudgetService").campaign_budget_path(
            customer_id.replace("-", ""), budget_id
        )
        operation.update.resource_name = resource_name
        operation.update.amount_micros = micros(new_daily_amount)
        operation.update_mask.CopyFrom(
            field_mask_pb2.FieldMask(paths=["amount_micros"])
        )

        description = f"Set budget {budget_id} daily amount -> {new_daily_amount:,.2f}"

        def execute():
            return ctx.client.mutate(
                "CampaignBudgetService", customer_id, [operation]
            )

        return ctx.safety.propose(
            tool_name="update_campaign_budget",
            customer_id=customer_id,
            description=description,
            payload={"budget_id": budget_id, "new_daily_amount": new_daily_amount},
            execute=execute,
        )
