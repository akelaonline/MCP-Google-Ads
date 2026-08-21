"""Advanced conversion configuration for Google Ads API v25."""

from __future__ import annotations

import re

from google.protobuf import field_mask_pb2

from ..context import AppContext

_TAG_RE = re.compile(r"^[a-z0-9_]+$")
_RULE_DIMENSIONS = {"AUDIENCE", "DEVICE", "GEO_LOCATION", "ITINERARY", "NO_CONDITION"}
_ATTACHMENT_TYPES = {"CUSTOMER", "CAMPAIGN"}


def _owned(ctx: AppContext, customer: str, resource: str, field_name: str) -> str:
    return ctx.client.assert_resource_name_customer(customer, resource, field_name=field_name)


def register(mcp, ctx: AppContext) -> None:
    @mcp.tool()
    def list_conversion_custom_variables(customer_id: str) -> dict:
        """List custom variables available for conversion uploads."""
        rows = ctx.client.search(
            customer_id,
            """
            SELECT conversion_custom_variable.resource_name,
                   conversion_custom_variable.id,
                   conversion_custom_variable.name,
                   conversion_custom_variable.tag,
                   conversion_custom_variable.status,
                   conversion_custom_variable.owner_customer
            FROM conversion_custom_variable
            ORDER BY conversion_custom_variable.name
            """,
        )
        return {"conversion_custom_variables": rows, "count": len(rows)}

    @mcp.tool()
    def create_conversion_custom_variable(
        customer_id: str,
        name: str,
        tag: str,
        validate_only: bool = False,
    ) -> dict:
        """Propose creating a conversion custom variable.

        ``tag`` is immutable after creation and must contain only lowercase
        letters, numbers, and underscores, up to 100 bytes.
        """
        customer = ctx.client.assert_customer_allowed(customer_id)
        clean_name = str(name).strip()
        clean_tag = str(tag).strip()
        if not 1 <= len(clean_name) <= 100 or clean_name != name:
            raise ValueError("name must be trimmed and 1-100 characters.")
        if not clean_tag or len(clean_tag.encode("utf-8")) > 100 or not _TAG_RE.fullmatch(clean_tag):
            raise ValueError("tag must be 1-100 bytes using only lowercase letters, numbers, and underscores.")
        raw = ctx.client.raw
        operation = raw.get_type("ConversionCustomVariableOperation")
        operation.create.name = clean_name
        operation.create.tag = clean_tag

        def execute():
            return ctx.client.mutate(
                "ConversionCustomVariableService",
                customer,
                [operation],
                validate_only=validate_only,
            )

        return ctx.safety.propose(
            tool_name="create_conversion_custom_variable",
            customer_id=customer,
            description=f"Create conversion custom variable '{clean_name}' ({clean_tag})",
            payload={"name": clean_name, "tag": clean_tag, "validate_only": validate_only},
            execute=execute,
        )

    @mcp.tool()
    def update_conversion_custom_variable(
        customer_id: str,
        conversion_custom_variable_resource_name: str,
        name: str | None = None,
        status: str | None = None,
        validate_only: bool = False,
    ) -> dict:
        """Propose renaming or enabling/pausing a conversion custom variable."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        resource = _owned(
            ctx,
            customer,
            conversion_custom_variable_resource_name,
            "conversion_custom_variable_resource_name",
        )
        raw = ctx.client.raw
        operation = raw.get_type("ConversionCustomVariableOperation")
        variable = operation.update
        variable.resource_name = resource
        paths: list[str] = []
        clean_status = None
        if name is not None:
            clean_name = str(name).strip()
            if not 1 <= len(clean_name) <= 100 or clean_name != name:
                raise ValueError("name must be trimmed and 1-100 characters.")
            variable.name = clean_name
            paths.append("name")
        if status is not None:
            clean_status = status.strip().upper()
            if clean_status not in {"ENABLED", "PAUSED"}:
                raise ValueError("status must be ENABLED or PAUSED.")
            variable.status = getattr(raw.enums.ConversionCustomVariableStatusEnum, clean_status)
            paths.append("status")
        if not paths:
            raise ValueError("Provide name and/or status to update.")
        operation.update_mask.CopyFrom(field_mask_pb2.FieldMask(paths=paths))

        def execute():
            return ctx.client.mutate(
                "ConversionCustomVariableService",
                customer,
                [operation],
                validate_only=validate_only,
            )

        return ctx.safety.propose(
            tool_name="update_conversion_custom_variable",
            customer_id=customer,
            description=f"Update conversion custom variable {resource}: {', '.join(paths)}",
            payload={
                "conversion_custom_variable_resource_name": resource,
                "fields": paths,
                "status": clean_status,
                "validate_only": validate_only,
            },
            execute=execute,
        )

    @mcp.tool()
    def list_conversion_value_rule_sets(customer_id: str) -> dict:
        """List conversion value rule sets and their attached rules/scope."""
        rows = ctx.client.search(
            customer_id,
            """
            SELECT conversion_value_rule_set.resource_name,
                   conversion_value_rule_set.id,
                   conversion_value_rule_set.status,
                   conversion_value_rule_set.attachment_type,
                   conversion_value_rule_set.campaign,
                   conversion_value_rule_set.dimensions,
                   conversion_value_rule_set.conversion_action_categories,
                   conversion_value_rule_set.conversion_value_rules,
                   conversion_value_rule_set.owner_customer
            FROM conversion_value_rule_set
            ORDER BY conversion_value_rule_set.id
            """,
        )
        return {"conversion_value_rule_sets": rows, "count": len(rows)}

    @mcp.tool()
    def create_conversion_value_rule_set(
        customer_id: str,
        conversion_value_rule_resource_names: list[str],
        dimensions: list[str],
        attachment_type: str = "CUSTOMER",
        campaign_id: str | None = None,
        conversion_action_categories: list[str] | None = None,
        validate_only: bool = False,
    ) -> dict:
        """Propose creating a conversion value rule set.

        A rule can belong to only one active/paused rule set. Dimensions must
        contain one or two values, except NO_CONDITION which must be used alone.
        """
        customer = ctx.client.assert_customer_allowed(customer_id)
        if not conversion_value_rule_resource_names:
            raise ValueError("Provide at least one conversion value rule resource name.")
        rules = [
            _owned(ctx, customer, value, "conversion_value_rule_resource_names")
            for value in conversion_value_rule_resource_names
        ]
        clean_dimensions = [str(value).strip().upper() for value in dimensions]
        if not 1 <= len(clean_dimensions) <= 2:
            raise ValueError("dimensions must contain one or two values.")
        if any(value not in _RULE_DIMENSIONS for value in clean_dimensions):
            raise ValueError(f"dimensions values must be in {sorted(_RULE_DIMENSIONS)}.")
        if len(set(clean_dimensions)) != len(clean_dimensions):
            raise ValueError("dimensions must not contain duplicates.")
        if "NO_CONDITION" in clean_dimensions and len(clean_dimensions) != 1:
            raise ValueError("NO_CONDITION must be the only dimension when used.")
        attach = attachment_type.strip().upper()
        if attach not in _ATTACHMENT_TYPES:
            raise ValueError(f"attachment_type must be one of {sorted(_ATTACHMENT_TYPES)}.")
        if attach == "CAMPAIGN" and campaign_id is None:
            raise ValueError("campaign_id is required for CAMPAIGN attachment_type.")
        if attach == "CUSTOMER" and campaign_id is not None:
            raise ValueError("campaign_id must be omitted for CUSTOMER attachment_type.")

        raw = ctx.client.raw
        categories: list[str] = []
        for value in conversion_action_categories or []:
            category = str(value).strip().upper()
            # Enum lookup validates against the current v25 client contract.
            getattr(raw.enums.ConversionActionCategoryEnum, category)
            categories.append(category)
        if "NO_CONDITION" in clean_dimensions and (
            len(categories) != 1 or categories[0] not in {"STORE_VISIT", "STORE_SALE"}
        ):
            raise ValueError(
                "NO_CONDITION requires exactly one conversion_action_category: STORE_VISIT or STORE_SALE."
            )

        operation = raw.get_type("ConversionValueRuleSetOperation")
        rule_set = operation.create
        rule_set.attachment_type = getattr(raw.enums.ValueRuleSetAttachmentTypeEnum, attach)
        rule_set.conversion_value_rules.extend(rules)
        rule_set.dimensions.extend(
            getattr(raw.enums.ValueRuleSetDimensionEnum, value)
            for value in clean_dimensions
        )
        rule_set.conversion_action_categories.extend(
            getattr(raw.enums.ConversionActionCategoryEnum, value)
            for value in categories
        )
        campaign_resource = None
        if campaign_id is not None:
            campaign = str(campaign_id).strip()
            if not campaign.isdigit() or int(campaign) <= 0:
                raise ValueError("campaign_id must be a positive numeric ID.")
            campaign_resource = f"customers/{customer}/campaigns/{campaign}"
            rule_set.campaign = campaign_resource

        def execute():
            return ctx.client.mutate(
                "ConversionValueRuleSetService",
                customer,
                [operation],
                validate_only=validate_only,
            )

        return ctx.safety.propose(
            tool_name="create_conversion_value_rule_set",
            customer_id=customer,
            description=f"Create {attach} conversion value rule set with {len(rules)} rule(s)",
            payload={
                "conversion_value_rule_resource_names": rules,
                "dimensions": clean_dimensions,
                "attachment_type": attach,
                "campaign": campaign_resource,
                "conversion_action_categories": categories,
                "validate_only": validate_only,
            },
            execute=execute,
        )

    @mcp.tool()
    def update_conversion_value_rule_set_rules(
        customer_id: str,
        conversion_value_rule_set_resource_name: str,
        conversion_value_rule_resource_names: list[str],
        validate_only: bool = False,
    ) -> dict:
        """Propose replacing the complete rule membership of a value rule set."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        resource = _owned(
            ctx,
            customer,
            conversion_value_rule_set_resource_name,
            "conversion_value_rule_set_resource_name",
        )
        if not conversion_value_rule_resource_names:
            raise ValueError("A value rule set must reference at least one rule.")
        rules = [
            _owned(ctx, customer, value, "conversion_value_rule_resource_names")
            for value in conversion_value_rule_resource_names
        ]
        raw = ctx.client.raw
        operation = raw.get_type("ConversionValueRuleSetOperation")
        operation.update.resource_name = resource
        operation.update.conversion_value_rules.extend(rules)
        operation.update_mask.CopyFrom(
            field_mask_pb2.FieldMask(paths=["conversion_value_rules"])
        )

        def execute():
            return ctx.client.mutate(
                "ConversionValueRuleSetService",
                customer,
                [operation],
                validate_only=validate_only,
            )

        return ctx.safety.propose(
            tool_name="update_conversion_value_rule_set_rules",
            customer_id=customer,
            description=f"Replace rule membership for conversion value rule set {resource}",
            payload={
                "conversion_value_rule_set_resource_name": resource,
                "conversion_value_rule_resource_names": rules,
                "validate_only": validate_only,
            },
            execute=execute,
        )

    @mcp.tool()
    def remove_conversion_value_rule_set(
        customer_id: str,
        conversion_value_rule_set_resource_name: str,
        validate_only: bool = False,
    ) -> dict:
        """Propose permanently removing a conversion value rule set."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        resource = _owned(
            ctx,
            customer,
            conversion_value_rule_set_resource_name,
            "conversion_value_rule_set_resource_name",
        )
        operation = ctx.client.raw.get_type("ConversionValueRuleSetOperation")
        operation.remove = resource

        def execute():
            return ctx.client.mutate(
                "ConversionValueRuleSetService",
                customer,
                [operation],
                validate_only=validate_only,
            )

        return ctx.safety.propose(
            tool_name="remove_conversion_value_rule_set",
            customer_id=customer,
            description=f"Remove conversion value rule set {resource}",
            payload={"conversion_value_rule_set_resource_name": resource, "validate_only": validate_only},
            execute=execute,
        )
