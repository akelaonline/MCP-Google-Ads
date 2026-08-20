"""Remaining public Google Ads API v25 core-service coverage.

This module deliberately fills service-level gaps left by the higher-level MCP
helpers: experiment arms, legacy AccountLink, CustomerService updates,
ConversionValueRule resources, and KeywordThemeConstant suggestions.
"""

from __future__ import annotations

import proto
from google.protobuf import field_mask_pb2, json_format

from ..context import AppContext
from ..errors import GoogleAdsMcpError, format_google_ads_exception


def _owned(ctx: AppContext, customer: str, resource: str, field_name: str) -> str:
    return ctx.client.assert_resource_name_customer(customer, resource, field_name=field_name)


def _call(service, method_name: str, **kwargs):
    from google.ads.googleads.errors import GoogleAdsException

    try:
        return getattr(service, method_name)(**kwargs)
    except GoogleAdsException as ex:
        raise GoogleAdsMcpError(format_google_ads_exception(ex)) from ex


def register(mcp, ctx: AppContext) -> None:
    # ------------------------------------------------------------------
    # ExperimentArmService
    # ------------------------------------------------------------------
    @mcp.tool()
    def list_experiment_arms(customer_id: str, experiment_resource_name: str | None = None) -> dict:
        """List experiment arms, campaign membership, split, and draft campaigns."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        where = ""
        if experiment_resource_name:
            experiment = _owned(ctx, customer, experiment_resource_name, "experiment_resource_name")
            safe = experiment.replace("'", "\\'")
            where = f"WHERE experiment_arm.experiment = '{safe}'"
        rows = ctx.client.search(
            customer,
            f"""
            SELECT experiment_arm.resource_name,
                   experiment_arm.experiment,
                   experiment_arm.name,
                   experiment_arm.control,
                   experiment_arm.traffic_split,
                   experiment_arm.campaigns,
                   experiment_arm.in_design_campaigns
            FROM experiment_arm
            {where}
            ORDER BY experiment_arm.name
            """,
        )
        return {"experiment_arms": rows, "count": len(rows)}

    @mcp.tool()
    def create_experiment_arms(
        customer_id: str,
        experiment_resource_name: str,
        arms: list[dict],
        validate_only: bool = False,
    ) -> dict:
        """Propose creating a complete set of experiment arms atomically.

        Each arm needs name, control, and traffic_split. The control arm must have
        exactly one campaign_resource_name. Exactly one arm must be control and
        total traffic_split must equal 100. Partial failure is intentionally off.
        """
        customer = ctx.client.assert_customer_allowed(customer_id)
        experiment = _owned(ctx, customer, experiment_resource_name, "experiment_resource_name")
        if len(arms) < 2:
            raise ValueError("Provide at least two experiment arms.")
        if sum(1 for item in arms if bool(item.get("control"))) != 1:
            raise ValueError("Exactly one experiment arm must have control=true.")
        splits = [int(item.get("traffic_split", 0)) for item in arms]
        if any(value < 1 or value > 100 for value in splits) or sum(splits) != 100:
            raise ValueError("Every traffic_split must be 1-100 and all arms must total 100.")
        raw = ctx.client.raw
        operations = []
        safe_arms = []
        names: set[str] = set()
        for item in arms:
            name = str(item.get("name", "")).strip()
            if not 1 <= len(name) <= 1024:
                raise ValueError("Each arm name must be 1-1024 characters.")
            if name in names:
                raise ValueError("Experiment arm names must be unique within the request.")
            names.add(name)
            control = bool(item.get("control"))
            campaign = item.get("campaign_resource_name")
            if control and not campaign:
                raise ValueError("The control arm requires campaign_resource_name.")
            if not control and campaign:
                # System-managed treatment arms generate their own in-design campaign.
                raise ValueError("Treatment arms must omit campaign_resource_name in the system-managed workflow.")
            operation = raw.get_type("ExperimentArmOperation")
            arm = operation.create
            arm.experiment = experiment
            arm.name = name
            arm.control = control
            arm.traffic_split = int(item["traffic_split"])
            campaign_resource = None
            if campaign:
                campaign_resource = _owned(ctx, customer, str(campaign), "campaign_resource_name")
                arm.campaigns.append(campaign_resource)
            operations.append(operation)
            safe_arms.append(
                {"name": name, "control": control, "traffic_split": int(item["traffic_split"]), "campaign_resource_name": campaign_resource}
            )

        def execute():
            return ctx.client.mutate(
                "ExperimentArmService",
                customer,
                operations,
                partial_failure=False,
                validate_only=validate_only,
            )

        return ctx.safety.propose(
            tool_name="create_experiment_arms",
            customer_id=customer,
            description=f"Create {len(operations)} experiment arms for {experiment}",
            payload={"experiment_resource_name": experiment, "arms": safe_arms, "validate_only": validate_only},
            execute=execute,
        )

    @mcp.tool()
    def update_experiment_arm(
        customer_id: str,
        experiment_arm_resource_name: str,
        name: str | None = None,
        traffic_split: int | None = None,
        campaign_resource_names: list[str] | None = None,
        validate_only: bool = False,
    ) -> dict:
        """Propose updating mutable experiment-arm fields."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        resource = _owned(ctx, customer, experiment_arm_resource_name, "experiment_arm_resource_name")
        raw = ctx.client.raw
        operation = raw.get_type("ExperimentArmOperation")
        arm = operation.update
        arm.resource_name = resource
        paths: list[str] = []
        safe_campaigns = None
        if name is not None:
            clean = str(name).strip()
            if not 1 <= len(clean) <= 1024:
                raise ValueError("name must be 1-1024 characters.")
            arm.name = clean
            paths.append("name")
        if traffic_split is not None:
            split = int(traffic_split)
            if not 1 <= split <= 100:
                raise ValueError("traffic_split must be 1-100.")
            arm.traffic_split = split
            paths.append("traffic_split")
        if campaign_resource_names is not None:
            if len(campaign_resource_names) > 1:
                raise ValueError("An experiment arm supports at most one campaign.")
            safe_campaigns = [
                _owned(ctx, customer, value, "campaign_resource_names")
                for value in campaign_resource_names
            ]
            arm.campaigns.extend(safe_campaigns)
            paths.append("campaigns")
        if not paths:
            raise ValueError("Provide name, traffic_split, and/or campaign_resource_names.")
        operation.update_mask.CopyFrom(field_mask_pb2.FieldMask(paths=paths))

        def execute():
            return ctx.client.mutate("ExperimentArmService", customer, [operation], validate_only=validate_only)

        return ctx.safety.propose(
            tool_name="update_experiment_arm",
            customer_id=customer,
            description=f"Update experiment arm {resource}: {', '.join(paths)}",
            payload={"experiment_arm_resource_name": resource, "fields": paths, "campaign_resource_names": safe_campaigns, "validate_only": validate_only},
            execute=execute,
        )

    @mcp.tool()
    def remove_experiment_arm(
        customer_id: str,
        experiment_arm_resource_name: str,
        validate_only: bool = False,
    ) -> dict:
        customer = ctx.client.assert_customer_allowed(customer_id)
        resource = _owned(ctx, customer, experiment_arm_resource_name, "experiment_arm_resource_name")
        operation = ctx.client.raw.get_type("ExperimentArmOperation")
        operation.remove = resource

        def execute():
            return ctx.client.mutate("ExperimentArmService", customer, [operation], validate_only=validate_only)

        return ctx.safety.propose(
            tool_name="remove_experiment_arm",
            customer_id=customer,
            description=f"Remove experiment arm {resource}",
            payload={"experiment_arm_resource_name": resource, "validate_only": validate_only},
            execute=execute,
        )

    # ------------------------------------------------------------------
    # CustomerService.MutateCustomer
    # ------------------------------------------------------------------
    @mcp.tool()
    def get_customer_operational_settings(customer_id: str) -> dict:
        """Read mutable customer-level auto-tagging and call-reporting settings."""
        rows = ctx.client.search(
            customer_id,
            """
            SELECT customer.resource_name,
                   customer.auto_tagging_enabled,
                   customer.call_reporting_setting.call_reporting_enabled,
                   customer.call_reporting_setting.call_conversion_reporting_enabled,
                   customer.call_reporting_setting.call_conversion_action
            FROM customer
            LIMIT 1
            """,
        )
        return {"customer": rows[0] if rows else None, "found": bool(rows)}

    @mcp.tool()
    def update_customer_operational_settings(
        customer_id: str,
        auto_tagging_enabled: bool | None = None,
        call_reporting_enabled: bool | None = None,
        call_conversion_reporting_enabled: bool | None = None,
        call_conversion_action_resource_name: str | None = None,
        validate_only: bool = False,
    ) -> dict:
        """Propose updating mutable CustomerService operational settings."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        raw = ctx.client.raw
        operation = raw.get_type("CustomerOperation")
        target = operation.update
        target.resource_name = f"customers/{customer}"
        paths: list[str] = []
        if auto_tagging_enabled is not None:
            target.auto_tagging_enabled = bool(auto_tagging_enabled)
            paths.append("auto_tagging_enabled")
        if call_reporting_enabled is not None:
            target.call_reporting_setting.call_reporting_enabled = bool(call_reporting_enabled)
            paths.append("call_reporting_setting.call_reporting_enabled")
        if call_conversion_reporting_enabled is not None:
            target.call_reporting_setting.call_conversion_reporting_enabled = bool(call_conversion_reporting_enabled)
            paths.append("call_reporting_setting.call_conversion_reporting_enabled")
        conversion_action = None
        if call_conversion_action_resource_name is not None:
            conversion_action = _owned(
                ctx, customer, call_conversion_action_resource_name, "call_conversion_action_resource_name"
            )
            target.call_reporting_setting.call_conversion_action = conversion_action
            paths.append("call_reporting_setting.call_conversion_action")
        if not paths:
            raise ValueError("Provide at least one customer setting to update.")
        operation.update_mask.CopyFrom(field_mask_pb2.FieldMask(paths=paths))
        request = raw.get_type("MutateCustomerRequest")
        request.customer_id = customer
        request.operation.CopyFrom(operation)
        request.validate_only = bool(validate_only)

        def execute():
            response = _call(ctx.client.service("CustomerService"), "mutate_customer", request=request)
            return proto.Message.to_dict(response, preserving_proto_field_name=True)

        return ctx.safety.propose(
            tool_name="update_customer_operational_settings",
            customer_id=customer,
            description=f"Update customer {customer} settings: {', '.join(paths)}",
            payload={"fields": paths, "call_conversion_action_resource_name": conversion_action, "validate_only": validate_only},
            execute=execute,
        )

    # ------------------------------------------------------------------
    # ConversionValueRuleService
    # ------------------------------------------------------------------
    @mcp.tool()
    def list_conversion_value_rules(customer_id: str) -> dict:
        rows = ctx.client.search(
            customer_id,
            """
            SELECT conversion_value_rule.resource_name,
                   conversion_value_rule.id,
                   conversion_value_rule.status,
                   conversion_value_rule.owner_customer,
                   conversion_value_rule.action,
                   conversion_value_rule.audience_condition,
                   conversion_value_rule.device_condition,
                   conversion_value_rule.geo_location_condition,
                   conversion_value_rule.itinerary_condition
            FROM conversion_value_rule
            ORDER BY conversion_value_rule.id
            """,
        )
        return {"conversion_value_rules": rows, "count": len(rows)}

    @mcp.tool()
    def create_conversion_value_rule(
        customer_id: str,
        rule: dict,
        validate_only: bool = False,
    ) -> dict:
        """Propose creating a conversion value rule from protobuf-JSON fields.

        Use action plus one or more supported condition objects. Output-only id,
        owner_customer, and resource_name are rejected by the protobuf contract.
        """
        customer = ctx.client.assert_customer_allowed(customer_id)
        if not isinstance(rule, dict) or not rule:
            raise ValueError("rule must be a non-empty protobuf-JSON object.")
        forbidden = {"id", "owner_customer", "resource_name"} & set(rule)
        if forbidden:
            raise ValueError(f"Output/immutable fields are not allowed on create: {sorted(forbidden)}")
        raw = ctx.client.raw
        operation = raw.get_type("ConversionValueRuleOperation")
        try:
            json_format.ParseDict(rule, operation.create._pb, ignore_unknown_fields=False)
        except Exception as ex:
            raise ValueError(f"Invalid ConversionValueRule payload: {ex}") from ex

        def execute():
            return ctx.client.mutate("ConversionValueRuleService", customer, [operation], validate_only=validate_only)

        return ctx.safety.propose(
            tool_name="create_conversion_value_rule",
            customer_id=customer,
            description="Create conversion value rule",
            payload={"rule": rule, "validate_only": validate_only},
            execute=execute,
        )

    @mcp.tool()
    def update_conversion_value_rule(
        customer_id: str,
        conversion_value_rule_resource_name: str,
        fields: dict,
        validate_only: bool = False,
    ) -> dict:
        """Propose patching a conversion value rule; top-level keys form update mask."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        resource = _owned(ctx, customer, conversion_value_rule_resource_name, "conversion_value_rule_resource_name")
        if not isinstance(fields, dict) or not fields:
            raise ValueError("fields must be a non-empty protobuf-JSON object.")
        if any(key in {"id", "owner_customer", "resource_name"} for key in fields):
            raise ValueError("id, owner_customer, and resource_name cannot be patched.")
        raw = ctx.client.raw
        operation = raw.get_type("ConversionValueRuleOperation")
        operation.update.resource_name = resource
        try:
            json_format.ParseDict(fields, operation.update._pb, ignore_unknown_fields=False)
        except Exception as ex:
            raise ValueError(f"Invalid ConversionValueRule patch: {ex}") from ex
        operation.update.resource_name = resource
        operation.update_mask.CopyFrom(field_mask_pb2.FieldMask(paths=list(fields)))

        def execute():
            return ctx.client.mutate("ConversionValueRuleService", customer, [operation], validate_only=validate_only)

        return ctx.safety.propose(
            tool_name="update_conversion_value_rule",
            customer_id=customer,
            description=f"Update conversion value rule {resource}: {', '.join(fields)}",
            payload={"conversion_value_rule_resource_name": resource, "fields": fields, "validate_only": validate_only},
            execute=execute,
        )

    @mcp.tool()
    def remove_conversion_value_rule(
        customer_id: str,
        conversion_value_rule_resource_name: str,
        validate_only: bool = False,
    ) -> dict:
        customer = ctx.client.assert_customer_allowed(customer_id)
        resource = _owned(ctx, customer, conversion_value_rule_resource_name, "conversion_value_rule_resource_name")
        operation = ctx.client.raw.get_type("ConversionValueRuleOperation")
        operation.remove = resource

        def execute():
            return ctx.client.mutate("ConversionValueRuleService", customer, [operation], validate_only=validate_only)

        return ctx.safety.propose(
            tool_name="remove_conversion_value_rule",
            customer_id=customer,
            description=f"Remove conversion value rule {resource}",
            payload={"conversion_value_rule_resource_name": resource, "validate_only": validate_only},
            execute=execute,
        )

    # ------------------------------------------------------------------
    # KeywordThemeConstantService
    # ------------------------------------------------------------------
    @mcp.tool()
    def suggest_keyword_theme_constants(
        query_text: str,
        country_code: str = "US",
        language_code: str = "en",
    ) -> dict:
        """Suggest localized Smart Campaign KeywordThemeConstants."""
        query = str(query_text).strip()
        if not query:
            raise ValueError("query_text must not be empty.")
        country = str(country_code).strip().upper()
        language = str(language_code).strip().lower()
        if len(country) != 2 or len(language) != 2:
            raise ValueError("country_code and language_code must each be two letters.")
        raw = ctx.client.raw
        request = raw.get_type("SuggestKeywordThemeConstantsRequest")
        request.query_text = query
        request.country_code = country
        request.language_code = language
        response = _call(
            ctx.client.service("KeywordThemeConstantService"),
            "suggest_keyword_theme_constants",
            request=request,
        )
        return {
            "keyword_theme_constants": [
                proto.Message.to_dict(item, preserving_proto_field_name=True)
                for item in response.keyword_theme_constants
            ],
            "count": len(response.keyword_theme_constants),
        }

    # ------------------------------------------------------------------
    # AccountLinkService (legacy-compatible third-party analytics link)
    # ------------------------------------------------------------------
    @mcp.tool()
    def list_account_links(customer_id: str) -> dict:
        rows = ctx.client.search(
            customer_id,
            """
            SELECT account_link.resource_name,
                   account_link.account_link_id,
                   account_link.status,
                   account_link.type,
                   account_link.third_party_app_analytics.app_analytics_provider_id,
                   account_link.third_party_app_analytics.app_id,
                   account_link.third_party_app_analytics.app_vendor
            FROM account_link
            ORDER BY account_link.account_link_id
            """,
        )
        return {"account_links": rows, "count": len(rows)}

    @mcp.tool()
    def create_legacy_third_party_app_account_link(
        customer_id: str,
        app_analytics_provider_id: int,
        app_id: str,
        app_vendor: str,
    ) -> dict:
        """Propose creating the legacy AccountLink representation for app analytics.

        New integrations should normally prefer ThirdPartyAppAnalyticsLinkService;
        this tool exists to provide complete v25 AccountLinkService compatibility.
        """
        customer = ctx.client.assert_customer_allowed(customer_id)
        provider = int(app_analytics_provider_id)
        if provider <= 0 or not str(app_id).strip():
            raise ValueError("app_analytics_provider_id must be positive and app_id is required.")
        vendor = app_vendor.strip().upper()
        raw = ctx.client.raw
        try:
            vendor_enum = getattr(raw.enums.MobileAppVendorEnum, vendor)
        except AttributeError as ex:
            raise ValueError("app_vendor must be APPLE_APP_STORE or GOOGLE_APP_STORE.") from ex
        link = raw.get_type("AccountLink")
        link.third_party_app_analytics.app_analytics_provider_id = provider
        link.third_party_app_analytics.app_id = str(app_id).strip()
        link.third_party_app_analytics.app_vendor = vendor_enum
        service = ctx.client.service("AccountLinkService")

        def execute():
            response = _call(service, "create_account_link", customer_id=customer, account_link=link)
            return proto.Message.to_dict(response, preserving_proto_field_name=True)

        return ctx.safety.propose(
            tool_name="create_legacy_third_party_app_account_link",
            customer_id=customer,
            description=f"Create AccountLink for app {app_id} via provider {provider}",
            payload={"app_analytics_provider_id": provider, "app_id": str(app_id).strip(), "app_vendor": vendor},
            execute=execute,
        )

    @mcp.tool()
    def set_account_link_status(
        customer_id: str,
        account_link_resource_name: str,
        status: str,
        validate_only: bool = False,
    ) -> dict:
        """Propose updating or removing an AccountLink."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        resource = _owned(ctx, customer, account_link_resource_name, "account_link_resource_name")
        clean_status = status.strip().upper()
        allowed = {"ENABLED", "PENDING_APPROVAL", "REJECTED", "REMOVED", "REQUESTED", "REVOKED"}
        if clean_status not in allowed:
            raise ValueError(f"status must be one of {sorted(allowed)}.")
        raw = ctx.client.raw
        operation = raw.get_type("AccountLinkOperation")
        if clean_status == "REMOVED":
            operation.remove = resource
        else:
            operation.update.resource_name = resource
            operation.update.status = getattr(raw.enums.AccountLinkStatusEnum, clean_status)
            operation.update_mask.CopyFrom(field_mask_pb2.FieldMask(paths=["status"]))
        request = raw.get_type("MutateAccountLinkRequest")
        request.customer_id = customer
        request.operation.CopyFrom(operation)
        request.partial_failure = False
        request.validate_only = bool(validate_only)

        def execute():
            response = _call(ctx.client.service("AccountLinkService"), "mutate_account_link", request=request)
            return proto.Message.to_dict(response, preserving_proto_field_name=True)

        return ctx.safety.propose(
            tool_name="set_account_link_status",
            customer_id=customer,
            description=f"Set AccountLink {resource} -> {clean_status}",
            payload={"account_link_resource_name": resource, "status": clean_status, "validate_only": validate_only},
            execute=execute,
        )
