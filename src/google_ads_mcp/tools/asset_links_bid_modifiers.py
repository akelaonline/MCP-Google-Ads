"""Customer/ad-group assets, bid modifiers, and brand suggestions for API v25."""

from __future__ import annotations

import proto
from google.protobuf import field_mask_pb2

from ..context import AppContext
from ..errors import GoogleAdsMcpError, format_google_ads_exception

_DEVICES = {"MOBILE", "DESKTOP", "TABLET", "CONNECTED_TV", "OTHER"}


def _id(value: str, field_name: str) -> str:
    text = str(value).strip()
    if not text.isdigit() or int(text) <= 0:
        raise ValueError(f"{field_name} must be a positive numeric ID.")
    return text


def _owned(ctx: AppContext, customer: str, resource: str, field_name: str) -> str:
    return ctx.client.assert_resource_name_customer(customer, resource, field_name=field_name)


def _modifier(value: float, *, allow_zero: bool) -> float:
    result = float(value)
    if result == 0 and allow_zero:
        return result
    if not 0.1 <= result <= 10.0:
        raise ValueError("bid_modifier must be between 0.1 and 10.0" + (", or 0 to opt out." if allow_zero else "."))
    return result


def register(mcp, ctx: AppContext) -> None:
    # Customer assets ---------------------------------------------------
    @mcp.tool()
    def list_customer_assets(customer_id: str) -> dict:
        rows = ctx.client.search(
            customer_id,
            """
            SELECT customer_asset.resource_name, customer_asset.asset,
                   customer_asset.field_type, customer_asset.status,
                   customer_asset.primary_status, customer_asset.primary_status_reasons,
                   customer_asset.source, asset.id, asset.name, asset.type
            FROM customer_asset
            ORDER BY customer_asset.resource_name
            """,
        )
        return {"customer_assets": rows, "count": len(rows)}

    @mcp.tool()
    def attach_asset_to_customer(
        customer_id: str,
        asset_resource_name: str,
        field_type: str,
        status: str = "ENABLED",
        validate_only: bool = False,
    ) -> dict:
        """Propose linking an existing Asset at account/customer scope."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        asset = _owned(ctx, customer, asset_resource_name, "asset_resource_name")
        clean_status = status.strip().upper()
        if clean_status not in {"ENABLED", "PAUSED"}:
            raise ValueError("status must be ENABLED or PAUSED.")
        raw = ctx.client.raw
        try:
            field_enum = getattr(raw.enums.AssetFieldTypeEnum, field_type.strip().upper())
        except AttributeError as ex:
            raise ValueError(f"Unknown AssetFieldType: {field_type}") from ex
        operation = raw.get_type("CustomerAssetOperation")
        operation.create.asset = asset
        operation.create.field_type = field_enum
        operation.create.status = getattr(raw.enums.AssetLinkStatusEnum, clean_status)

        def execute():
            return ctx.client.mutate("CustomerAssetService", customer, [operation], validate_only=validate_only)

        return ctx.safety.propose(
            tool_name="attach_asset_to_customer",
            customer_id=customer,
            description=f"Attach {field_type.upper()} asset {asset} to customer {customer}",
            payload={"asset_resource_name": asset, "field_type": field_type.upper(), "status": clean_status, "validate_only": validate_only},
            execute=execute,
        )

    @mcp.tool()
    def set_customer_asset_status(
        customer_id: str,
        customer_asset_resource_name: str,
        status: str,
        validate_only: bool = False,
    ) -> dict:
        customer = ctx.client.assert_customer_allowed(customer_id)
        resource = _owned(ctx, customer, customer_asset_resource_name, "customer_asset_resource_name")
        clean_status = status.strip().upper()
        if clean_status not in {"ENABLED", "PAUSED", "REMOVED"}:
            raise ValueError("status must be ENABLED, PAUSED, or REMOVED.")
        raw = ctx.client.raw
        operation = raw.get_type("CustomerAssetOperation")
        if clean_status == "REMOVED":
            operation.remove = resource
        else:
            operation.update.resource_name = resource
            operation.update.status = getattr(raw.enums.AssetLinkStatusEnum, clean_status)
            operation.update_mask.CopyFrom(field_mask_pb2.FieldMask(paths=["status"]))

        def execute():
            return ctx.client.mutate("CustomerAssetService", customer, [operation], validate_only=validate_only)

        return ctx.safety.propose(
            tool_name="set_customer_asset_status",
            customer_id=customer,
            description=f"Set customer asset {resource} -> {clean_status}",
            payload={"customer_asset_resource_name": resource, "status": clean_status, "validate_only": validate_only},
            execute=execute,
        )

    # Ad-group assets ---------------------------------------------------
    @mcp.tool()
    def list_ad_group_assets(customer_id: str, ad_group_id: str | None = None) -> dict:
        where = ""
        if ad_group_id is not None:
            where = f"WHERE ad_group.id = {_id(ad_group_id, 'ad_group_id')}"
        rows = ctx.client.search(
            customer_id,
            f"""
            SELECT ad_group_asset.resource_name, ad_group_asset.ad_group,
                   ad_group_asset.asset, ad_group_asset.field_type,
                   ad_group_asset.status, ad_group_asset.primary_status,
                   ad_group_asset.primary_status_reasons, ad_group_asset.source,
                   asset.id, asset.name, asset.type
            FROM ad_group_asset
            {where}
            ORDER BY ad_group_asset.resource_name
            """,
        )
        return {"ad_group_assets": rows, "count": len(rows)}

    @mcp.tool()
    def attach_asset_to_ad_group(
        customer_id: str,
        ad_group_id: str,
        asset_resource_name: str,
        field_type: str,
        status: str = "ENABLED",
        validate_only: bool = False,
    ) -> dict:
        customer = ctx.client.assert_customer_allowed(customer_id)
        ad_group = _id(ad_group_id, "ad_group_id")
        asset = _owned(ctx, customer, asset_resource_name, "asset_resource_name")
        clean_status = status.strip().upper()
        if clean_status not in {"ENABLED", "PAUSED"}:
            raise ValueError("status must be ENABLED or PAUSED.")
        raw = ctx.client.raw
        try:
            field_enum = getattr(raw.enums.AssetFieldTypeEnum, field_type.strip().upper())
        except AttributeError as ex:
            raise ValueError(f"Unknown AssetFieldType: {field_type}") from ex
        operation = raw.get_type("AdGroupAssetOperation")
        operation.create.ad_group = f"customers/{customer}/adGroups/{ad_group}"
        operation.create.asset = asset
        operation.create.field_type = field_enum
        operation.create.status = getattr(raw.enums.AssetLinkStatusEnum, clean_status)

        def execute():
            return ctx.client.mutate("AdGroupAssetService", customer, [operation], validate_only=validate_only)

        return ctx.safety.propose(
            tool_name="attach_asset_to_ad_group",
            customer_id=customer,
            description=f"Attach {field_type.upper()} asset {asset} to ad group {ad_group}",
            payload={"ad_group_id": ad_group, "asset_resource_name": asset, "field_type": field_type.upper(), "status": clean_status, "validate_only": validate_only},
            execute=execute,
        )

    @mcp.tool()
    def set_ad_group_asset_status(
        customer_id: str,
        ad_group_asset_resource_name: str,
        status: str,
        validate_only: bool = False,
    ) -> dict:
        customer = ctx.client.assert_customer_allowed(customer_id)
        resource = _owned(ctx, customer, ad_group_asset_resource_name, "ad_group_asset_resource_name")
        clean_status = status.strip().upper()
        if clean_status not in {"ENABLED", "PAUSED", "REMOVED"}:
            raise ValueError("status must be ENABLED, PAUSED, or REMOVED.")
        raw = ctx.client.raw
        operation = raw.get_type("AdGroupAssetOperation")
        if clean_status == "REMOVED":
            operation.remove = resource
        else:
            operation.update.resource_name = resource
            operation.update.status = getattr(raw.enums.AssetLinkStatusEnum, clean_status)
            operation.update_mask.CopyFrom(field_mask_pb2.FieldMask(paths=["status"]))

        def execute():
            return ctx.client.mutate("AdGroupAssetService", customer, [operation], validate_only=validate_only)

        return ctx.safety.propose(
            tool_name="set_ad_group_asset_status",
            customer_id=customer,
            description=f"Set ad-group asset {resource} -> {clean_status}",
            payload={"ad_group_asset_resource_name": resource, "status": clean_status, "validate_only": validate_only},
            execute=execute,
        )

    # Campaign bid modifiers ------------------------------------------
    @mcp.tool()
    def list_campaign_bid_modifiers(customer_id: str, campaign_id: str | None = None) -> dict:
        """List campaign-level interaction bid modifiers. v25 only supports CALLS."""
        where = ""
        if campaign_id is not None:
            where = f"WHERE campaign.id = {_id(campaign_id, 'campaign_id')}"
        rows = ctx.client.search(
            customer_id,
            f"""
            SELECT campaign_bid_modifier.resource_name,
                   campaign_bid_modifier.criterion_id,
                   campaign_bid_modifier.campaign,
                   campaign_bid_modifier.bid_modifier,
                   campaign_bid_modifier.interaction_type.type
            FROM campaign_bid_modifier
            {where}
            ORDER BY campaign_bid_modifier.resource_name
            """,
        )
        return {"campaign_bid_modifiers": rows, "count": len(rows)}

    @mcp.tool()
    def set_campaign_call_bid_modifier(
        customer_id: str,
        campaign_id: str,
        bid_modifier: float,
        validate_only: bool = False,
    ) -> dict:
        """Propose updating the existing campaign CALLS bid modifier.

        In v25 the parent ``campaign`` field on CampaignBidModifier is output-only,
        so this tool intentionally does not fabricate a create operation. It looks
        up the existing CALLS modifier for the campaign and updates it. If Google
        has not exposed one for the campaign, no mutation is attempted.
        """
        customer = ctx.client.assert_customer_allowed(customer_id)
        campaign = _id(campaign_id, "campaign_id")
        modifier = _modifier(bid_modifier, allow_zero=False)
        rows = ctx.client.search(
            customer,
            f"""
            SELECT campaign_bid_modifier.resource_name,
                   campaign_bid_modifier.interaction_type.type
            FROM campaign_bid_modifier
            WHERE campaign.id = {campaign}
              AND campaign_bid_modifier.interaction_type.type = 'CALLS'
            LIMIT 1
            """,
        )
        if not rows:
            raise GoogleAdsMcpError(
                "No writable CALLS CampaignBidModifier is exposed for this campaign in API v25. "
                "No mutation was attempted."
            )
        resource = rows[0]["campaign_bid_modifier"]["resource_name"]
        _owned(ctx, customer, resource, "campaign_bid_modifier.resource_name")
        raw = ctx.client.raw
        operation = raw.get_type("CampaignBidModifierOperation")
        operation.update.resource_name = resource
        operation.update.bid_modifier = modifier
        operation.update_mask.CopyFrom(field_mask_pb2.FieldMask(paths=["bid_modifier"]))

        def execute():
            return ctx.client.mutate("CampaignBidModifierService", customer, [operation], validate_only=validate_only)

        return ctx.safety.propose(
            tool_name="set_campaign_call_bid_modifier",
            customer_id=customer,
            description=f"Set campaign {campaign} CALLS bid modifier -> x{modifier}",
            payload={"campaign_id": campaign, "resource_name": resource, "bid_modifier": modifier, "validate_only": validate_only},
            execute=execute,
        )

    @mcp.tool()
    def remove_campaign_bid_modifier(
        customer_id: str,
        campaign_bid_modifier_resource_name: str,
        validate_only: bool = False,
    ) -> dict:
        customer = ctx.client.assert_customer_allowed(customer_id)
        resource = _owned(ctx, customer, campaign_bid_modifier_resource_name, "campaign_bid_modifier_resource_name")
        operation = ctx.client.raw.get_type("CampaignBidModifierOperation")
        operation.remove = resource

        def execute():
            return ctx.client.mutate("CampaignBidModifierService", customer, [operation], validate_only=validate_only)

        return ctx.safety.propose(
            tool_name="remove_campaign_bid_modifier",
            customer_id=customer,
            description=f"Remove campaign bid modifier {resource}",
            payload={"campaign_bid_modifier_resource_name": resource, "validate_only": validate_only},
            execute=execute,
        )

    # Ad-group bid modifiers ------------------------------------------
    @mcp.tool()
    def list_ad_group_bid_modifiers(customer_id: str, ad_group_id: str | None = None) -> dict:
        where = ""
        if ad_group_id is not None:
            where = f"WHERE ad_group.id = {_id(ad_group_id, 'ad_group_id')}"
        rows = ctx.client.search(
            customer_id,
            f"""
            SELECT ad_group_bid_modifier.resource_name,
                   ad_group_bid_modifier.criterion_id,
                   ad_group_bid_modifier.ad_group,
                   ad_group_bid_modifier.bid_modifier,
                   ad_group_bid_modifier.device.type
            FROM ad_group_bid_modifier
            {where}
            ORDER BY ad_group_bid_modifier.resource_name
            """,
        )
        return {"ad_group_bid_modifiers": rows, "count": len(rows)}

    @mcp.tool()
    def create_ad_group_device_bid_modifier(
        customer_id: str,
        ad_group_id: str,
        device: str,
        bid_modifier: float,
        validate_only: bool = False,
    ) -> dict:
        customer = ctx.client.assert_customer_allowed(customer_id)
        ad_group = _id(ad_group_id, "ad_group_id")
        clean_device = device.strip().upper()
        if clean_device not in _DEVICES:
            raise ValueError(f"device must be one of {sorted(_DEVICES)}.")
        modifier = _modifier(bid_modifier, allow_zero=True)
        raw = ctx.client.raw
        operation = raw.get_type("AdGroupBidModifierOperation")
        operation.create.ad_group = f"customers/{customer}/adGroups/{ad_group}"
        operation.create.bid_modifier = modifier
        operation.create.device.type_ = getattr(raw.enums.DeviceEnum, clean_device)

        def execute():
            return ctx.client.mutate("AdGroupBidModifierService", customer, [operation], validate_only=validate_only)

        return ctx.safety.propose(
            tool_name="create_ad_group_device_bid_modifier",
            customer_id=customer,
            description=f"Set {clean_device} bid modifier x{modifier} on ad group {ad_group}",
            payload={"ad_group_id": ad_group, "device": clean_device, "bid_modifier": modifier, "validate_only": validate_only},
            execute=execute,
        )

    @mcp.tool()
    def update_ad_group_bid_modifier(
        customer_id: str,
        ad_group_bid_modifier_resource_name: str,
        bid_modifier: float,
        validate_only: bool = False,
    ) -> dict:
        customer = ctx.client.assert_customer_allowed(customer_id)
        resource = _owned(ctx, customer, ad_group_bid_modifier_resource_name, "ad_group_bid_modifier_resource_name")
        modifier = _modifier(bid_modifier, allow_zero=True)
        raw = ctx.client.raw
        operation = raw.get_type("AdGroupBidModifierOperation")
        operation.update.resource_name = resource
        operation.update.bid_modifier = modifier
        operation.update_mask.CopyFrom(field_mask_pb2.FieldMask(paths=["bid_modifier"]))

        def execute():
            return ctx.client.mutate("AdGroupBidModifierService", customer, [operation], validate_only=validate_only)

        return ctx.safety.propose(
            tool_name="update_ad_group_bid_modifier",
            customer_id=customer,
            description=f"Update ad-group bid modifier {resource} -> x{modifier}",
            payload={"ad_group_bid_modifier_resource_name": resource, "bid_modifier": modifier, "validate_only": validate_only},
            execute=execute,
        )

    @mcp.tool()
    def remove_ad_group_bid_modifier(
        customer_id: str,
        ad_group_bid_modifier_resource_name: str,
        validate_only: bool = False,
    ) -> dict:
        customer = ctx.client.assert_customer_allowed(customer_id)
        resource = _owned(ctx, customer, ad_group_bid_modifier_resource_name, "ad_group_bid_modifier_resource_name")
        operation = ctx.client.raw.get_type("AdGroupBidModifierOperation")
        operation.remove = resource

        def execute():
            return ctx.client.mutate("AdGroupBidModifierService", customer, [operation], validate_only=validate_only)

        return ctx.safety.propose(
            tool_name="remove_ad_group_bid_modifier",
            customer_id=customer,
            description=f"Remove ad-group bid modifier {resource}",
            payload={"ad_group_bid_modifier_resource_name": resource, "validate_only": validate_only},
            execute=execute,
        )

    # Brand suggestions ------------------------------------------------
    @mcp.tool()
    def suggest_brands(
        customer_id: str,
        brand_prefix: str,
        selected_brand_ids: list[str] | None = None,
    ) -> dict:
        """Suggest verified Google brand entities by name prefix."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        prefix = str(brand_prefix).strip()
        if not prefix:
            raise ValueError("brand_prefix must not be empty.")
        selected = [str(value).strip() for value in (selected_brand_ids or []) if str(value).strip()]
        raw = ctx.client.raw
        request = raw.get_type("SuggestBrandsRequest")
        request.customer_id = customer
        request.brand_prefix = prefix
        request.selected_brands.extend(selected)
        from google.ads.googleads.errors import GoogleAdsException
        try:
            response = ctx.client.service("BrandSuggestionService").suggest_brands(request=request)
        except GoogleAdsException as ex:
            raise GoogleAdsMcpError(format_google_ads_exception(ex)) from ex
        return {
            "brands": [proto.Message.to_dict(item, preserving_proto_field_name=True) for item in response.brands],
            "count": len(response.brands),
            "brand_prefix": prefix,
            "excluded_brand_ids": selected,
        }
