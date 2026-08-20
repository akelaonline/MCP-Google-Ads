"""Asset Set lifecycle and relationship management for Google Ads API v25."""

from __future__ import annotations

from google.protobuf import field_mask_pb2

from ..context import AppContext

_ASSET_SET_TYPES = {
    "BUSINESS_PROFILE_DYNAMIC_LOCATION_GROUP",
    "CHAIN_DYNAMIC_LOCATION_GROUP",
    "DYNAMIC_CUSTOM",
    "DYNAMIC_EDUCATION",
    "DYNAMIC_FLIGHTS",
    "DYNAMIC_HOTELS_AND_RENTALS",
    "DYNAMIC_JOBS",
    "DYNAMIC_LOCAL",
    "DYNAMIC_REAL_ESTATE",
    "DYNAMIC_TRAVEL",
    "HOTEL_PROPERTY",
    "LOCATION_SYNC",
    "MERCHANT_CENTER_FEED",
    "PAGE_FEED",
    "STATIC_LOCATION_GROUP",
    "TRAVEL_FEED",
}


def _id(value: str, field_name: str) -> str:
    text = str(value).strip()
    if not text.isdigit() or int(text) <= 0:
        raise ValueError(f"{field_name} must be a positive numeric ID.")
    return text


def _owned(ctx: AppContext, customer: str, resource: str, field_name: str) -> str:
    return ctx.client.assert_resource_name_customer(customer, resource, field_name=field_name)


def register(mcp, ctx: AppContext) -> None:
    @mcp.tool()
    def list_asset_sets(
        customer_id: str,
        type_filter: str | None = None,
        include_removed: bool = False,
    ) -> dict:
        """List reusable AssetSet resources and their source metadata."""
        filters: list[str] = []
        if not include_removed:
            filters.append("asset_set.status != 'REMOVED'")
        if type_filter:
            clean_type = type_filter.strip().upper()
            if clean_type not in _ASSET_SET_TYPES:
                raise ValueError(f"type_filter must be one of {sorted(_ASSET_SET_TYPES)}.")
            filters.append(f"asset_set.type = '{clean_type}'")
        where = "WHERE " + " AND ".join(filters) if filters else ""
        rows = ctx.client.search(
            customer_id,
            f"""
            SELECT
                asset_set.resource_name,
                asset_set.id,
                asset_set.name,
                asset_set.type,
                asset_set.status,
                asset_set.merchant_center_feed.merchant_id,
                asset_set.merchant_center_feed.feed_label,
                asset_set.location_group_parent_asset_set_id,
                asset_set.hotel_property_data.hotel_center_id,
                asset_set.hotel_property_data.partner_name
            FROM asset_set
            {where}
            ORDER BY asset_set.name
            """,
        )
        return {"asset_sets": rows, "count": len(rows)}

    @mcp.tool()
    def create_asset_set(
        customer_id: str,
        name: str,
        asset_set_type: str,
        merchant_id: str | None = None,
        feed_label: str | None = None,
        location_group_parent_asset_set_id: str | None = None,
        validate_only: bool = False,
    ) -> dict:
        """Propose creating an AssetSet.

        ``name`` and ``asset_set_type`` are required by v25. For
        MERCHANT_CENTER_FEED, ``merchant_id`` is required and ``feed_label`` is
        optional. Location-group types can additionally provide the required
        parent sync AssetSet ID through ``location_group_parent_asset_set_id``.
        Specialized LOCATION_SYNC source configuration is intentionally handled
        separately because its fields depend on Business Profile vs chain source.
        """
        customer = ctx.client.assert_customer_allowed(customer_id)
        clean_name = str(name).strip()
        if not 1 <= len(clean_name) <= 128:
            raise ValueError("name must be between 1 and 128 characters.")
        clean_type = asset_set_type.strip().upper()
        if clean_type not in _ASSET_SET_TYPES:
            raise ValueError(f"asset_set_type must be one of {sorted(_ASSET_SET_TYPES)}.")
        if clean_type == "MERCHANT_CENTER_FEED" and merchant_id is None:
            raise ValueError("merchant_id is required for MERCHANT_CENTER_FEED.")

        raw = ctx.client.raw
        operation = raw.get_type("AssetSetOperation")
        asset_set = operation.create
        asset_set.name = clean_name
        asset_set.type_ = getattr(raw.enums.AssetSetTypeEnum, clean_type)
        if merchant_id is not None:
            asset_set.merchant_center_feed.merchant_id = int(_id(merchant_id, "merchant_id"))
            if feed_label is not None:
                label = str(feed_label).strip()
                if not label:
                    raise ValueError("feed_label must not be empty when supplied.")
                asset_set.merchant_center_feed.feed_label = label
        if location_group_parent_asset_set_id is not None:
            asset_set.location_group_parent_asset_set_id = int(
                _id(location_group_parent_asset_set_id, "location_group_parent_asset_set_id")
            )

        def execute():
            return ctx.client.mutate(
                "AssetSetService", customer, [operation], validate_only=validate_only
            )

        return ctx.safety.propose(
            tool_name="create_asset_set",
            customer_id=customer,
            description=f"Create {clean_type} AssetSet '{clean_name}'",
            payload={
                "name": clean_name,
                "asset_set_type": clean_type,
                "merchant_id": merchant_id,
                "feed_label": feed_label,
                "location_group_parent_asset_set_id": location_group_parent_asset_set_id,
                "validate_only": validate_only,
            },
            execute=execute,
        )

    @mcp.tool()
    def update_asset_set_name(
        customer_id: str,
        asset_set_resource_name: str,
        name: str,
        validate_only: bool = False,
    ) -> dict:
        """Propose renaming an AssetSet. Its type is immutable."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        resource = _owned(ctx, customer, asset_set_resource_name, "asset_set_resource_name")
        clean_name = str(name).strip()
        if not 1 <= len(clean_name) <= 128:
            raise ValueError("name must be between 1 and 128 characters.")
        raw = ctx.client.raw
        operation = raw.get_type("AssetSetOperation")
        operation.update.resource_name = resource
        operation.update.name = clean_name
        operation.update_mask.CopyFrom(field_mask_pb2.FieldMask(paths=["name"]))

        def execute():
            return ctx.client.mutate(
                "AssetSetService", customer, [operation], validate_only=validate_only
            )

        return ctx.safety.propose(
            tool_name="update_asset_set_name",
            customer_id=customer,
            description=f"Rename AssetSet {resource} -> '{clean_name}'",
            payload={"asset_set_resource_name": resource, "name": clean_name, "validate_only": validate_only},
            execute=execute,
        )

    @mcp.tool()
    def remove_asset_set(
        customer_id: str,
        asset_set_resource_name: str,
        validate_only: bool = False,
    ) -> dict:
        """Propose permanently removing an AssetSet."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        resource = _owned(ctx, customer, asset_set_resource_name, "asset_set_resource_name")
        operation = ctx.client.raw.get_type("AssetSetOperation")
        operation.remove = resource

        def execute():
            return ctx.client.mutate(
                "AssetSetService", customer, [operation], validate_only=validate_only
            )

        return ctx.safety.propose(
            tool_name="remove_asset_set",
            customer_id=customer,
            description=f"Remove AssetSet {resource}",
            payload={"asset_set_resource_name": resource, "validate_only": validate_only},
            execute=execute,
        )

    @mcp.tool()
    def list_asset_set_assets(
        customer_id: str,
        asset_set_id: str | None = None,
    ) -> dict:
        """List assets linked into AssetSets."""
        where = ""
        if asset_set_id is not None:
            set_id = _id(asset_set_id, "asset_set_id")
            where = f"WHERE asset_set.id = {set_id}"
        rows = ctx.client.search(
            customer_id,
            f"""
            SELECT
                asset_set_asset.resource_name,
                asset_set_asset.asset_set,
                asset_set_asset.asset,
                asset_set_asset.status,
                asset.id,
                asset.name,
                asset.type
            FROM asset_set_asset
            {where}
            ORDER BY asset_set_asset.resource_name
            """,
        )
        return {"asset_set_assets": rows, "count": len(rows)}

    @mcp.tool()
    def attach_asset_to_asset_set(
        customer_id: str,
        asset_set_resource_name: str,
        asset_resource_name: str,
        validate_only: bool = False,
    ) -> dict:
        """Propose linking an existing Asset into an AssetSet."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        asset_set = _owned(ctx, customer, asset_set_resource_name, "asset_set_resource_name")
        asset = _owned(ctx, customer, asset_resource_name, "asset_resource_name")
        operation = ctx.client.raw.get_type("AssetSetAssetOperation")
        operation.create.asset_set = asset_set
        operation.create.asset = asset

        def execute():
            return ctx.client.mutate(
                "AssetSetAssetService", customer, [operation], validate_only=validate_only
            )

        return ctx.safety.propose(
            tool_name="attach_asset_to_asset_set",
            customer_id=customer,
            description=f"Attach asset {asset} to AssetSet {asset_set}",
            payload={"asset_set_resource_name": asset_set, "asset_resource_name": asset, "validate_only": validate_only},
            execute=execute,
        )

    @mcp.tool()
    def remove_asset_from_asset_set(
        customer_id: str,
        asset_set_id: str,
        asset_id: str,
        validate_only: bool = False,
    ) -> dict:
        """Propose removing an AssetSetAsset relationship."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        set_id = _id(asset_set_id, "asset_set_id")
        a_id = _id(asset_id, "asset_id")
        resource = f"customers/{customer}/assetSetAssets/{set_id}~{a_id}"
        operation = ctx.client.raw.get_type("AssetSetAssetOperation")
        operation.remove = resource

        def execute():
            return ctx.client.mutate(
                "AssetSetAssetService", customer, [operation], validate_only=validate_only
            )

        return ctx.safety.propose(
            tool_name="remove_asset_from_asset_set",
            customer_id=customer,
            description=f"Remove asset {a_id} from AssetSet {set_id}",
            payload={"asset_set_id": set_id, "asset_id": a_id, "validate_only": validate_only},
            execute=execute,
        )

    @mcp.tool()
    def list_customer_asset_sets(customer_id: str) -> dict:
        """List AssetSets linked at customer level."""
        rows = ctx.client.search(
            customer_id,
            """
            SELECT
                customer_asset_set.resource_name,
                customer_asset_set.asset_set,
                customer_asset_set.status,
                asset_set.id,
                asset_set.name,
                asset_set.type
            FROM customer_asset_set
            ORDER BY customer_asset_set.resource_name
            """,
        )
        return {"customer_asset_sets": rows, "count": len(rows)}

    @mcp.tool()
    def attach_asset_set_to_customer(
        customer_id: str,
        asset_set_resource_name: str,
        validate_only: bool = False,
    ) -> dict:
        """Propose linking an AssetSet at account/customer scope."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        asset_set = _owned(ctx, customer, asset_set_resource_name, "asset_set_resource_name")
        operation = ctx.client.raw.get_type("CustomerAssetSetOperation")
        operation.create.customer = f"customers/{customer}"
        operation.create.asset_set = asset_set

        def execute():
            return ctx.client.mutate(
                "CustomerAssetSetService", customer, [operation], validate_only=validate_only
            )

        return ctx.safety.propose(
            tool_name="attach_asset_set_to_customer",
            customer_id=customer,
            description=f"Attach AssetSet {asset_set} to customer {customer}",
            payload={"asset_set_resource_name": asset_set, "validate_only": validate_only},
            execute=execute,
        )

    @mcp.tool()
    def remove_asset_set_from_customer(
        customer_id: str,
        asset_set_id: str,
        validate_only: bool = False,
    ) -> dict:
        """Propose unlinking an AssetSet from customer scope."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        set_id = _id(asset_set_id, "asset_set_id")
        resource = f"customers/{customer}/customerAssetSets/{set_id}"
        operation = ctx.client.raw.get_type("CustomerAssetSetOperation")
        operation.remove = resource

        def execute():
            return ctx.client.mutate(
                "CustomerAssetSetService", customer, [operation], validate_only=validate_only
            )

        return ctx.safety.propose(
            tool_name="remove_asset_set_from_customer",
            customer_id=customer,
            description=f"Remove AssetSet {set_id} from customer {customer}",
            payload={"asset_set_id": set_id, "validate_only": validate_only},
            execute=execute,
        )

    @mcp.tool()
    def list_campaign_asset_sets(customer_id: str, campaign_id: str | None = None) -> dict:
        """List AssetSets linked to campaigns."""
        where = ""
        if campaign_id is not None:
            c_id = _id(campaign_id, "campaign_id")
            where = f"WHERE campaign.id = {c_id}"
        rows = ctx.client.search(
            customer_id,
            f"""
            SELECT
                campaign_asset_set.resource_name,
                campaign_asset_set.campaign,
                campaign_asset_set.asset_set,
                campaign_asset_set.status,
                asset_set.id,
                asset_set.name,
                asset_set.type
            FROM campaign_asset_set
            {where}
            ORDER BY campaign_asset_set.resource_name
            """,
        )
        return {"campaign_asset_sets": rows, "count": len(rows)}

    @mcp.tool()
    def attach_asset_set_to_campaign(
        customer_id: str,
        campaign_id: str,
        asset_set_resource_name: str,
        validate_only: bool = False,
    ) -> dict:
        """Propose linking an AssetSet to a campaign."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        campaign = _id(campaign_id, "campaign_id")
        asset_set = _owned(ctx, customer, asset_set_resource_name, "asset_set_resource_name")
        operation = ctx.client.raw.get_type("CampaignAssetSetOperation")
        operation.create.campaign = f"customers/{customer}/campaigns/{campaign}"
        operation.create.asset_set = asset_set

        def execute():
            return ctx.client.mutate(
                "CampaignAssetSetService", customer, [operation], validate_only=validate_only
            )

        return ctx.safety.propose(
            tool_name="attach_asset_set_to_campaign",
            customer_id=customer,
            description=f"Attach AssetSet {asset_set} to campaign {campaign}",
            payload={"campaign_id": campaign, "asset_set_resource_name": asset_set, "validate_only": validate_only},
            execute=execute,
        )

    @mcp.tool()
    def remove_asset_set_from_campaign(
        customer_id: str,
        campaign_id: str,
        asset_set_id: str,
        validate_only: bool = False,
    ) -> dict:
        """Propose unlinking an AssetSet from a campaign."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        campaign = _id(campaign_id, "campaign_id")
        set_id = _id(asset_set_id, "asset_set_id")
        resource = f"customers/{customer}/campaignAssetSets/{campaign}~{set_id}"
        operation = ctx.client.raw.get_type("CampaignAssetSetOperation")
        operation.remove = resource

        def execute():
            return ctx.client.mutate(
                "CampaignAssetSetService", customer, [operation], validate_only=validate_only
            )

        return ctx.safety.propose(
            tool_name="remove_asset_set_from_campaign",
            customer_id=customer,
            description=f"Remove AssetSet {set_id} from campaign {campaign}",
            payload={"campaign_id": campaign, "asset_set_id": set_id, "validate_only": validate_only},
            execute=execute,
        )

    @mcp.tool()
    def list_ad_group_asset_sets(customer_id: str, ad_group_id: str | None = None) -> dict:
        """List AssetSets linked to ad groups."""
        where = ""
        if ad_group_id is not None:
            ag_id = _id(ad_group_id, "ad_group_id")
            where = f"WHERE ad_group.id = {ag_id}"
        rows = ctx.client.search(
            customer_id,
            f"""
            SELECT
                ad_group_asset_set.resource_name,
                ad_group_asset_set.ad_group,
                ad_group_asset_set.asset_set,
                ad_group_asset_set.status,
                asset_set.id,
                asset_set.name,
                asset_set.type
            FROM ad_group_asset_set
            {where}
            ORDER BY ad_group_asset_set.resource_name
            """,
        )
        return {"ad_group_asset_sets": rows, "count": len(rows)}

    @mcp.tool()
    def attach_asset_set_to_ad_group(
        customer_id: str,
        ad_group_id: str,
        asset_set_resource_name: str,
        validate_only: bool = False,
    ) -> dict:
        """Propose linking an AssetSet to an ad group."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        ad_group = _id(ad_group_id, "ad_group_id")
        asset_set = _owned(ctx, customer, asset_set_resource_name, "asset_set_resource_name")
        operation = ctx.client.raw.get_type("AdGroupAssetSetOperation")
        operation.create.ad_group = f"customers/{customer}/adGroups/{ad_group}"
        operation.create.asset_set = asset_set

        def execute():
            return ctx.client.mutate(
                "AdGroupAssetSetService", customer, [operation], validate_only=validate_only
            )

        return ctx.safety.propose(
            tool_name="attach_asset_set_to_ad_group",
            customer_id=customer,
            description=f"Attach AssetSet {asset_set} to ad group {ad_group}",
            payload={"ad_group_id": ad_group, "asset_set_resource_name": asset_set, "validate_only": validate_only},
            execute=execute,
        )

    @mcp.tool()
    def remove_asset_set_from_ad_group(
        customer_id: str,
        ad_group_id: str,
        asset_set_id: str,
        validate_only: bool = False,
    ) -> dict:
        """Propose unlinking an AssetSet from an ad group."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        ad_group = _id(ad_group_id, "ad_group_id")
        set_id = _id(asset_set_id, "asset_set_id")
        resource = f"customers/{customer}/adGroupAssetSets/{ad_group}~{set_id}"
        operation = ctx.client.raw.get_type("AdGroupAssetSetOperation")
        operation.remove = resource

        def execute():
            return ctx.client.mutate(
                "AdGroupAssetSetService", customer, [operation], validate_only=validate_only
            )

        return ctx.safety.propose(
            tool_name="remove_asset_set_from_ad_group",
            customer_id=customer,
            description=f"Remove AssetSet {set_id} from ad group {ad_group}",
            payload={"ad_group_id": ad_group, "asset_set_id": set_id, "validate_only": validate_only},
            execute=execute,
        )
