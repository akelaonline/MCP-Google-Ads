"""Conversion-goal and lifecycle-goal management for Google Ads API v25.

Google Ads API v25 removed the legacy CustomerLifecycleGoalService and
CampaignLifecycleGoalService. Lifecycle configuration now lives in GoalService
and CampaignGoalConfigService. This module intentionally uses only v25
contracts so the MCP cannot advertise stale lifecycle tools.
"""

from __future__ import annotations

from typing import Any

from google.protobuf import field_mask_pb2

from ..context import AppContext

_GOAL_TYPES = {
    "NEW_CUSTOMER_ACQUISITION": "new_customer_acquisition_goal_settings",
    "CUSTOMER_RETENTION": "retention_goal_settings",
    "LOYALTY_RETENTION": "loyalty_retention_goal_settings",
}
_CAMPAIGN_GOAL_SETTINGS = {
    "NEW_CUSTOMER_ACQUISITION": "campaign_new_customer_acquisition_settings",
    "CUSTOMER_RETENTION": "campaign_retention_settings",
    "LOYALTY_RETENTION": "campaign_loyalty_retention_settings",
}
_LIFECYCLE_TARGET_OPTIONS = {
    "TARGET_ALL",
    "BID_HIGHER_FOR_ALL",
    "TARGET_SPECIFIC",
    "BID_HIGHER_FOR_SPECIFIC",
    "EXCLUDE_SPECIFIC",
}


def _resource(
    ctx: AppContext,
    customer_id: str,
    value: str,
    field_name: str,
) -> tuple[str, str]:
    customer = ctx.client.assert_customer_allowed(customer_id)
    resource = ctx.client.assert_resource_name_customer(
        customer, value, field_name=field_name
    )
    return customer, resource


def _goal_type(value: str) -> str:
    clean = str(value).strip().upper()
    if clean not in _GOAL_TYPES:
        raise ValueError(
            "goal_type must be NEW_CUSTOMER_ACQUISITION, CUSTOMER_RETENTION, "
            "or LOYALTY_RETENTION."
        )
    return clean


def _value_mode(value: str) -> str:
    clean = str(value).strip().upper()
    if clean not in {"ADDITIONAL", "MULTIPLIER"}:
        raise ValueError("value_mode must be ADDITIONAL or MULTIPLIER.")
    return clean


def _set_lifecycle_value_settings(
    value_settings: Any,
    *,
    value_mode: str,
    value: float,
    high_lifetime_value: float | None,
) -> list[str]:
    mode = _value_mode(value_mode)
    if value < 0:
        raise ValueError("value must be zero or greater.")
    if high_lifetime_value is not None and high_lifetime_value < 0:
        raise ValueError("high_lifetime_value must be zero or greater.")
    if high_lifetime_value is not None and high_lifetime_value < value:
        raise ValueError("high_lifetime_value must be greater than or equal to value.")

    if mode == "ADDITIONAL":
        value_settings.additional_value = value
        paths = ["additional_value"]
        if high_lifetime_value is not None:
            value_settings.additional_high_lifetime_value = high_lifetime_value
            paths.append("additional_high_lifetime_value")
        return paths

    value_settings.value_multiplier = value
    paths = ["value_multiplier"]
    if high_lifetime_value is not None:
        value_settings.high_lifetime_value_multiplier = high_lifetime_value
        paths.append("high_lifetime_value_multiplier")
    return paths


def _escape_gaql(value: str) -> str:
    return value.replace("\\", "\\\\").replace("'", "\\'")


def register(mcp, ctx: AppContext) -> None:
    @mcp.tool()
    def list_customer_conversion_goals(customer_id: str) -> dict:
        """List account-level category/origin conversion goals and biddability."""
        rows = ctx.client.search(
            customer_id,
            """
            SELECT
                customer_conversion_goal.resource_name,
                customer_conversion_goal.category,
                customer_conversion_goal.origin,
                customer_conversion_goal.biddable
            FROM customer_conversion_goal
            ORDER BY customer_conversion_goal.category, customer_conversion_goal.origin
            """,
        )
        return {"customer_conversion_goals": rows, "count": len(rows)}

    @mcp.tool()
    def set_customer_conversion_goal_biddable(
        customer_id: str,
        customer_conversion_goal_resource_name: str,
        biddable: bool,
        validate_only: bool = False,
    ) -> dict:
        """Propose changing account-level biddability for one category/origin goal."""
        customer, resource = _resource(
            ctx,
            customer_id,
            customer_conversion_goal_resource_name,
            "customer_conversion_goal_resource_name",
        )
        raw = ctx.client.raw
        operation = raw.get_type("CustomerConversionGoalOperation")
        operation.update.resource_name = resource
        operation.update.biddable = bool(biddable)
        operation.update_mask.CopyFrom(field_mask_pb2.FieldMask(paths=["biddable"]))

        def execute():
            return ctx.client.mutate(
                "CustomerConversionGoalService",
                customer,
                [operation],
                validate_only=validate_only,
            )

        return ctx.safety.propose(
            tool_name="set_customer_conversion_goal_biddable",
            customer_id=customer,
            description=f"Set customer conversion goal {resource} biddable={bool(biddable)}",
            payload={
                "customer_conversion_goal_resource_name": resource,
                "biddable": bool(biddable),
                "validate_only": bool(validate_only),
            },
            execute=execute,
        )

    @mcp.tool()
    def list_campaign_conversion_goals(
        customer_id: str,
        campaign_id: str | None = None,
    ) -> dict:
        """List campaign-specific category/origin conversion goal overrides."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        where = ""
        if campaign_id is not None:
            campaign = str(campaign_id).strip()
            if not campaign.isdigit():
                raise ValueError("campaign_id must be numeric.")
            where = (
                "WHERE campaign_conversion_goal.campaign = "
                f"'customers/{customer}/campaigns/{campaign}'"
            )
        rows = ctx.client.search(
            customer,
            f"""
            SELECT
                campaign_conversion_goal.resource_name,
                campaign_conversion_goal.campaign,
                campaign_conversion_goal.category,
                campaign_conversion_goal.origin,
                campaign_conversion_goal.biddable
            FROM campaign_conversion_goal
            {where}
            ORDER BY campaign_conversion_goal.campaign,
                     campaign_conversion_goal.category,
                     campaign_conversion_goal.origin
            """,
        )
        return {"campaign_conversion_goals": rows, "count": len(rows)}

    @mcp.tool()
    def set_campaign_conversion_goal_biddable(
        customer_id: str,
        campaign_conversion_goal_resource_name: str,
        biddable: bool,
        validate_only: bool = False,
    ) -> dict:
        """Propose changing biddability for one campaign category/origin goal."""
        customer, resource = _resource(
            ctx,
            customer_id,
            campaign_conversion_goal_resource_name,
            "campaign_conversion_goal_resource_name",
        )
        raw = ctx.client.raw
        operation = raw.get_type("CampaignConversionGoalOperation")
        operation.update.resource_name = resource
        operation.update.biddable = bool(biddable)
        operation.update_mask.CopyFrom(field_mask_pb2.FieldMask(paths=["biddable"]))

        def execute():
            return ctx.client.mutate(
                "CampaignConversionGoalService",
                customer,
                [operation],
                validate_only=validate_only,
            )

        return ctx.safety.propose(
            tool_name="set_campaign_conversion_goal_biddable",
            customer_id=customer,
            description=f"Set campaign conversion goal {resource} biddable={bool(biddable)}",
            payload={
                "campaign_conversion_goal_resource_name": resource,
                "biddable": bool(biddable),
                "validate_only": bool(validate_only),
            },
            execute=execute,
        )

    @mcp.tool()
    def list_custom_conversion_goals(customer_id: str) -> dict:
        """List custom conversion goals and their conversion actions."""
        rows = ctx.client.search(
            customer_id,
            """
            SELECT
                custom_conversion_goal.resource_name,
                custom_conversion_goal.id,
                custom_conversion_goal.name,
                custom_conversion_goal.status,
                custom_conversion_goal.conversion_actions
            FROM custom_conversion_goal
            ORDER BY custom_conversion_goal.name
            """,
        )
        return {"custom_conversion_goals": rows, "count": len(rows)}

    @mcp.tool()
    def create_custom_conversion_goal(
        customer_id: str,
        name: str,
        conversion_action_resource_names: list[str],
        validate_only: bool = False,
    ) -> dict:
        """Propose creating an ENABLED custom conversion goal."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        clean_name = str(name).strip()
        if not clean_name:
            raise ValueError("name must not be empty.")
        if not conversion_action_resource_names:
            raise ValueError("Provide at least one conversion_action_resource_name.")
        actions = [
            ctx.client.assert_resource_name_customer(
                customer, value, field_name="conversion_action_resource_names"
            )
            for value in conversion_action_resource_names
        ]
        raw = ctx.client.raw
        operation = raw.get_type("CustomConversionGoalOperation")
        goal = operation.create
        goal.name = clean_name
        goal.status = raw.enums.CustomConversionGoalStatusEnum.ENABLED
        goal.conversion_actions.extend(actions)

        def execute():
            return ctx.client.mutate(
                "CustomConversionGoalService",
                customer,
                [operation],
                validate_only=validate_only,
            )

        return ctx.safety.propose(
            tool_name="create_custom_conversion_goal",
            customer_id=customer,
            description=f"Create custom conversion goal '{clean_name}' with {len(actions)} action(s)",
            payload={
                "name": clean_name,
                "conversion_action_count": len(actions),
                "validate_only": bool(validate_only),
            },
            execute=execute,
        )

    @mcp.tool()
    def update_custom_conversion_goal(
        customer_id: str,
        custom_conversion_goal_resource_name: str,
        name: str | None = None,
        conversion_action_resource_names: list[str] | None = None,
        status: str | None = None,
        validate_only: bool = False,
    ) -> dict:
        """Propose updating name, action membership, or status of a custom goal."""
        customer, resource = _resource(
            ctx,
            customer_id,
            custom_conversion_goal_resource_name,
            "custom_conversion_goal_resource_name",
        )
        raw = ctx.client.raw
        operation = raw.get_type("CustomConversionGoalOperation")
        goal = operation.update
        goal.resource_name = resource
        paths: list[str] = []
        if name is not None:
            clean_name = name.strip()
            if not clean_name:
                raise ValueError("name must not be empty when supplied.")
            goal.name = clean_name
            paths.append("name")
        if conversion_action_resource_names is not None:
            if not conversion_action_resource_names:
                raise ValueError("conversion_action_resource_names must not be empty.")
            actions = [
                ctx.client.assert_resource_name_customer(
                    customer, value, field_name="conversion_action_resource_names"
                )
                for value in conversion_action_resource_names
            ]
            goal.conversion_actions.extend(actions)
            paths.append("conversion_actions")
        if status is not None:
            clean_status = status.strip().upper()
            if clean_status not in {"ENABLED", "REMOVED"}:
                raise ValueError("status must be ENABLED or REMOVED.")
            goal.status = getattr(raw.enums.CustomConversionGoalStatusEnum, clean_status)
            paths.append("status")
        if not paths:
            raise ValueError("Provide at least one field to update.")
        operation.update_mask.CopyFrom(field_mask_pb2.FieldMask(paths=paths))

        def execute():
            return ctx.client.mutate(
                "CustomConversionGoalService",
                customer,
                [operation],
                validate_only=validate_only,
            )

        return ctx.safety.propose(
            tool_name="update_custom_conversion_goal",
            customer_id=customer,
            description=f"Update custom conversion goal {resource}: {', '.join(paths)}",
            payload={
                "custom_conversion_goal_resource_name": resource,
                "fields": paths,
                "status": status,
                "validate_only": bool(validate_only),
            },
            execute=execute,
        )

    @mcp.tool()
    def remove_custom_conversion_goal(
        customer_id: str,
        custom_conversion_goal_resource_name: str,
        validate_only: bool = False,
    ) -> dict:
        """Propose removing a custom conversion goal."""
        customer, resource = _resource(
            ctx,
            customer_id,
            custom_conversion_goal_resource_name,
            "custom_conversion_goal_resource_name",
        )
        raw = ctx.client.raw
        operation = raw.get_type("CustomConversionGoalOperation")
        operation.remove = resource

        def execute():
            return ctx.client.mutate(
                "CustomConversionGoalService",
                customer,
                [operation],
                validate_only=validate_only,
            )

        return ctx.safety.propose(
            tool_name="remove_custom_conversion_goal",
            customer_id=customer,
            description=f"Remove custom conversion goal {resource}",
            payload={
                "custom_conversion_goal_resource_name": resource,
                "validate_only": bool(validate_only),
            },
            execute=execute,
        )

    @mcp.tool()
    def list_conversion_goal_campaign_configs(customer_id: str) -> dict:
        """List whether campaigns use customer/campaign/custom conversion goals."""
        rows = ctx.client.search(
            customer_id,
            """
            SELECT
                conversion_goal_campaign_config.resource_name,
                conversion_goal_campaign_config.campaign,
                conversion_goal_campaign_config.goal_config_level,
                conversion_goal_campaign_config.custom_conversion_goal
            FROM conversion_goal_campaign_config
            ORDER BY conversion_goal_campaign_config.campaign
            """,
        )
        return {"conversion_goal_campaign_configs": rows, "count": len(rows)}

    @mcp.tool()
    def set_conversion_goal_campaign_config(
        customer_id: str,
        campaign_id: str,
        goal_config_level: str,
        custom_conversion_goal_resource_name: str | None = None,
        validate_only: bool = False,
    ) -> dict:
        """Propose switching a campaign between customer and campaign goal config."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        campaign = str(campaign_id).strip()
        if not campaign.isdigit():
            raise ValueError("campaign_id must be numeric.")
        level = str(goal_config_level).strip().upper()
        if level not in {"CUSTOMER", "CAMPAIGN"}:
            raise ValueError("goal_config_level must be CUSTOMER or CAMPAIGN.")
        custom = None
        if custom_conversion_goal_resource_name:
            custom = ctx.client.assert_resource_name_customer(
                customer,
                custom_conversion_goal_resource_name,
                field_name="custom_conversion_goal_resource_name",
            )
            if level != "CAMPAIGN":
                raise ValueError("custom_conversion_goal requires goal_config_level=CAMPAIGN.")
        raw = ctx.client.raw
        operation = raw.get_type("ConversionGoalCampaignConfigOperation")
        config = operation.update
        config.resource_name = f"customers/{customer}/conversionGoalCampaignConfigs/{campaign}"
        config.goal_config_level = getattr(raw.enums.GoalConfigLevelEnum, level)
        paths = ["goal_config_level"]
        if custom is not None:
            config.custom_conversion_goal = custom
            paths.append("custom_conversion_goal")
        operation.update_mask.CopyFrom(field_mask_pb2.FieldMask(paths=paths))

        def execute():
            return ctx.client.mutate(
                "ConversionGoalCampaignConfigService",
                customer,
                [operation],
                validate_only=validate_only,
            )

        return ctx.safety.propose(
            tool_name="set_conversion_goal_campaign_config",
            customer_id=customer,
            description=(
                f"Set campaign {campaign} conversion goal config to {level}"
                + (f" using {custom}" if custom else "")
            ),
            payload={
                "campaign_id": campaign,
                "goal_config_level": level,
                "custom_conversion_goal_resource_name": custom,
                "validate_only": bool(validate_only),
            },
            execute=execute,
        )

    @mcp.tool()
    def list_user_list_customer_types(customer_id: str) -> dict:
        """List customer-type labels assigned to audience lists."""
        rows = ctx.client.search(
            customer_id,
            """
            SELECT
                user_list_customer_type.resource_name,
                user_list_customer_type.user_list,
                user_list_customer_type.customer_type_category
            FROM user_list_customer_type
            ORDER BY user_list_customer_type.customer_type_category
            """,
        )
        return {"user_list_customer_types": rows, "count": len(rows)}

    @mcp.tool()
    def assign_user_list_customer_type(
        customer_id: str,
        user_list_resource_name: str,
        customer_type_category: str,
        validate_only: bool = False,
    ) -> dict:
        """Propose classifying a user list for acquisition/retention lifecycle goals."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        user_list = ctx.client.assert_resource_name_customer(
            customer, user_list_resource_name, field_name="user_list_resource_name"
        )
        category = str(customer_type_category).strip().upper()
        raw = ctx.client.raw
        try:
            category_value = getattr(raw.enums.UserListCustomerTypeCategoryEnum, category)
        except AttributeError as ex:
            raise ValueError("Unknown customer_type_category enum value.") from ex
        operation = raw.get_type("UserListCustomerTypeOperation")
        operation.create.user_list = user_list
        operation.create.customer_type_category = category_value

        def execute():
            return ctx.client.mutate(
                "UserListCustomerTypeService",
                customer,
                [operation],
                validate_only=validate_only,
            )

        return ctx.safety.propose(
            tool_name="assign_user_list_customer_type",
            customer_id=customer,
            description=f"Classify {user_list} as {category}",
            payload={
                "user_list_resource_name": user_list,
                "customer_type_category": category,
                "validate_only": bool(validate_only),
            },
            execute=execute,
        )

    @mcp.tool()
    def remove_user_list_customer_type(
        customer_id: str,
        user_list_customer_type_resource_name: str,
        validate_only: bool = False,
    ) -> dict:
        """Propose removing a lifecycle/customer-type label from a user list."""
        customer, resource = _resource(
            ctx,
            customer_id,
            user_list_customer_type_resource_name,
            "user_list_customer_type_resource_name",
        )
        raw = ctx.client.raw
        operation = raw.get_type("UserListCustomerTypeOperation")
        operation.remove = resource

        def execute():
            return ctx.client.mutate(
                "UserListCustomerTypeService",
                customer,
                [operation],
                validate_only=validate_only,
            )

        return ctx.safety.propose(
            tool_name="remove_user_list_customer_type",
            customer_id=customer,
            description=f"Remove user-list customer type {resource}",
            payload={
                "user_list_customer_type_resource_name": resource,
                "validate_only": bool(validate_only),
            },
            execute=execute,
        )

    @mcp.tool()
    def list_lifecycle_goals(customer_id: str) -> dict:
        """List unified v25 acquisition, retention, and loyalty lifecycle goals."""
        rows = ctx.client.search(
            customer_id,
            """
            SELECT
                goal.resource_name,
                goal.goal_id,
                goal.goal_type,
                goal.optimization_eligibility,
                goal.owner_customer,
                goal.new_customer_acquisition_goal_settings.value_settings.additional_value,
                goal.new_customer_acquisition_goal_settings.value_settings.additional_high_lifetime_value,
                goal.new_customer_acquisition_goal_settings.value_settings.value_multiplier,
                goal.new_customer_acquisition_goal_settings.value_settings.high_lifetime_value_multiplier,
                goal.retention_goal_settings.value_settings.additional_value,
                goal.retention_goal_settings.value_settings.additional_high_lifetime_value,
                goal.retention_goal_settings.value_settings.value_multiplier,
                goal.retention_goal_settings.value_settings.high_lifetime_value_multiplier,
                goal.loyalty_retention_goal_settings.value_settings.additional_value,
                goal.loyalty_retention_goal_settings.value_settings.additional_high_lifetime_value,
                goal.loyalty_retention_goal_settings.value_settings.value_multiplier,
                goal.loyalty_retention_goal_settings.value_settings.high_lifetime_value_multiplier
            FROM goal
            ORDER BY goal.goal_type
            """,
        )
        return {"goals": rows, "count": len(rows)}

    @mcp.tool()
    def set_lifecycle_goal(
        customer_id: str,
        goal_type: str,
        value_mode: str,
        value: float,
        high_lifetime_value: float | None = None,
        validate_only: bool = False,
    ) -> dict:
        """Propose creating or updating a unified v25 lifecycle Goal.

        ``goal_type`` supports NEW_CUSTOMER_ACQUISITION, CUSTOMER_RETENTION, and
        LOYALTY_RETENTION. ``value_mode`` is ADDITIONAL or MULTIPLIER. Google
        allows at most one Goal per lifecycle type per customer.
        """
        customer = ctx.client.assert_customer_allowed(customer_id)
        clean_type = _goal_type(goal_type)
        settings_field = _GOAL_TYPES[clean_type]
        safe_type = _escape_gaql(clean_type)
        existing = ctx.client.search(
            customer,
            f"SELECT goal.resource_name, goal.goal_type FROM goal WHERE goal.goal_type = '{safe_type}' LIMIT 1",
        )
        raw = ctx.client.raw
        operation = raw.get_type("GoalOperation")
        mode = "update" if existing else "create"
        goal = operation.update if existing else operation.create
        if existing:
            goal.resource_name = existing[0]["goal"]["resource_name"]
        value_settings = getattr(getattr(goal, settings_field), "value_settings")
        suffix_paths = _set_lifecycle_value_settings(
            value_settings,
            value_mode=value_mode,
            value=value,
            high_lifetime_value=high_lifetime_value,
        )
        if existing:
            operation.update_mask.CopyFrom(
                field_mask_pb2.FieldMask(
                    paths=[f"{settings_field}.value_settings.{p}" for p in suffix_paths]
                )
            )

        def execute():
            return ctx.client.mutate(
                "GoalService", customer, [operation], validate_only=validate_only
            )

        return ctx.safety.propose(
            tool_name="set_lifecycle_goal",
            customer_id=customer,
            description=(
                f"{mode.title()} {clean_type} lifecycle Goal using "
                f"{_value_mode(value_mode)} value {value}"
            ),
            payload={
                "goal_type": clean_type,
                "mode": mode,
                "value_mode": _value_mode(value_mode),
                "value": value,
                "high_lifetime_value": high_lifetime_value,
                "validate_only": bool(validate_only),
            },
            execute=execute,
        )

    @mcp.tool()
    def list_campaign_lifecycle_goal_configs(customer_id: str) -> dict:
        """List campaign links to unified v25 lifecycle Goals and overrides."""
        rows = ctx.client.search(
            customer_id,
            """
            SELECT
                campaign_goal_config.resource_name,
                campaign_goal_config.campaign,
                campaign_goal_config.goal,
                campaign_goal_config.goal_type,
                campaign_goal_config.campaign_new_customer_acquisition_settings.target_option,
                campaign_goal_config.campaign_retention_settings.target_option,
                campaign_goal_config.campaign_loyalty_retention_settings.target_option,
                campaign_goal_config.campaign_new_customer_acquisition_settings.value_settings_override.additional_value,
                campaign_goal_config.campaign_new_customer_acquisition_settings.value_settings_override.additional_high_lifetime_value,
                campaign_goal_config.campaign_new_customer_acquisition_settings.value_settings_override.value_multiplier,
                campaign_goal_config.campaign_new_customer_acquisition_settings.value_settings_override.high_lifetime_value_multiplier,
                campaign_goal_config.campaign_retention_settings.value_settings_override.additional_value,
                campaign_goal_config.campaign_retention_settings.value_settings_override.additional_high_lifetime_value,
                campaign_goal_config.campaign_retention_settings.value_settings_override.value_multiplier,
                campaign_goal_config.campaign_retention_settings.value_settings_override.high_lifetime_value_multiplier,
                campaign_goal_config.campaign_loyalty_retention_settings.value_settings_override.additional_value,
                campaign_goal_config.campaign_loyalty_retention_settings.value_settings_override.additional_high_lifetime_value,
                campaign_goal_config.campaign_loyalty_retention_settings.value_settings_override.value_multiplier,
                campaign_goal_config.campaign_loyalty_retention_settings.value_settings_override.high_lifetime_value_multiplier
            FROM campaign_goal_config
            ORDER BY campaign_goal_config.campaign, campaign_goal_config.goal_type
            """,
        )
        return {"campaign_goal_configs": rows, "count": len(rows)}

    @mcp.tool()
    def attach_lifecycle_goal_to_campaign(
        customer_id: str,
        campaign_resource_name: str,
        goal_resource_name: str,
        target_option: str = "TARGET_ALL",
        value_mode_override: str | None = None,
        value_override: float | None = None,
        high_lifetime_value_override: float | None = None,
        validate_only: bool = False,
    ) -> dict:
        """Propose attaching a unified v25 lifecycle Goal to a campaign.

        The goal type is read first, then the correct campaign settings branch is
        populated. This prevents retention settings from being accidentally used
        for acquisition or loyalty-retention goals.
        """
        customer = ctx.client.assert_customer_allowed(customer_id)
        campaign = ctx.client.assert_resource_name_customer(
            customer, campaign_resource_name, field_name="campaign_resource_name"
        )
        goal_resource = ctx.client.assert_resource_name_customer(
            customer, goal_resource_name, field_name="goal_resource_name"
        )
        safe_goal = _escape_gaql(goal_resource)
        goal_rows = ctx.client.search(
            customer,
            f"SELECT goal.resource_name, goal.goal_type FROM goal WHERE goal.resource_name = '{safe_goal}' LIMIT 1",
        )
        if not goal_rows:
            raise ValueError("goal_resource_name was not found in the target customer.")
        clean_type = _goal_type(goal_rows[0]["goal"]["goal_type"])
        settings_field = _CAMPAIGN_GOAL_SETTINGS[clean_type]
        target = target_option.strip().upper()
        if target not in _LIFECYCLE_TARGET_OPTIONS:
            raise ValueError(
                "target_option must be TARGET_ALL, BID_HIGHER_FOR_ALL, TARGET_SPECIFIC, "
                "BID_HIGHER_FOR_SPECIFIC, or EXCLUDE_SPECIFIC."
            )
        if value_mode_override is None and (
            value_override is not None or high_lifetime_value_override is not None
        ):
            raise ValueError("value_mode_override is required when value overrides are supplied.")
        if value_mode_override is not None and value_override is None:
            raise ValueError("value_override is required when value_mode_override is supplied.")

        raw = ctx.client.raw
        operation = raw.get_type("CampaignGoalConfigOperation")
        config = operation.create
        config.campaign = campaign
        config.goal = goal_resource
        settings = getattr(config, settings_field)
        settings.target_option = getattr(raw.enums.CustomerLifecycleOptimizationModeEnum, target)
        if value_mode_override is not None:
            _set_lifecycle_value_settings(
                settings.value_settings_override,
                value_mode=value_mode_override,
                value=float(value_override),
                high_lifetime_value=high_lifetime_value_override,
            )

        def execute():
            return ctx.client.mutate(
                "CampaignGoalConfigService",
                customer,
                [operation],
                validate_only=validate_only,
            )

        return ctx.safety.propose(
            tool_name="attach_lifecycle_goal_to_campaign",
            customer_id=customer,
            description=(
                f"Attach {clean_type} Goal {goal_resource} to campaign {campaign} "
                f"with target option {target}"
            ),
            payload={
                "campaign_resource_name": campaign,
                "goal_resource_name": goal_resource,
                "goal_type": clean_type,
                "target_option": target,
                "value_mode_override": value_mode_override,
                "value_override": value_override,
                "high_lifetime_value_override": high_lifetime_value_override,
                "validate_only": bool(validate_only),
            },
            execute=execute,
        )

    @mcp.tool()
    def remove_campaign_lifecycle_goal_config(
        customer_id: str,
        campaign_goal_config_resource_name: str,
        validate_only: bool = False,
    ) -> dict:
        """Propose removing a unified lifecycle Goal-to-campaign config."""
        customer, resource = _resource(
            ctx,
            customer_id,
            campaign_goal_config_resource_name,
            "campaign_goal_config_resource_name",
        )
        raw = ctx.client.raw
        operation = raw.get_type("CampaignGoalConfigOperation")
        operation.remove = resource

        def execute():
            return ctx.client.mutate(
                "CampaignGoalConfigService",
                customer,
                [operation],
                validate_only=validate_only,
            )

        return ctx.safety.propose(
            tool_name="remove_campaign_lifecycle_goal_config",
            customer_id=customer,
            description=f"Remove campaign lifecycle goal config {resource}",
            payload={
                "campaign_goal_config_resource_name": resource,
                "validate_only": bool(validate_only),
            },
            execute=execute,
        )
