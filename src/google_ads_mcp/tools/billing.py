"""Billing, payments-account, account-budget, and invoice tools for API v25."""

from __future__ import annotations

from datetime import datetime

import proto
from google.protobuf import field_mask_pb2

from ..client import micros
from ..context import AppContext
from ..errors import GoogleAdsMcpError, format_google_ads_exception

_MONTHS = {
    "JANUARY",
    "FEBRUARY",
    "MARCH",
    "APRIL",
    "MAY",
    "JUNE",
    "JULY",
    "AUGUST",
    "SEPTEMBER",
    "OCTOBER",
    "NOVEMBER",
    "DECEMBER",
}


def _date_time(value: str | None, field_name: str) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    accepted = ("%Y-%m-%d", "%Y-%m-%d %H:%M:%S")
    if not any(_try_parse(text, fmt) for fmt in accepted):
        raise ValueError(
            f"{field_name} must use YYYY-MM-DD or YYYY-MM-DD HH:MM:SS in the "
            "Google Ads customer's time zone."
        )
    return text


def _try_parse(value: str, fmt: str) -> bool:
    try:
        datetime.strptime(value, fmt)
        return True
    except ValueError:
        return False


def _payments_account_id(value: str) -> str:
    text = str(value).strip()
    digits = text.replace("-", "")
    if len(digits) != 16 or not digits.isdigit():
        raise ValueError(
            "payments_account_id must contain 16 digits, normally formatted "
            "1234-5678-9012-3456."
        )
    return f"{digits[0:4]}-{digits[4:8]}-{digits[8:12]}-{digits[12:16]}"


def _payments_profile_id(value: str) -> str:
    text = str(value).strip()
    digits = text.replace("-", "")
    if len(digits) != 12 or not digits.isdigit():
        raise ValueError(
            "payments_profile_id must contain 12 digits, normally formatted "
            "1234-5678-9012."
        )
    return f"{digits[0:4]}-{digits[4:8]}-{digits[8:12]}"


def _proposal_result(response) -> dict:
    result = getattr(response, "result", None)
    return {
        "resource_name": getattr(result, "resource_name", None),
    }


def register(mcp, ctx: AppContext) -> None:
    @mcp.tool()
    def list_payments_accounts(customer_id: str) -> dict:
        """List payments accounts usable by this customer/manager hierarchy."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        service = ctx.client.service("PaymentsAccountService")
        from google.ads.googleads.errors import GoogleAdsException

        try:
            response = service.list_payments_accounts(customer_id=customer)
        except GoogleAdsException as ex:
            raise GoogleAdsMcpError(format_google_ads_exception(ex)) from ex
        accounts = [
            proto.Message.to_dict(item, preserving_proto_field_name=True)
            for item in response.payments_accounts
        ]
        return {"payments_accounts": accounts, "count": len(accounts)}

    @mcp.tool()
    def list_billing_setups(customer_id: str) -> dict:
        """List billing setups and payments-account metadata for a customer."""
        query = """
            SELECT
                billing_setup.id,
                billing_setup.status,
                billing_setup.start_date_time,
                billing_setup.start_time_type,
                billing_setup.end_date_time,
                billing_setup.end_time_type,
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
    def create_billing_setup_with_payments_account(
        customer_id: str,
        payments_account_id: str,
        start_date_time: str | None = None,
    ) -> dict:
        """Propose linking an existing accessible Payments account.

        This billing workflow is available for accounts configured for monthly
        invoicing. ``payments_account_id`` can be discovered with
        ``list_payments_accounts``. If start_date_time is omitted, NOW is used.
        """
        customer = ctx.client.assert_customer_allowed(customer_id)
        payment_id = _payments_account_id(payments_account_id)
        start = _date_time(start_date_time, "start_date_time")
        raw = ctx.client.raw
        operation = raw.get_type("BillingSetupOperation")
        setup = operation.create
        setup.payments_account = raw.get_service(
            "PaymentsAccountService"
        ).payments_account_path(customer, payment_id)
        if start:
            setup.start_date_time = start
        else:
            setup.start_time_type = raw.enums.TimeTypeEnum.NOW

        def execute():
            return ctx.client.mutate(
                "BillingSetupService",
                customer,
                [operation],
                operations_field="operation",
            )

        return ctx.safety.propose(
            tool_name="create_billing_setup",
            customer_id=customer,
            description=(
                f"Link Payments account {payment_id} to customer {customer}"
                + (f" starting {start}" if start else " starting NOW")
            ),
            payload={
                "payments_account_id": payment_id,
                "start_date_time": start,
            },
            execute=execute,
        )

    @mcp.tool()
    def create_billing_setup_with_new_payments_account(
        customer_id: str,
        payments_profile_id: str,
        payments_account_name: str,
        start_date_time: str | None = None,
    ) -> dict:
        """Propose creating a Payments account under a profile and linking billing."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        profile_id = _payments_profile_id(payments_profile_id)
        name = str(payments_account_name).strip()
        if not name:
            raise ValueError("payments_account_name must not be empty.")
        start = _date_time(start_date_time, "start_date_time")
        raw = ctx.client.raw
        operation = raw.get_type("BillingSetupOperation")
        setup = operation.create
        setup.payments_account_info.payments_profile_id = profile_id
        setup.payments_account_info.payments_account_name = name
        if start:
            setup.start_date_time = start
        else:
            setup.start_time_type = raw.enums.TimeTypeEnum.NOW

        def execute():
            return ctx.client.mutate(
                "BillingSetupService",
                customer,
                [operation],
                operations_field="operation",
            )

        return ctx.safety.propose(
            tool_name="create_billing_setup",
            customer_id=customer,
            description=(
                f"Create Payments account '{name}' under profile {profile_id} and "
                f"link it to customer {customer}"
            ),
            payload={
                "payments_profile_id": profile_id,
                "payments_account_name": name,
                "start_date_time": start,
            },
            execute=execute,
        )

    @mcp.tool()
    def cancel_pending_billing_setup(
        customer_id: str,
        billing_setup_resource_name: str,
    ) -> dict:
        """Propose canceling a pending/future billing setup."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        resource = ctx.client.assert_resource_name_customer(
            customer,
            billing_setup_resource_name,
            field_name="billing_setup_resource_name",
        )
        raw = ctx.client.raw
        operation = raw.get_type("BillingSetupOperation")
        operation.remove = resource

        def execute():
            return ctx.client.mutate(
                "BillingSetupService",
                customer,
                [operation],
                operations_field="operation",
            )

        return ctx.safety.propose(
            tool_name="cancel_pending_billing_setup",
            customer_id=customer,
            description=f"Cancel pending/future billing setup {resource}",
            payload={"billing_setup_resource_name": resource},
            execute=execute,
        )

    @mcp.tool()
    def list_account_budgets(customer_id: str) -> dict:
        """List account-level budgets, effective values, and pending changes."""
        query = """
            SELECT
                account_budget.resource_name,
                account_budget.id,
                account_budget.name,
                account_budget.status,
                account_budget.billing_setup,
                account_budget.amount_served_micros,
                account_budget.total_adjustments_micros,
                account_budget.purchase_order_number,
                account_budget.notes,
                account_budget.proposed_start_date_time,
                account_budget.approved_start_date_time,
                account_budget.proposed_end_date_time,
                account_budget.proposed_end_time_type,
                account_budget.approved_end_date_time,
                account_budget.approved_end_time_type,
                account_budget.proposed_spending_limit_micros,
                account_budget.proposed_spending_limit_type,
                account_budget.approved_spending_limit_micros,
                account_budget.approved_spending_limit_type,
                account_budget.adjusted_spending_limit_micros,
                account_budget.adjusted_spending_limit_type,
                account_budget.pending_proposal.proposal_type,
                account_budget.pending_proposal.creation_date_time,
                account_budget.pending_proposal.spending_limit_micros,
                account_budget.pending_proposal.spending_limit_type,
                account_budget.pending_proposal.end_date_time,
                account_budget.pending_proposal.end_time_type,
                account_budget.pending_proposal.name,
                account_budget.pending_proposal.purchase_order_number,
                account_budget.pending_proposal.notes
            FROM account_budget
            ORDER BY account_budget.id DESC
        """
        rows = ctx.client.search(customer_id, query)
        return {"account_budgets": rows, "count": len(rows)}

    @mcp.tool()
    def list_account_budget_proposals(customer_id: str) -> dict:
        """List pending, approved, rejected, and cancelled account-budget proposals."""
        query = """
            SELECT
                account_budget_proposal.resource_name,
                account_budget_proposal.id,
                account_budget_proposal.status,
                account_budget_proposal.proposal_type,
                account_budget_proposal.account_budget,
                account_budget_proposal.billing_setup,
                account_budget_proposal.creation_date_time,
                account_budget_proposal.approval_date_time,
                account_budget_proposal.proposed_name,
                account_budget_proposal.proposed_notes,
                account_budget_proposal.proposed_purchase_order_number,
                account_budget_proposal.proposed_start_date_time,
                account_budget_proposal.proposed_end_date_time,
                account_budget_proposal.proposed_end_time_type,
                account_budget_proposal.proposed_spending_limit_micros,
                account_budget_proposal.proposed_spending_limit_type,
                account_budget_proposal.approved_spending_limit_micros,
                account_budget_proposal.approved_spending_limit_type
            FROM account_budget_proposal
            ORDER BY account_budget_proposal.id DESC
        """
        rows = ctx.client.search(customer_id, query)
        return {"account_budget_proposals": rows, "count": len(rows)}

    @mcp.tool()
    def create_account_budget(
        customer_id: str,
        billing_setup_resource_name: str,
        name: str,
        spending_limit: float | None = None,
        infinite_spending_limit: bool = False,
        start_date_time: str | None = None,
        end_date_time: str | None = None,
        notes: str | None = None,
        purchase_order_number: str | None = None,
    ) -> dict:
        """Propose a new account-level budget under a billing setup."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        billing_setup = ctx.client.assert_resource_name_customer(
            customer,
            billing_setup_resource_name,
            field_name="billing_setup_resource_name",
        )
        budget_name = str(name).strip()
        if not budget_name:
            raise ValueError("name must not be empty.")
        if infinite_spending_limit and spending_limit is not None:
            raise ValueError(
                "Choose either spending_limit or infinite_spending_limit, not both."
            )
        if not infinite_spending_limit and spending_limit is None:
            raise ValueError(
                "Provide spending_limit or set infinite_spending_limit=true."
            )
        if spending_limit is not None and spending_limit <= 0:
            raise ValueError("spending_limit must be greater than 0.")
        start = _date_time(start_date_time, "start_date_time")
        end = _date_time(end_date_time, "end_date_time")
        if start and end and end <= start:
            raise ValueError("end_date_time must be later than start_date_time.")

        raw = ctx.client.raw
        operation = raw.get_type("AccountBudgetProposalOperation")
        proposal = operation.create
        proposal.proposal_type = raw.enums.AccountBudgetProposalTypeEnum.CREATE
        proposal.billing_setup = billing_setup
        proposal.proposed_name = budget_name
        if start:
            proposal.proposed_start_date_time = start
        else:
            proposal.proposed_start_time_type = raw.enums.TimeTypeEnum.NOW
        if end:
            proposal.proposed_end_date_time = end
        else:
            proposal.proposed_end_time_type = raw.enums.TimeTypeEnum.FOREVER
        if infinite_spending_limit:
            proposal.proposed_spending_limit_type = raw.enums.SpendingLimitTypeEnum.INFINITE
        else:
            proposal.proposed_spending_limit_micros = micros(float(spending_limit))
        if notes is not None:
            proposal.proposed_notes = notes
        if purchase_order_number is not None:
            proposal.proposed_purchase_order_number = purchase_order_number

        def execute():
            response = ctx.client.mutate(
                "AccountBudgetProposalService",
                customer,
                [operation],
                operations_field="operation",
            )
            return _proposal_result(response)

        return ctx.safety.propose(
            tool_name="create_account_budget",
            customer_id=customer,
            description=(
                f"Create account budget '{budget_name}' for customer {customer} under "
                f"{billing_setup}"
            ),
            payload={
                "billing_setup_resource_name": billing_setup,
                "name": budget_name,
                "spending_limit": spending_limit,
                "infinite_spending_limit": infinite_spending_limit,
                "start_date_time": start,
                "end_date_time": end,
                "notes": notes,
                "purchase_order_number": purchase_order_number,
            },
            execute=execute,
        )

    @mcp.tool()
    def update_account_budget(
        customer_id: str,
        account_budget_resource_name: str,
        spending_limit: float | None = None,
        infinite_spending_limit: bool = False,
        end_date_time: str | None = None,
        end_forever: bool = False,
        name: str | None = None,
        notes: str | None = None,
        purchase_order_number: str | None = None,
    ) -> dict:
        """Propose mutable changes to an existing account-level budget."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        budget = ctx.client.assert_resource_name_customer(
            customer,
            account_budget_resource_name,
            field_name="account_budget_resource_name",
        )
        if spending_limit is not None and spending_limit <= 0:
            raise ValueError("spending_limit must be greater than 0.")
        if spending_limit is not None and infinite_spending_limit:
            raise ValueError(
                "Choose either spending_limit or infinite_spending_limit, not both."
            )
        if end_date_time is not None and end_forever:
            raise ValueError("Choose either end_date_time or end_forever, not both.")
        end = _date_time(end_date_time, "end_date_time")

        raw = ctx.client.raw
        operation = raw.get_type("AccountBudgetProposalOperation")
        proposal = operation.create
        proposal.proposal_type = raw.enums.AccountBudgetProposalTypeEnum.UPDATE
        proposal.account_budget = budget
        mask: list[str] = []
        if spending_limit is not None:
            proposal.proposed_spending_limit_micros = micros(spending_limit)
            mask.append("proposed_spending_limit")
        elif infinite_spending_limit:
            proposal.proposed_spending_limit_type = raw.enums.SpendingLimitTypeEnum.INFINITE
            mask.append("proposed_spending_limit")
        if end is not None:
            proposal.proposed_end_date_time = end
            mask.append("proposed_end_time")
        elif end_forever:
            proposal.proposed_end_time_type = raw.enums.TimeTypeEnum.FOREVER
            mask.append("proposed_end_time")
        if name is not None:
            clean_name = name.strip()
            if not clean_name:
                raise ValueError("name must not be empty when supplied.")
            proposal.proposed_name = clean_name
            mask.append("proposed_name")
        if notes is not None:
            proposal.proposed_notes = notes
            mask.append("proposed_notes")
        if purchase_order_number is not None:
            proposal.proposed_purchase_order_number = purchase_order_number
            mask.append("proposed_purchase_order_number")
        if not mask:
            raise ValueError("Provide at least one account-budget field to update.")
        operation.update_mask.CopyFrom(field_mask_pb2.FieldMask(paths=mask))

        def execute():
            response = ctx.client.mutate(
                "AccountBudgetProposalService",
                customer,
                [operation],
                operations_field="operation",
            )
            return _proposal_result(response)

        return ctx.safety.propose(
            tool_name="update_account_budget",
            customer_id=customer,
            description=f"Update account budget {budget}: {', '.join(mask)}",
            payload={
                "account_budget_resource_name": budget,
                "fields": mask,
                "spending_limit": spending_limit,
                "infinite_spending_limit": infinite_spending_limit,
                "end_date_time": end,
                "end_forever": end_forever,
                "name": name,
                "notes": notes,
                "purchase_order_number": purchase_order_number,
            },
            execute=execute,
        )

    @mcp.tool()
    def end_account_budget(
        customer_id: str,
        account_budget_resource_name: str,
    ) -> dict:
        """Propose ending an active account budget immediately."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        budget = ctx.client.assert_resource_name_customer(
            customer,
            account_budget_resource_name,
            field_name="account_budget_resource_name",
        )
        raw = ctx.client.raw
        operation = raw.get_type("AccountBudgetProposalOperation")
        operation.create.proposal_type = raw.enums.AccountBudgetProposalTypeEnum.END
        operation.create.account_budget = budget

        def execute():
            response = ctx.client.mutate(
                "AccountBudgetProposalService",
                customer,
                [operation],
                operations_field="operation",
            )
            return _proposal_result(response)

        return ctx.safety.propose(
            tool_name="end_account_budget",
            customer_id=customer,
            description=f"END active account budget {budget} immediately",
            payload={"account_budget_resource_name": budget},
            execute=execute,
        )

    @mcp.tool()
    def remove_future_account_budget(
        customer_id: str,
        account_budget_resource_name: str,
    ) -> dict:
        """Propose removing an approved account budget before its future start."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        budget = ctx.client.assert_resource_name_customer(
            customer,
            account_budget_resource_name,
            field_name="account_budget_resource_name",
        )
        raw = ctx.client.raw
        operation = raw.get_type("AccountBudgetProposalOperation")
        operation.create.proposal_type = raw.enums.AccountBudgetProposalTypeEnum.REMOVE
        operation.create.account_budget = budget

        def execute():
            response = ctx.client.mutate(
                "AccountBudgetProposalService",
                customer,
                [operation],
                operations_field="operation",
            )
            return _proposal_result(response)

        return ctx.safety.propose(
            tool_name="remove_future_account_budget",
            customer_id=customer,
            description=f"Remove future account budget {budget} before it starts",
            payload={"account_budget_resource_name": budget},
            execute=execute,
        )

    @mcp.tool()
    def cancel_pending_account_budget_proposal(
        customer_id: str,
        proposal_resource_name: str,
    ) -> dict:
        """Propose cancelling a still-pending AccountBudgetProposal."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        resource = ctx.client.assert_resource_name_customer(
            customer,
            proposal_resource_name,
            field_name="proposal_resource_name",
        )
        raw = ctx.client.raw
        operation = raw.get_type("AccountBudgetProposalOperation")
        operation.remove = resource

        def execute():
            response = ctx.client.mutate(
                "AccountBudgetProposalService",
                customer,
                [operation],
                operations_field="operation",
            )
            return _proposal_result(response)

        return ctx.safety.propose(
            tool_name="cancel_pending_account_budget_proposal",
            customer_id=customer,
            description=f"Cancel pending account-budget proposal {resource}",
            payload={"proposal_resource_name": resource},
            execute=execute,
        )

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
            issue_month=ctx.client.raw.enums.MonthOfYearEnum[month].value,
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
