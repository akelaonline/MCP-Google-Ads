"""User-list customer-type relationships for Google Ads API v25."""

from __future__ import annotations

from ..context import AppContext


def register(mcp, ctx: AppContext) -> None:
    @mcp.tool()
    def list_user_list_customer_types(customer_id: str) -> dict:
        """List semantic customer-type labels attached to user lists."""
        rows = ctx.client.search(
            customer_id,
            """
            SELECT
                user_list_customer_type.resource_name,
                user_list_customer_type.user_list,
                user_list_customer_type.customer_type_category
            FROM user_list_customer_type
            ORDER BY user_list_customer_type.resource_name
            """,
        )
        return {"count": len(rows), "user_list_customer_types": rows}

    @mcp.tool()
    def assign_user_list_customer_type(
        customer_id: str,
        user_list_resource_name: str,
        customer_type_category: str,
    ) -> dict:
        """Propose attaching a lifecycle/customer semantic category to a user list."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        user_list = _user_list(customer, user_list_resource_name)
        category = customer_type_category.strip().upper()
        if category in {"", "UNKNOWN", "UNSPECIFIED"}:
            raise ValueError("customer_type_category must be a concrete enum name.")
        raw = ctx.client.raw
        operation = raw.get_type("UserListCustomerTypeOperation")
        relation = operation.create
        relation.user_list = user_list
        try:
            relation.customer_type_category = getattr(
                raw.enums.UserListCustomerTypeCategoryEnum, category
            )
        except AttributeError as ex:
            raise ValueError(
                f"Unknown UserListCustomerTypeCategory {category!r} for v25."
            ) from ex

        def execute():
            return ctx.client.mutate("UserListCustomerTypeService", customer, [operation])

        return ctx.safety.propose(
            tool_name="assign_user_list_customer_type",
            customer_id=customer,
            description=f"Attach customer type {category} to {user_list}",
            payload={
                "user_list_resource_name": user_list,
                "customer_type_category": category,
            },
            execute=execute,
        )

    @mcp.tool()
    def remove_user_list_customer_type(
        customer_id: str,
        resource_name: str,
    ) -> dict:
        """Propose removing one user-list customer-type relationship."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        resource = _relation(customer, resource_name)
        operation = ctx.client.raw.get_type("UserListCustomerTypeOperation")
        operation.remove = resource

        def execute():
            return ctx.client.mutate("UserListCustomerTypeService", customer, [operation])

        return ctx.safety.propose(
            tool_name="remove_user_list_customer_type",
            customer_id=customer,
            description=f"Remove user-list customer type {resource}",
            payload={"resource_name": resource},
            execute=execute,
        )


def _user_list(customer_id: str, value: str) -> str:
    resource = value.strip()
    prefix = f"customers/{customer_id}/userLists/"
    if not resource.startswith(prefix) or not resource[len(prefix) :].isdigit():
        raise ValueError(f"user_list_resource_name must match '{prefix}{{user_list_id}}'.")
    return resource


def _relation(customer_id: str, value: str) -> str:
    resource = value.strip()
    prefix = f"customers/{customer_id}/userListCustomerTypes/"
    suffix = resource[len(prefix) :] if resource.startswith(prefix) else ""
    left, sep, right = suffix.partition("~")
    if not sep or not left.isdigit() or not right:
        raise ValueError(
            f"resource_name must match '{prefix}{{user_list_id}}~{{customer_type_category}}'."
        )
    return resource
