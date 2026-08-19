"""RemarketingAction lifecycle and Google tag retrieval for API v25."""

from __future__ import annotations

from google.protobuf import field_mask_pb2

from ..context import AppContext


def register(mcp, ctx: AppContext) -> None:
    @mcp.tool()
    def list_remarketing_actions(customer_id: str) -> dict:
        """List remarketing actions including generated Google tag snippets."""
        rows = ctx.client.search(
            customer_id,
            """
            SELECT
                remarketing_action.id,
                remarketing_action.resource_name,
                remarketing_action.name,
                remarketing_action.tag_snippets
            FROM remarketing_action
            ORDER BY remarketing_action.id DESC
            """,
        )
        return {"remarketing_actions": rows, "count": len(rows)}

    @mcp.tool()
    def get_remarketing_action(
        customer_id: str,
        remarketing_action_resource_name: str,
    ) -> dict:
        """Retrieve one remarketing action and its Google tag/event snippets."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        resource = ctx.client.assert_resource_name_customer(
            customer,
            remarketing_action_resource_name,
            field_name="remarketing_action_resource_name",
        )
        safe = resource.replace("\\", "\\\\").replace("'", "\\'")
        rows = ctx.client.search(
            customer,
            f"""
            SELECT
                remarketing_action.id,
                remarketing_action.resource_name,
                remarketing_action.name,
                remarketing_action.tag_snippets
            FROM remarketing_action
            WHERE remarketing_action.resource_name = '{safe}'
            LIMIT 1
            """,
        )
        return {"remarketing_action": rows[0] if rows else None, "found": bool(rows)}

    @mcp.tool()
    def create_remarketing_action(customer_id: str, name: str) -> dict:
        """Propose creating a remarketing action so its Google tag can be retrieved."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        clean_name = str(name).strip()
        if not clean_name:
            raise ValueError("name must not be empty.")
        raw = ctx.client.raw
        operation = raw.get_type("RemarketingActionOperation")
        operation.create.name = clean_name

        def execute():
            response = ctx.client.mutate("RemarketingActionService", customer, [operation])
            resource_names = [
                result.resource_name for result in getattr(response, "results", [])
                if getattr(result, "resource_name", None)
            ]
            return {
                "resource_names": resource_names,
                "next_step": (
                    "Call get_remarketing_action with the returned resource name to "
                    "retrieve the account-level Google tag and event snippets."
                ),
            }

        return ctx.safety.propose(
            tool_name="create_remarketing_action",
            customer_id=customer,
            description=f"Create remarketing action '{clean_name}'",
            payload={"name": clean_name},
            execute=execute,
        )

    @mcp.tool()
    def rename_remarketing_action(
        customer_id: str,
        remarketing_action_resource_name: str,
        new_name: str,
    ) -> dict:
        """Propose renaming an existing remarketing action."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        resource = ctx.client.assert_resource_name_customer(
            customer,
            remarketing_action_resource_name,
            field_name="remarketing_action_resource_name",
        )
        clean_name = str(new_name).strip()
        if not clean_name:
            raise ValueError("new_name must not be empty.")
        raw = ctx.client.raw
        operation = raw.get_type("RemarketingActionOperation")
        operation.update.resource_name = resource
        operation.update.name = clean_name
        operation.update_mask.CopyFrom(field_mask_pb2.FieldMask(paths=["name"]))

        def execute():
            return ctx.client.mutate("RemarketingActionService", customer, [operation])

        return ctx.safety.propose(
            tool_name="rename_remarketing_action",
            customer_id=customer,
            description=f"Rename remarketing action {resource} to '{clean_name}'",
            payload={
                "remarketing_action_resource_name": resource,
                "new_name": clean_name,
            },
            execute=execute,
        )
