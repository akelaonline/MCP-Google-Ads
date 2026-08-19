"""Account discovery & hierarchy tools, plus MCC/client account linking."""

from __future__ import annotations

from google.protobuf import field_mask_pb2

from ..context import AppContext
from ..errors import GoogleAdsMcpError, format_google_ads_exception


def _numeric_customer_id(value: str, field_name: str) -> str:
    normalized = str(value).replace("-", "").strip()
    if not normalized.isdigit():
        raise ValueError(f"{field_name} must be a numeric Google Ads customer ID.")
    return normalized


def _manager_status_operation(ctx: AppContext, resource_name: str, status: str):
    client = ctx.client.raw
    operation = client.get_type("CustomerManagerLinkOperation")
    operation.update.resource_name = resource_name
    operation.update.status = getattr(client.enums.ManagerLinkStatusEnum, status)
    operation.update_mask.CopyFrom(field_mask_pb2.FieldMask(paths=["status"]))
    return operation


def _client_link_status_operation(ctx: AppContext, resource_name: str, status: str):
    client = ctx.client.raw
    operation = client.get_type("CustomerClientLinkOperation")
    operation.update.resource_name = resource_name
    operation.update.status = getattr(client.enums.ManagerLinkStatusEnum, status)
    operation.update_mask.CopyFrom(field_mask_pb2.FieldMask(paths=["status"]))
    return operation


def register(mcp, ctx: AppContext) -> None:
    @mcp.tool()
    def list_accessible_customers() -> dict:
        """List Google Ads customer IDs visible within this deployment's scope."""
        service = ctx.client.service("CustomerService")
        response = service.list_accessible_customers()
        ids = [rn.split("/")[-1] for rn in response.resource_names]
        ids = ctx.client.filter_allowed_customer_ids(ids)
        return {"customer_ids": ids, "count": len(ids)}

    @mcp.tool()
    def get_account_hierarchy(login_customer_id: str) -> dict:
        """Return the manager/client account tree under an allowed MCC."""
        manager = ctx.client.assert_customer_allowed(login_customer_id)
        query = """
            SELECT
                customer_client.id,
                customer_client.descriptive_name,
                customer_client.level,
                customer_client.manager,
                customer_client.status,
                customer_client.currency_code,
                customer_client.time_zone
            FROM customer_client
            WHERE customer_client.status = 'ENABLED'
        """
        rows = ctx.client.search(manager, query)
        allowed = set(ctx.client.filter_allowed_customer_ids(
            [str(r["customer_client"]["id"]) for r in rows]
        ))
        accounts = [
            {
                "id": str(r["customer_client"]["id"]),
                "name": r["customer_client"].get("descriptive_name"),
                "level": r["customer_client"]["level"],
                "is_manager": r["customer_client"]["manager"],
                "currency": r["customer_client"].get("currency_code"),
                "time_zone": r["customer_client"].get("time_zone"),
            }
            for r in rows
            if str(r["customer_client"]["id"]) in allowed
        ]
        return {"login_customer_id": manager, "accounts": accounts, "count": len(accounts)}

    @mcp.tool()
    def get_account_summary(customer_id: str) -> dict:
        """Basic account info: name, currency, time zone, and account status."""
        query = """
            SELECT
                customer.id,
                customer.descriptive_name,
                customer.currency_code,
                customer.time_zone,
                customer.status,
                customer.manager,
                customer.test_account
            FROM customer
            LIMIT 1
        """
        rows = ctx.client.search(customer_id, query)
        if not rows:
            return {"error": "No data returned for that customer_id."}
        c = rows[0]["customer"]
        return {
            "id": c["id"],
            "name": c.get("descriptive_name"),
            "currency": c.get("currency_code"),
            "time_zone": c.get("time_zone"),
            "status": c.get("status"),
            "is_manager": c.get("manager"),
            "is_test_account": c.get("test_account"),
        }

    @mcp.tool()
    def create_customer_client(
        login_customer_id: str,
        descriptive_name: str,
        currency_code: str = "USD",
        time_zone: str = "America/Argentina/Buenos_Aires",
    ) -> dict:
        """Propose creating a new client account under a manager account."""
        manager = ctx.client.assert_customer_allowed(login_customer_id)
        if not descriptive_name.strip():
            raise ValueError("descriptive_name must not be empty.")
        client = ctx.client.raw
        customer_client = client.get_type("Customer")
        customer_client.descriptive_name = descriptive_name.strip()
        customer_client.currency_code = currency_code.strip().upper()
        customer_client.time_zone = time_zone.strip()

        description = (
            f"Create new client account '{descriptive_name.strip()}' ({currency_code}, "
            f"{time_zone}) under manager {manager}"
        )

        def execute():
            from google.ads.googleads.errors import GoogleAdsException

            service = client.get_service("CustomerService")
            try:
                response = service.create_customer_client(
                    customer_id=manager,
                    customer_client=customer_client,
                )
            except GoogleAdsException as ex:
                raise GoogleAdsMcpError(format_google_ads_exception(ex)) from ex
            return {"resource_name": response.resource_name}

        return ctx.safety.propose(
            tool_name="create_customer_client",
            customer_id=manager,
            description=description,
            payload={
                "login_customer_id": manager,
                "descriptive_name": descriptive_name.strip(),
                "currency_code": currency_code.strip().upper(),
                "time_zone": time_zone.strip(),
            },
            execute=execute,
        )

    @mcp.tool()
    def list_client_links(manager_customer_id: str) -> dict:
        """List manager-side CustomerClientLink records, including pending links."""
        manager = ctx.client.assert_customer_allowed(manager_customer_id)
        rows = ctx.client.search(
            manager,
            """
            SELECT
                customer_client_link.resource_name,
                customer_client_link.client_customer,
                customer_client_link.manager_link_id,
                customer_client_link.status,
                customer_client_link.hidden
            FROM customer_client_link
            """,
        )
        return {"client_links": rows, "count": len(rows)}

    @mcp.tool()
    def list_manager_links(customer_id: str) -> dict:
        """List manager (MCC) links for an allowed client account."""
        rows = ctx.client.search(
            customer_id,
            """
            SELECT
                customer_manager_link.resource_name,
                customer_manager_link.manager_customer,
                customer_manager_link.manager_link_id,
                customer_manager_link.status
            FROM customer_manager_link
            """,
        )
        return {"manager_links": rows, "count": len(rows)}

    @mcp.tool()
    def invite_manager_link(
        manager_customer_id: str,
        client_customer_id: str,
    ) -> dict:
        """Propose inviting an existing client account from a manager account."""
        manager = ctx.client.assert_customer_allowed(manager_customer_id)
        client_customer = ctx.client.assert_customer_allowed(client_customer_id)
        if manager == client_customer:
            raise ValueError("manager_customer_id and client_customer_id must differ.")

        raw = ctx.client.raw
        operation = raw.get_type("CustomerClientLinkOperation")
        operation.create.client_customer = f"customers/{client_customer}"
        operation.create.status = raw.enums.ManagerLinkStatusEnum.PENDING

        def execute():
            return ctx.client.mutate(
                "CustomerClientLinkService",
                manager,
                [operation],
                operations_field="operation",
            )

        return ctx.safety.propose(
            tool_name="invite_manager_link",
            customer_id=manager,
            description=(
                f"Invite client customer {client_customer} to be managed by {manager}"
            ),
            payload={
                "manager_customer_id": manager,
                "client_customer_id": client_customer,
            },
            execute=execute,
        )

    @mcp.tool()
    def accept_manager_link(customer_id: str, manager_link_resource_name: str) -> dict:
        """Propose accepting a pending manager link invitation from the client side."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        resource = ctx.client.assert_resource_name_customer(
            customer,
            manager_link_resource_name,
            field_name="manager_link_resource_name",
        )
        operation = _manager_status_operation(ctx, resource, "ACTIVE")

        def execute():
            return ctx.client.mutate(
                "CustomerManagerLinkService", customer, [operation]
            )

        return ctx.safety.propose(
            tool_name="accept_manager_link",
            customer_id=customer,
            description=f"Accept manager link {resource}",
            payload={"manager_link_resource_name": resource},
            execute=execute,
        )

    @mcp.tool()
    def decline_manager_link(customer_id: str, manager_link_resource_name: str) -> dict:
        """Propose refusing a pending manager invitation from the client side."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        resource = ctx.client.assert_resource_name_customer(
            customer,
            manager_link_resource_name,
            field_name="manager_link_resource_name",
        )
        operation = _manager_status_operation(ctx, resource, "REFUSED")

        def execute():
            return ctx.client.mutate(
                "CustomerManagerLinkService", customer, [operation]
            )

        return ctx.safety.propose(
            tool_name="decline_manager_link",
            customer_id=customer,
            description=f"Refuse manager link invitation {resource}",
            payload={"manager_link_resource_name": resource},
            execute=execute,
        )

    @mcp.tool()
    def unlink_manager(customer_id: str, manager_link_resource_name: str) -> dict:
        """Propose terminating an active manager relationship from the client side."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        resource = ctx.client.assert_resource_name_customer(
            customer,
            manager_link_resource_name,
            field_name="manager_link_resource_name",
        )
        operation = _manager_status_operation(ctx, resource, "INACTIVE")

        def execute():
            return ctx.client.mutate(
                "CustomerManagerLinkService", customer, [operation]
            )

        return ctx.safety.propose(
            tool_name="unlink_manager",
            customer_id=customer,
            description=f"Terminate active manager relationship {resource}",
            payload={"manager_link_resource_name": resource},
            execute=execute,
        )

    @mcp.tool()
    def cancel_manager_link_invitation(
        manager_customer_id: str,
        client_link_resource_name: str,
    ) -> dict:
        """Propose canceling a pending CustomerClientLink from the manager side."""
        manager = ctx.client.assert_customer_allowed(manager_customer_id)
        resource = ctx.client.assert_resource_name_customer(
            manager,
            client_link_resource_name,
            field_name="client_link_resource_name",
        )
        operation = _client_link_status_operation(ctx, resource, "CANCELED")

        def execute():
            return ctx.client.mutate(
                "CustomerClientLinkService",
                manager,
                [operation],
                operations_field="operation",
            )

        return ctx.safety.propose(
            tool_name="cancel_manager_link_invitation",
            customer_id=manager,
            description=f"Cancel pending manager invitation {resource}",
            payload={"client_link_resource_name": resource},
            execute=execute,
        )

    @mcp.tool()
    def move_manager_link(
        customer_id: str,
        previous_manager_link_resource_name: str,
        new_manager_customer_id: str,
    ) -> dict:
        """Propose moving a client customer from its current manager to a new manager."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        previous = ctx.client.assert_resource_name_customer(
            customer,
            previous_manager_link_resource_name,
            field_name="previous_manager_link_resource_name",
        )
        new_manager = ctx.client.assert_customer_allowed(new_manager_customer_id)
        if new_manager == customer:
            raise ValueError("new_manager_customer_id cannot equal customer_id.")

        def execute():
            from google.ads.googleads.errors import GoogleAdsException

            raw = ctx.client.raw
            service = raw.get_service("CustomerManagerLinkService")
            request = raw.get_type("MoveManagerLinkRequest")
            request.customer_id = customer
            request.previous_customer_manager_link = previous
            request.new_manager = f"customers/{new_manager}"
            try:
                response = service.move_manager_link(request=request)
            except GoogleAdsException as ex:
                raise GoogleAdsMcpError(format_google_ads_exception(ex)) from ex
            return {"resource_name": response.resource_name}

        return ctx.safety.propose(
            tool_name="move_manager_link",
            customer_id=customer,
            description=(
                f"Move customer {customer} from {previous} to new manager {new_manager}"
            ),
            payload={
                "previous_manager_link_resource_name": previous,
                "new_manager_customer_id": new_manager,
            },
            execute=execute,
        )
