"""Campaign budget tools (write)."""

from __future__ import annotations

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
        """Propose creating a new campaign budget (daily amount, in account currency).

        Args:
            daily_amount: Daily budget in whole currency units (e.g. 25.50 for $25.50/day).
            delivery_method: STANDARD or ACCELERATED.
            shared: If true, the budget can be attached to multiple campaigns.
        """
        client = ctx.client.raw
        operation = client.get_type("CampaignBudgetOperation")
        budget = operation.create
        budget.name = name
        budget.amount_micros = micros(daily_amount)
        budget.delivery_method = client.enums.BudgetDeliveryMethodEnum[delivery_method].value
        budget.explicitly_shared = shared

        description = f"Create budget '{name}': ${daily_amount:,.2f}/day ({delivery_method})"

        def execute():
            return ctx.client.mutate("CampaignBudgetService", customer_id, [operation])

        return ctx.safety.propose(
            tool_name="create_campaign_budget",
            customer_id=customer_id,
            description=description,
            payload={"name": name, "daily_amount": daily_amount, "delivery_method": delivery_method},
            execute=execute,
        )

    @mcp.tool()
    def update_campaign_budget(customer_id: str, budget_id: str, new_daily_amount: float) -> dict:
        """Propose changing an existing campaign budget's daily amount."""
        client = ctx.client.raw
        operation = client.get_type("CampaignBudgetOperation")
        resource_name = client.get_service("CampaignBudgetService").campaign_budget_path(
            customer_id.replace("-", ""), budget_id
        )
        budget = operation.update
        budget.resource_name = resource_name
        budget.amount_micros = micros(new_daily_amount)

        from google.protobuf import field_mask_pb2

        operation.update_mask.CopyFrom(
            field_mask_pb2.FieldMask(paths=["amount_micros"])
        )

        description = f"Update budget {budget_id} daily amount to ${new_daily_amount:,.2f}"

        def execute():
            return ctx.client.mutate("CampaignBudgetService", customer_id, [operation])

        return ctx.safety.propose(
            tool_name="update_campaign_budget",
            customer_id=customer_id,
            description=description,
            payload={"budget_id": budget_id, "new_daily_amount": new_daily_amount},
            execute=execute,
        )
