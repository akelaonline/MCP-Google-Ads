"""Customizer attributes/values and legacy numeric ad parameters for API v25."""

from __future__ import annotations

from google.protobuf import field_mask_pb2

from ..context import AppContext

_CUSTOMIZER_TYPES = {"TEXT", "NUMBER", "PRICE", "PERCENT"}


def _customizer_type(raw, value: str):
    clean = str(value).strip().upper()
    if clean not in _CUSTOMIZER_TYPES:
        raise ValueError("customizer_type must be TEXT, NUMBER, PRICE, or PERCENT.")
    return clean, getattr(raw.enums.CustomizerAttributeTypeEnum, clean)


def _customer_resource(
    ctx: AppContext, customer_id: str, resource_name: str, field_name: str
) -> tuple[str, str]:
    customer = ctx.client.assert_customer_allowed(customer_id)
    resource = ctx.client.assert_resource_name_customer(
        customer, resource_name, field_name=field_name
    )
    return customer, resource


def _set_value(raw, target, customizer_type: str, string_value: str) -> str:
    clean_type, enum_value = _customizer_type(raw, customizer_type)
    value = str(string_value)
    if not value:
        raise ValueError("string_value must not be empty.")
    target.type_ = enum_value
    target.string_value = value
    return clean_type


def register(mcp, ctx: AppContext) -> None:
    @mcp.tool()
    def list_customizer_attributes(customer_id: str) -> dict:
        """List account customizer attributes and immutable data types."""
        rows = ctx.client.search(
            customer_id,
            """
            SELECT
                customizer_attribute.resource_name,
                customizer_attribute.id,
                customizer_attribute.name,
                customizer_attribute.type,
                customizer_attribute.status
            FROM customizer_attribute
            ORDER BY customizer_attribute.name
            """,
        )
        return {"customizer_attributes": rows, "count": len(rows)}

    @mcp.tool()
    def create_customizer_attribute(
        customer_id: str,
        name: str,
        customizer_type: str,
        validate_only: bool = False,
    ) -> dict:
        """Propose creating an immutable customizer attribute."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        clean_name = str(name).strip()
        if not (1 <= len(clean_name) <= 40):
            raise ValueError("name must contain between 1 and 40 characters.")
        raw = ctx.client.raw
        type_name, type_value = _customizer_type(raw, customizer_type)
        operation = raw.get_type("CustomizerAttributeOperation")
        operation.create.name = clean_name
        operation.create.type_ = type_value

        def execute():
            return ctx.client.mutate(
                "CustomizerAttributeService",
                customer,
                [operation],
                validate_only=validate_only,
            )

        return ctx.safety.propose(
            tool_name="create_customizer_attribute",
            customer_id=customer,
            description=f"Create {type_name} customizer attribute '{clean_name}'",
            payload={
                "name": clean_name,
                "customizer_type": type_name,
                "validate_only": bool(validate_only),
            },
            execute=execute,
        )

    @mcp.tool()
    def remove_customizer_attribute(
        customer_id: str,
        customizer_attribute_resource_name: str,
        validate_only: bool = False,
    ) -> dict:
        """Propose removing a customizer attribute and its active use."""
        customer, resource = _customer_resource(
            ctx,
            customer_id,
            customizer_attribute_resource_name,
            "customizer_attribute_resource_name",
        )
        raw = ctx.client.raw
        operation = raw.get_type("CustomizerAttributeOperation")
        operation.remove = resource

        def execute():
            return ctx.client.mutate(
                "CustomizerAttributeService",
                customer,
                [operation],
                validate_only=validate_only,
            )

        return ctx.safety.propose(
            tool_name="remove_customizer_attribute",
            customer_id=customer,
            description=f"Remove customizer attribute {resource}",
            payload={
                "customizer_attribute_resource_name": resource,
                "validate_only": bool(validate_only),
            },
            execute=execute,
        )

    @mcp.tool()
    def list_customer_customizers(customer_id: str) -> dict:
        """List customer-level customizer values."""
        rows = ctx.client.search(
            customer_id,
            """
            SELECT
                customer_customizer.resource_name,
                customer_customizer.customizer_attribute,
                customer_customizer.value.type,
                customer_customizer.value.string_value,
                customer_customizer.status
            FROM customer_customizer
            ORDER BY customer_customizer.customizer_attribute
            """,
        )
        return {"customer_customizers": rows, "count": len(rows)}

    @mcp.tool()
    def set_customer_customizer(
        customer_id: str,
        customizer_attribute_resource_name: str,
        customizer_type: str,
        string_value: str,
        validate_only: bool = False,
    ) -> dict:
        """Propose creating a customer-level value for one customizer attribute."""
        customer, attribute = _customer_resource(
            ctx,
            customer_id,
            customizer_attribute_resource_name,
            "customizer_attribute_resource_name",
        )
        raw = ctx.client.raw
        operation = raw.get_type("CustomerCustomizerOperation")
        customizer = operation.create
        customizer.customizer_attribute = attribute
        type_name = _set_value(raw, customizer.value, customizer_type, string_value)

        def execute():
            return ctx.client.mutate(
                "CustomerCustomizerService",
                customer,
                [operation],
                validate_only=validate_only,
            )

        return ctx.safety.propose(
            tool_name="set_customer_customizer",
            customer_id=customer,
            description=f"Set customer customizer {attribute}={string_value!r}",
            payload={
                "customizer_attribute_resource_name": attribute,
                "customizer_type": type_name,
                "string_value": str(string_value),
                "validate_only": bool(validate_only),
            },
            execute=execute,
        )

    @mcp.tool()
    def remove_customer_customizer(
        customer_id: str,
        customer_customizer_resource_name: str,
        validate_only: bool = False,
    ) -> dict:
        """Propose removing a customer-level customizer value."""
        customer, resource = _customer_resource(
            ctx, customer_id, customer_customizer_resource_name,
            "customer_customizer_resource_name"
        )
        raw = ctx.client.raw
        operation = raw.get_type("CustomerCustomizerOperation")
        operation.remove = resource

        def execute():
            return ctx.client.mutate(
                "CustomerCustomizerService", customer, [operation], validate_only=validate_only
            )

        return ctx.safety.propose(
            tool_name="remove_customer_customizer",
            customer_id=customer,
            description=f"Remove customer customizer {resource}",
            payload={"customer_customizer_resource_name": resource, "validate_only": bool(validate_only)},
            execute=execute,
        )

    @mcp.tool()
    def list_campaign_customizers(customer_id: str, campaign_id: str | None = None) -> dict:
        """List campaign-level customizer values."""
        where = ""
        if campaign_id is not None:
            campaign = str(campaign_id).strip()
            if not campaign.isdigit():
                raise ValueError("campaign_id must be numeric.")
            where = f"WHERE campaign.id = {campaign}"
        rows = ctx.client.search(
            customer_id,
            f"""
            SELECT
                campaign_customizer.resource_name,
                campaign_customizer.campaign,
                campaign_customizer.customizer_attribute,
                campaign_customizer.value.type,
                campaign_customizer.value.string_value,
                campaign_customizer.status
            FROM campaign_customizer
            {where}
            ORDER BY campaign_customizer.campaign, campaign_customizer.customizer_attribute
            """,
        )
        return {"campaign_customizers": rows, "count": len(rows)}

    @mcp.tool()
    def set_campaign_customizer(
        customer_id: str,
        campaign_id: str,
        customizer_attribute_resource_name: str,
        customizer_type: str,
        string_value: str,
        validate_only: bool = False,
    ) -> dict:
        """Propose creating a campaign-level customizer value."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        campaign = str(campaign_id).strip()
        if not campaign.isdigit():
            raise ValueError("campaign_id must be numeric.")
        attribute = ctx.client.assert_resource_name_customer(
            customer, customizer_attribute_resource_name,
            field_name="customizer_attribute_resource_name"
        )
        raw = ctx.client.raw
        operation = raw.get_type("CampaignCustomizerOperation")
        customizer = operation.create
        customizer.campaign = raw.get_service("CampaignService").campaign_path(customer, campaign)
        customizer.customizer_attribute = attribute
        type_name = _set_value(raw, customizer.value, customizer_type, string_value)

        def execute():
            return ctx.client.mutate(
                "CampaignCustomizerService", customer, [operation], validate_only=validate_only
            )

        return ctx.safety.propose(
            tool_name="set_campaign_customizer",
            customer_id=customer,
            description=f"Set campaign {campaign} customizer {attribute}={string_value!r}",
            payload={
                "campaign_id": campaign,
                "customizer_attribute_resource_name": attribute,
                "customizer_type": type_name,
                "string_value": str(string_value),
                "validate_only": bool(validate_only),
            },
            execute=execute,
        )

    @mcp.tool()
    def remove_campaign_customizer(
        customer_id: str,
        campaign_customizer_resource_name: str,
        validate_only: bool = False,
    ) -> dict:
        """Propose removing a campaign-level customizer value."""
        customer, resource = _customer_resource(
            ctx, customer_id, campaign_customizer_resource_name,
            "campaign_customizer_resource_name"
        )
        raw = ctx.client.raw
        operation = raw.get_type("CampaignCustomizerOperation")
        operation.remove = resource

        def execute():
            return ctx.client.mutate(
                "CampaignCustomizerService", customer, [operation], validate_only=validate_only
            )

        return ctx.safety.propose(
            tool_name="remove_campaign_customizer",
            customer_id=customer,
            description=f"Remove campaign customizer {resource}",
            payload={"campaign_customizer_resource_name": resource, "validate_only": bool(validate_only)},
            execute=execute,
        )

    @mcp.tool()
    def list_ad_group_customizers(customer_id: str, ad_group_id: str | None = None) -> dict:
        """List ad-group-level customizer values."""
        where = ""
        if ad_group_id is not None:
            ad_group = str(ad_group_id).strip()
            if not ad_group.isdigit():
                raise ValueError("ad_group_id must be numeric.")
            where = f"WHERE ad_group.id = {ad_group}"
        rows = ctx.client.search(
            customer_id,
            f"""
            SELECT
                ad_group_customizer.resource_name,
                ad_group_customizer.ad_group,
                ad_group_customizer.customizer_attribute,
                ad_group_customizer.value.type,
                ad_group_customizer.value.string_value,
                ad_group_customizer.status
            FROM ad_group_customizer
            {where}
            ORDER BY ad_group_customizer.ad_group, ad_group_customizer.customizer_attribute
            """,
        )
        return {"ad_group_customizers": rows, "count": len(rows)}

    @mcp.tool()
    def set_ad_group_customizer(
        customer_id: str,
        ad_group_id: str,
        customizer_attribute_resource_name: str,
        customizer_type: str,
        string_value: str,
        validate_only: bool = False,
    ) -> dict:
        """Propose creating an ad-group-level customizer value."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        ad_group = str(ad_group_id).strip()
        if not ad_group.isdigit():
            raise ValueError("ad_group_id must be numeric.")
        attribute = ctx.client.assert_resource_name_customer(
            customer, customizer_attribute_resource_name,
            field_name="customizer_attribute_resource_name"
        )
        raw = ctx.client.raw
        operation = raw.get_type("AdGroupCustomizerOperation")
        customizer = operation.create
        customizer.ad_group = raw.get_service("AdGroupService").ad_group_path(customer, ad_group)
        customizer.customizer_attribute = attribute
        type_name = _set_value(raw, customizer.value, customizer_type, string_value)

        def execute():
            return ctx.client.mutate(
                "AdGroupCustomizerService", customer, [operation], validate_only=validate_only
            )

        return ctx.safety.propose(
            tool_name="set_ad_group_customizer",
            customer_id=customer,
            description=f"Set ad group {ad_group} customizer {attribute}={string_value!r}",
            payload={
                "ad_group_id": ad_group,
                "customizer_attribute_resource_name": attribute,
                "customizer_type": type_name,
                "string_value": str(string_value),
                "validate_only": bool(validate_only),
            },
            execute=execute,
        )

    @mcp.tool()
    def remove_ad_group_customizer(
        customer_id: str,
        ad_group_customizer_resource_name: str,
        validate_only: bool = False,
    ) -> dict:
        """Propose removing an ad-group-level customizer value."""
        customer, resource = _customer_resource(
            ctx, customer_id, ad_group_customizer_resource_name,
            "ad_group_customizer_resource_name"
        )
        raw = ctx.client.raw
        operation = raw.get_type("AdGroupCustomizerOperation")
        operation.remove = resource

        def execute():
            return ctx.client.mutate(
                "AdGroupCustomizerService", customer, [operation], validate_only=validate_only
            )

        return ctx.safety.propose(
            tool_name="remove_ad_group_customizer",
            customer_id=customer,
            description=f"Remove ad group customizer {resource}",
            payload={"ad_group_customizer_resource_name": resource, "validate_only": bool(validate_only)},
            execute=execute,
        )

    @mcp.tool()
    def list_ad_group_criterion_customizers(
        customer_id: str,
        ad_group_id: str | None = None,
    ) -> dict:
        """List criterion/keyword-level customizer values."""
        where = ""
        if ad_group_id is not None:
            ad_group = str(ad_group_id).strip()
            if not ad_group.isdigit():
                raise ValueError("ad_group_id must be numeric.")
            where = f"WHERE ad_group.id = {ad_group}"
        rows = ctx.client.search(
            customer_id,
            f"""
            SELECT
                ad_group_criterion_customizer.resource_name,
                ad_group_criterion_customizer.ad_group_criterion,
                ad_group_criterion_customizer.customizer_attribute,
                ad_group_criterion_customizer.value.type,
                ad_group_criterion_customizer.value.string_value,
                ad_group_criterion_customizer.status
            FROM ad_group_criterion_customizer
            {where}
            ORDER BY ad_group_criterion_customizer.ad_group_criterion,
                     ad_group_criterion_customizer.customizer_attribute
            """,
        )
        return {"ad_group_criterion_customizers": rows, "count": len(rows)}

    @mcp.tool()
    def set_ad_group_criterion_customizer(
        customer_id: str,
        ad_group_id: str,
        criterion_id: str,
        customizer_attribute_resource_name: str,
        customizer_type: str,
        string_value: str,
        validate_only: bool = False,
    ) -> dict:
        """Propose creating a criterion/keyword-level customizer value."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        ad_group = str(ad_group_id).strip()
        criterion = str(criterion_id).strip()
        if not ad_group.isdigit() or not criterion.isdigit():
            raise ValueError("ad_group_id and criterion_id must be numeric.")
        attribute = ctx.client.assert_resource_name_customer(
            customer, customizer_attribute_resource_name,
            field_name="customizer_attribute_resource_name"
        )
        raw = ctx.client.raw
        operation = raw.get_type("AdGroupCriterionCustomizerOperation")
        customizer = operation.create
        customizer.ad_group_criterion = raw.get_service(
            "AdGroupCriterionService"
        ).ad_group_criterion_path(customer, ad_group, criterion)
        customizer.customizer_attribute = attribute
        type_name = _set_value(raw, customizer.value, customizer_type, string_value)

        def execute():
            return ctx.client.mutate(
                "AdGroupCriterionCustomizerService", customer, [operation],
                validate_only=validate_only
            )

        return ctx.safety.propose(
            tool_name="set_ad_group_criterion_customizer",
            customer_id=customer,
            description=(
                f"Set criterion {ad_group}~{criterion} customizer "
                f"{attribute}={string_value!r}"
            ),
            payload={
                "ad_group_id": ad_group,
                "criterion_id": criterion,
                "customizer_attribute_resource_name": attribute,
                "customizer_type": type_name,
                "string_value": str(string_value),
                "validate_only": bool(validate_only),
            },
            execute=execute,
        )

    @mcp.tool()
    def remove_ad_group_criterion_customizer(
        customer_id: str,
        ad_group_criterion_customizer_resource_name: str,
        validate_only: bool = False,
    ) -> dict:
        """Propose removing a criterion/keyword-level customizer value."""
        customer, resource = _customer_resource(
            ctx, customer_id, ad_group_criterion_customizer_resource_name,
            "ad_group_criterion_customizer_resource_name"
        )
        raw = ctx.client.raw
        operation = raw.get_type("AdGroupCriterionCustomizerOperation")
        operation.remove = resource

        def execute():
            return ctx.client.mutate(
                "AdGroupCriterionCustomizerService", customer, [operation],
                validate_only=validate_only
            )

        return ctx.safety.propose(
            tool_name="remove_ad_group_criterion_customizer",
            customer_id=customer,
            description=f"Remove criterion customizer {resource}",
            payload={
                "ad_group_criterion_customizer_resource_name": resource,
                "validate_only": bool(validate_only),
            },
            execute=execute,
        )

    @mcp.tool()
    def list_ad_parameters(customer_id: str, ad_group_id: str | None = None) -> dict:
        """List numeric ad parameters ({param1}/{param2}) attached to keyword criteria."""
        where = ""
        if ad_group_id is not None:
            ad_group = str(ad_group_id).strip()
            if not ad_group.isdigit():
                raise ValueError("ad_group_id must be numeric.")
            where = f"WHERE ad_group.id = {ad_group}"
        rows = ctx.client.search(
            customer_id,
            f"""
            SELECT
                ad_parameter.resource_name,
                ad_parameter.ad_group_criterion,
                ad_parameter.parameter_index,
                ad_parameter.insertion_text
            FROM ad_parameter
            {where}
            ORDER BY ad_parameter.ad_group_criterion, ad_parameter.parameter_index
            """,
        )
        return {"ad_parameters": rows, "count": len(rows)}

    @mcp.tool()
    def set_ad_parameter(
        customer_id: str,
        ad_group_id: str,
        criterion_id: str,
        parameter_index: int,
        insertion_text: str,
        validate_only: bool = False,
    ) -> dict:
        """Propose creating or updating numeric {param1}/{param2} insertion text."""
        if parameter_index not in {1, 2}:
            raise ValueError("parameter_index must be 1 or 2.")
        text = str(insertion_text).strip()
        if not text:
            raise ValueError("insertion_text must not be empty.")
        customer = ctx.client.assert_customer_allowed(customer_id)
        ad_group = str(ad_group_id).strip()
        criterion = str(criterion_id).strip()
        if not ad_group.isdigit() or not criterion.isdigit():
            raise ValueError("ad_group_id and criterion_id must be numeric.")
        raw = ctx.client.raw
        resource_name = raw.get_service("AdParameterService").ad_parameter_path(
            customer, ad_group, criterion, parameter_index
        )
        safe = resource_name.replace("\\", "\\\\").replace("'", "\\'")
        existing = ctx.client.search(
            customer,
            f"SELECT ad_parameter.resource_name FROM ad_parameter WHERE ad_parameter.resource_name = '{safe}' LIMIT 1",
        )
        operation = raw.get_type("AdParameterOperation")
        mode = "update" if existing else "create"
        if existing:
            parameter = operation.update
            parameter.resource_name = resource_name
            parameter.insertion_text = text
            operation.update_mask.CopyFrom(
                field_mask_pb2.FieldMask(paths=["insertion_text"])
            )
        else:
            parameter = operation.create
            parameter.ad_group_criterion = raw.get_service(
                "AdGroupCriterionService"
            ).ad_group_criterion_path(customer, ad_group, criterion)
            parameter.parameter_index = parameter_index
            parameter.insertion_text = text

        def execute():
            return ctx.client.mutate(
                "AdParameterService", customer, [operation], validate_only=validate_only
            )

        return ctx.safety.propose(
            tool_name="set_ad_parameter",
            customer_id=customer,
            description=(
                f"{mode.title()} ad parameter {parameter_index} on criterion "
                f"{ad_group}~{criterion} with {text!r}"
            ),
            payload={
                "ad_group_id": ad_group,
                "criterion_id": criterion,
                "parameter_index": parameter_index,
                "insertion_text": text,
                "mode": mode,
                "validate_only": bool(validate_only),
            },
            execute=execute,
        )

    @mcp.tool()
    def remove_ad_parameter(
        customer_id: str,
        ad_parameter_resource_name: str,
        validate_only: bool = False,
    ) -> dict:
        """Propose removing one numeric ad parameter."""
        customer, resource = _customer_resource(
            ctx, customer_id, ad_parameter_resource_name, "ad_parameter_resource_name"
        )
        raw = ctx.client.raw
        operation = raw.get_type("AdParameterOperation")
        operation.remove = resource

        def execute():
            return ctx.client.mutate(
                "AdParameterService", customer, [operation], validate_only=validate_only
            )

        return ctx.safety.propose(
            tool_name="remove_ad_parameter",
            customer_id=customer,
            description=f"Remove ad parameter {resource}",
            payload={"ad_parameter_resource_name": resource, "validate_only": bool(validate_only)},
            execute=execute,
        )
