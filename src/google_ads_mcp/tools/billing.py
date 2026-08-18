"""Read-only billing and invoice tools for Google Ads API v25."""

from __future__ import annotations

import calendar

import proto

from ..context import AppContext

_MONTHS = {name.upper() for name in calendar.month_name if name}


def register(mcp, ctx: AppContext) -> None:
    @mcp.tool()
    def list_billing_setups(customer_id: str) -> dict:
        """List billing setups and payments-account metadata for a customer."""
        query = """
            SELECT
                billing_setup.id,
                billing_setup.status,
                billing_setup.payments_account,
                billing_setup.payments_account_info.payments_account_id,
                billing_setup.payments_account_info.payments_account_name,
                billing_setup.payments_account_info.payments_profile_id,
                billing_setup.payments_account_info.payments_profile_name,
                billing_setup.resource_name
            FROM billing_setup
            ORDER BY billing_setup.id DESC
        """
        rows = ctx.client.search(customer_id, query)
        return {"billing_setups": rows, "count": len(rows)}

    @mcp.tool()
    def list_invoices(
        customer_id: str,
        billing_setup_id: str,
        issue_year: int,
        issue_month: str,
        include_granular_details: bool = False,
    ) -> dict:
        """Fetch invoices issued for one billing setup and month."""
        if issue_year < 2019:
            raise ValueError("Google Ads invoice retrieval supports issue_year 2019 or later.")
        month = issue_month.strip().upper()
        if month not in _MONTHS:
            raise ValueError(
                "issue_month must be a full English month name such as JANUARY or DECEMBER."
            )

        customer = ctx.client.assert_customer_allowed(customer_id)
        billing_setup = f"customers/{customer}/billingSetups/{int(billing_setup_id)}"
        service = ctx.client.service("InvoiceService")
        response = service.list_invoices(
            customer_id=customer,
            billing_setup=billing_setup,
            issue_year=str(issue_year),
            issue_month=month,
            include_granular_level_invoice_details=include_granular_details,
        )
        invoices = [
            proto.Message.to_dict(invoice, preserving_proto_field_name=True)
            for invoice in response.invoices
        ]
        return {
            "customer_id": customer,
            "billing_setup_id": str(billing_setup_id),
            "issue_year": issue_year,
            "issue_month": month,
            "include_granular_details": include_granular_details,
            "invoices": invoices,
            "count": len(invoices),
        }
