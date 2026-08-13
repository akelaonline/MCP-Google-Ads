"""Account discovery & hierarchy tools (read-only), plus MCC<->client
account linking (write)."""

from __future__ import annotations

from ..context import AppContext


def register(mcp, ctx: AppContext) -> None:
    @mcp.tool()
    def list_accessible_customers() -> dict:
        """List every Google Ads customer ID the authenticated credentials can access."""
        service = ctx.client.service("CustomerService")
        response = service.list_accessible_customers()
        ids = [rn.split("/")[-1] for rn in response.resource_names]
        return {"customer_ids": ids, "count": len(ids)}

    @mcp.tool()
    def get_account_hierarchy(login_customer_id: str) -> dict:
        """Return the full manager/client account tree under a given MCC customer ID.

        Args:
            login_customer_id: The manager (MCC) account ID, digits only or with dashes.
        """
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
        rows = ctx.client.search(login_customer_id, query)
        accounts = [
            {
                "id": r["customer_client"]["id"],
                "name": r["customer_client"].get("descriptive_name"),
                "level": r["customer_client"]["level"],
                "is_manager": r["customer_client"]["manager"],
                "currency": r["customer_client"].get("currency_code"),
                "time_zone": r["customer_client"].get("time_zone"),
            }
            for r in rows
        ]
        return {"login_customer_id": login_customer_id, "accounts": accounts}

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
        """Propose creating a brand-new client account under a manager (MCC)
        account — e.g. onboarding a new agency client without leaving the
        MCP. The new account is automatically linked under login_customer_id.

        Args:
            login_customer_id: The MCC (manager) account ID this new client
                account will be created under.
            currency_code: ISO currency, e.g. "USD", "ARS". Immutable after
                creation — double-check before confirming.
            time_zone: IANA time zone, e.g. "America/Argentina/Buenos_Aires".
                Also immutable after creation.
        """
        client = ctx.client.raw
        customer_client = client.get_type("Customer")
        customer_client.descriptive_name = descriptive_name
        customer_client.currency_code = currency_code
        customer_client.time_zone = time_zone

        description = (
            f"Create new client account '{descriptive_name}' ({currency_code}, "
            f"{time_zone}) under manager {login_customer_id}"
        )

        def execute():
            service = client.get_service("CustomerService")
            response = service.create_customer_client(
                customer_id=login_customer_id.replace("-", ""),
                customer_client=customer_client,
            )
            return {"resource_name": response.resource_name}

        return ctx.safety.propose(
            tool_name="create_customer_client",
            customer_id=login_customer_id,
            description=description,
            payload={
                "login_customer_id": login_customer_id,
                "descriptive_name": descriptive_name,
                "currency_code": currency_code,
                "time_zone": time_zone,
            },
            execute=execute,
        )

    @mcp.tool()
    def list_manager_links(customer_id: str) -> dict:
        """List the manager (MCC) links for a client account — which MCCs
        have access, and the link status (ACTIVE, PENDING, REFUSED, etc).
        Use this to find a pending invitation's resource_name before
        accepting it, or to audit who has manager access to an account.
        """
        query = """
            SELECT
                customer_manager_link.manager_customer,
                customer_manager_link.manager_link_id,
                customer_manager_link.status
            FROM customer_manager_link
        """
        rows = ctx.client.search(customer_id, query)
        return {"manager_links": rows, "count": len(rows)}

    @mcp.tool()
    def accept_manager_link(customer_id: str, manager_link_resource_name: str) -> dict:
        """Propose accepting a pending manager (MCC) link invitation on a
        client account — the second half of onboarding a client whose
        account already exists and who sent an MCC access invitation
        (rather than one created fresh with create_customer_client).

        Args:
            manager_link_resource_name: From list_manager_links, a link with
                status PENDING.
        """
        client = ctx.client.raw
        operation = client.get_type("CustomerManagerLinkOperation")
        operation.update.resource_name = manager_link_resource_name
        operation.update.status = client.enums.ManagerLinkStatusEnum.ACTIVE
        from google.protobuf import field_mask_pb2

        operation.update_mask.CopyFrom(field_mask_pb2.FieldMask(paths=["status"]))

        description = f"Accept manager link {manager_link_resource_name}"

        def execute():
            return ctx.client.mutate(
                "CustomerManagerLinkService", customer_id, [operation]
            )

        return ctx.safety.propose(
            tool_name="accept_manager_link",
            customer_id=customer_id,
            description=description,
            payload={"manager_link_resource_name": manager_link_resource_name},
            execute=execute,
        )
