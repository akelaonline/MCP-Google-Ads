"""Account discovery & hierarchy tools (read-only)."""

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
