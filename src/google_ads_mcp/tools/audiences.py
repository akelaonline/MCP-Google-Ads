"""Audience / remarketing list tools."""

from __future__ import annotations

from ..context import AppContext


def register(mcp, ctx: AppContext) -> None:
    @mcp.tool()
    def list_user_lists(customer_id: str) -> dict:
        """List remarketing / customer-match audience lists available in the account."""
        query = """
            SELECT user_list.id, user_list.name, user_list.size_for_search,
                   user_list.size_for_display, user_list.membership_status, user_list.type
            FROM user_list
            WHERE user_list.membership_status = 'OPEN'
        """
        rows = ctx.client.search(customer_id, query)
        return {"user_lists": rows}

    @mcp.tool()
    def attach_audience_to_ad_group(
        customer_id: str,
        ad_group_id: str,
        user_list_resource_name: str,
        bid_modifier: float | None = None,
    ) -> dict:
        """Propose attaching an audience (user list) to an ad group for observation or targeting.

        Args:
            user_list_resource_name: e.g. "customers/123/userLists/456" (from list_user_lists).
            bid_modifier: Optional bid modifier, e.g. 1.2 for +20%.
        """
        client = ctx.client.raw
        operation = client.get_type("AdGroupCriterionOperation")
        criterion = operation.create
        criterion.ad_group = client.get_service("AdGroupService").ad_group_path(
            customer_id.replace("-", ""), ad_group_id
        )
        criterion.user_list.user_list = user_list_resource_name
        if bid_modifier is not None:
            criterion.bid_modifier = bid_modifier

        description = f"Attach audience {user_list_resource_name} to ad group {ad_group_id}" + (
            f" (bid modifier x{bid_modifier})" if bid_modifier else ""
        )

        def execute():
            return ctx.client.mutate("AdGroupCriterionService", customer_id, [operation])

        return ctx.safety.propose(
            tool_name="attach_audience_to_ad_group",
            customer_id=customer_id,
            description=description,
            payload={
                "ad_group_id": ad_group_id,
                "user_list_resource_name": user_list_resource_name,
                "bid_modifier": bid_modifier,
            },
            execute=execute,
        )
