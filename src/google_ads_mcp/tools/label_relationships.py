"""Label relationships missing from the core label module (Google Ads API v25)."""

from __future__ import annotations

from ..context import AppContext


def _id(value: str, field_name: str) -> str:
    text = str(value).strip()
    if not text.isdigit() or int(text) <= 0:
        raise ValueError(f"{field_name} must be a positive numeric ID.")
    return text


def register(mcp, ctx: AppContext) -> None:
    @mcp.tool()
    def list_customer_labels(customer_id: str) -> dict:
        """List manager/customer label relationships visible for one customer."""
        rows = ctx.client.search(
            customer_id,
            """
            SELECT
                customer_label.resource_name,
                customer_label.customer,
                customer_label.label
            FROM customer_label
            ORDER BY customer_label.resource_name
            """,
        )
        return {"customer_labels": rows, "count": len(rows)}

    @mcp.tool()
    def attach_label_to_customer(
        customer_id: str,
        label_id: str,
        validate_only: bool = False,
    ) -> dict:
        """Propose attaching a manager-owned label to a client customer."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        label = _id(label_id, "label_id")
        raw = ctx.client.raw
        operation = raw.get_type("CustomerLabelOperation")
        # CustomerLabel's relationship key is encoded in its resource name.
        operation.create.resource_name = f"customers/{customer}/customerLabels/{label}"

        def execute():
            return ctx.client.mutate(
                "CustomerLabelService", customer, [operation], validate_only=validate_only
            )

        return ctx.safety.propose(
            tool_name="attach_label_to_customer",
            customer_id=customer,
            description=f"Attach label {label} to customer {customer}",
            payload={"label_id": label, "validate_only": validate_only},
            execute=execute,
        )

    @mcp.tool()
    def remove_label_from_customer(
        customer_id: str,
        label_id: str,
        validate_only: bool = False,
    ) -> dict:
        """Propose removing a manager/customer label relationship."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        label = _id(label_id, "label_id")
        operation = ctx.client.raw.get_type("CustomerLabelOperation")
        operation.remove = f"customers/{customer}/customerLabels/{label}"

        def execute():
            return ctx.client.mutate(
                "CustomerLabelService", customer, [operation], validate_only=validate_only
            )

        return ctx.safety.propose(
            tool_name="remove_label_from_customer",
            customer_id=customer,
            description=f"Remove label {label} from customer {customer}",
            payload={"label_id": label, "validate_only": validate_only},
            execute=execute,
        )

    @mcp.tool()
    def list_ad_group_ad_labels(
        customer_id: str,
        ad_group_id: str | None = None,
        ad_id: str | None = None,
    ) -> dict:
        """List labels attached to ads."""
        where = []
        if ad_group_id is not None:
            where.append(f"ad_group.id = {_id(ad_group_id, 'ad_group_id')}")
        if ad_id is not None:
            where.append(f"ad_group_ad.ad.id = {_id(ad_id, 'ad_id')}")
        clause = "WHERE " + " AND ".join(where) if where else ""
        rows = ctx.client.search(
            customer_id,
            f"""
            SELECT
                ad_group_ad_label.resource_name,
                ad_group_ad_label.ad_group_ad,
                ad_group_ad_label.label
            FROM ad_group_ad_label
            {clause}
            ORDER BY ad_group_ad_label.resource_name
            """,
        )
        return {"ad_group_ad_labels": rows, "count": len(rows)}

    @mcp.tool()
    def attach_label_to_ad(
        customer_id: str,
        ad_group_id: str,
        ad_id: str,
        label_id: str,
        validate_only: bool = False,
    ) -> dict:
        """Propose attaching an existing label to an ad."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        ag = _id(ad_group_id, "ad_group_id")
        ad = _id(ad_id, "ad_id")
        label = _id(label_id, "label_id")
        raw = ctx.client.raw
        operation = raw.get_type("AdGroupAdLabelOperation")
        relation = operation.create
        relation.ad_group_ad = f"customers/{customer}/adGroupAds/{ag}~{ad}"
        relation.label = f"customers/{customer}/labels/{label}"

        def execute():
            return ctx.client.mutate(
                "AdGroupAdLabelService", customer, [operation], validate_only=validate_only
            )

        return ctx.safety.propose(
            tool_name="attach_label_to_ad",
            customer_id=customer,
            description=f"Attach label {label} to ad {ag}~{ad}",
            payload={"ad_group_id": ag, "ad_id": ad, "label_id": label, "validate_only": validate_only},
            execute=execute,
        )

    @mcp.tool()
    def remove_label_from_ad(
        customer_id: str,
        ad_group_id: str,
        ad_id: str,
        label_id: str,
        validate_only: bool = False,
    ) -> dict:
        """Propose removing a label from an ad."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        ag = _id(ad_group_id, "ad_group_id")
        ad = _id(ad_id, "ad_id")
        label = _id(label_id, "label_id")
        operation = ctx.client.raw.get_type("AdGroupAdLabelOperation")
        operation.remove = f"customers/{customer}/adGroupAdLabels/{ag}~{ad}~{label}"

        def execute():
            return ctx.client.mutate(
                "AdGroupAdLabelService", customer, [operation], validate_only=validate_only
            )

        return ctx.safety.propose(
            tool_name="remove_label_from_ad",
            customer_id=customer,
            description=f"Remove label {label} from ad {ag}~{ad}",
            payload={"ad_group_id": ag, "ad_id": ad, "label_id": label, "validate_only": validate_only},
            execute=execute,
        )

    @mcp.tool()
    def list_ad_group_criterion_labels(
        customer_id: str,
        ad_group_id: str | None = None,
        criterion_id: str | None = None,
    ) -> dict:
        """List labels attached to keywords or other ad-group criteria."""
        where = []
        if ad_group_id is not None:
            where.append(f"ad_group.id = {_id(ad_group_id, 'ad_group_id')}")
        if criterion_id is not None:
            where.append(
                f"ad_group_criterion.criterion_id = {_id(criterion_id, 'criterion_id')}"
            )
        clause = "WHERE " + " AND ".join(where) if where else ""
        rows = ctx.client.search(
            customer_id,
            f"""
            SELECT
                ad_group_criterion_label.resource_name,
                ad_group_criterion_label.ad_group_criterion,
                ad_group_criterion_label.label
            FROM ad_group_criterion_label
            {clause}
            ORDER BY ad_group_criterion_label.resource_name
            """,
        )
        return {"ad_group_criterion_labels": rows, "count": len(rows)}

    @mcp.tool()
    def attach_label_to_ad_group_criterion(
        customer_id: str,
        ad_group_id: str,
        criterion_id: str,
        label_id: str,
        validate_only: bool = False,
    ) -> dict:
        """Propose attaching a label to a keyword or other ad-group criterion."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        ag = _id(ad_group_id, "ad_group_id")
        criterion = _id(criterion_id, "criterion_id")
        label = _id(label_id, "label_id")
        raw = ctx.client.raw
        operation = raw.get_type("AdGroupCriterionLabelOperation")
        relation = operation.create
        relation.ad_group_criterion = f"customers/{customer}/adGroupCriteria/{ag}~{criterion}"
        relation.label = f"customers/{customer}/labels/{label}"

        def execute():
            return ctx.client.mutate(
                "AdGroupCriterionLabelService", customer, [operation], validate_only=validate_only
            )

        return ctx.safety.propose(
            tool_name="attach_label_to_ad_group_criterion",
            customer_id=customer,
            description=f"Attach label {label} to criterion {ag}~{criterion}",
            payload={"ad_group_id": ag, "criterion_id": criterion, "label_id": label, "validate_only": validate_only},
            execute=execute,
        )

    @mcp.tool()
    def remove_label_from_ad_group_criterion(
        customer_id: str,
        ad_group_id: str,
        criterion_id: str,
        label_id: str,
        validate_only: bool = False,
    ) -> dict:
        """Propose removing a label from a keyword or other ad-group criterion."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        ag = _id(ad_group_id, "ad_group_id")
        criterion = _id(criterion_id, "criterion_id")
        label = _id(label_id, "label_id")
        operation = ctx.client.raw.get_type("AdGroupCriterionLabelOperation")
        operation.remove = (
            f"customers/{customer}/adGroupCriterionLabels/{ag}~{criterion}~{label}"
        )

        def execute():
            return ctx.client.mutate(
                "AdGroupCriterionLabelService", customer, [operation], validate_only=validate_only
            )

        return ctx.safety.propose(
            tool_name="remove_label_from_ad_group_criterion",
            customer_id=customer,
            description=f"Remove label {label} from criterion {ag}~{criterion}",
            payload={"ad_group_id": ag, "criterion_id": criterion, "label_id": label, "validate_only": validate_only},
            execute=execute,
        )
