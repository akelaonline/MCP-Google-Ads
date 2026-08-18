"""Performance Max tools compatible with Google Ads API v25."""

from __future__ import annotations

from google.protobuf import field_mask_pb2

from ..campaign_compat import (
    DEFAULT_EU_POLITICAL_ADVERTISING,
    apply_required_campaign_fields,
)
from ..context import AppContext
from ..net import fetch_public_https_image

_PMAX_IMAGE_MAX_BYTES = 5_120_000


def register(mcp, ctx: AppContext) -> None:
    @mcp.tool()
    def create_performance_max_campaign(
        customer_id: str,
        name: str,
        campaign_budget_resource_name: str,
        target_cpa: float | None = None,
        target_roas: float | None = None,
        contains_eu_political_advertising: str = DEFAULT_EU_POLITICAL_ADVERTISING,
    ) -> dict:
        """Propose creating a standard Performance Max campaign shell."""
        if target_cpa is not None and target_roas is not None:
            raise ValueError("Set at most one of target_cpa or target_roas, not both.")
        if target_cpa is not None and target_cpa <= 0:
            raise ValueError("target_cpa must be greater than 0.")
        if target_roas is not None and target_roas <= 0:
            raise ValueError("target_roas must be greater than 0.")

        client = ctx.client.raw
        operation = client.get_type("CampaignOperation")
        campaign = operation.create
        campaign.name = name
        campaign.campaign_budget = campaign_budget_resource_name
        campaign.advertising_channel_type = (
            client.enums.AdvertisingChannelTypeEnum.PERFORMANCE_MAX
        )
        campaign.status = client.enums.CampaignStatusEnum.PAUSED
        campaign.brand_guidelines_enabled = False
        apply_required_campaign_fields(
            client,
            campaign,
            contains_eu_political_advertising=contains_eu_political_advertising,
        )

        if target_cpa is not None:
            from ..client import micros

            campaign.maximize_conversions.target_cpa_micros = micros(target_cpa)
        elif target_roas is not None:
            campaign.maximize_conversion_value.target_roas = target_roas
        else:
            client.copy_from(
                campaign.maximize_conversions,
                client.get_type("MaximizeConversions"),
            )

        description = (
            f"Create Performance Max campaign '{name}', created PAUSED; "
            "brand guidelines disabled for asset-group branding"
        )

        def execute():
            return ctx.client.mutate("CampaignService", customer_id, [operation])

        return ctx.safety.propose(
            tool_name="create_performance_max_campaign",
            customer_id=customer_id,
            description=description,
            payload={
                "name": name,
                "target_cpa": target_cpa,
                "target_roas": target_roas,
                "brand_guidelines_enabled": False,
                "contains_eu_political_advertising": contains_eu_political_advertising,
            },
            execute=execute,
        )

    @mcp.tool()
    def create_asset_group(
        customer_id: str,
        campaign_id: str,
        name: str,
        final_urls: list[str],
        headlines: list[str],
        long_headline: str,
        descriptions: list[str],
        business_name: str,
        marketing_image_urls: list[str] | None = None,
        square_marketing_image_urls: list[str] | None = None,
        logo_image_urls: list[str] | None = None,
    ) -> dict:
        """Create a complete non-retail PMax AssetGroup in one atomic request."""
        _validate_asset_group_inputs(
            final_urls,
            headlines,
            long_headline,
            descriptions,
            business_name,
            marketing_image_urls,
            square_marketing_image_urls,
            logo_image_urls,
        )

        client = ctx.client.raw
        customer_id_clean = customer_id.replace("-", "")
        ga_service = client.get_service("GoogleAdsService")
        campaign_resource_name = ga_service.campaign_path(customer_id_clean, campaign_id)
        asset_group_temp_id = -1000
        asset_group_resource_name = ga_service.asset_group_path(
            customer_id_clean, asset_group_temp_id
        )
        description_text = (
            f"Create complete Asset Group '{name}' in PMax campaign {campaign_id} "
            "with required v25 assets; atomic mutation"
        )

        def execute():
            operations = []
            asset_refs_by_field: list[tuple[str, str]] = []
            next_temp_id = -1

            for text in headlines:
                ref, op, next_temp_id = _text_asset_operation(
                    client, customer_id_clean, text, next_temp_id
                )
                operations.append(op)
                asset_refs_by_field.append((ref, "HEADLINE"))

            ref, op, next_temp_id = _text_asset_operation(
                client, customer_id_clean, long_headline, next_temp_id
            )
            operations.append(op)
            asset_refs_by_field.append((ref, "LONG_HEADLINE"))

            for text in descriptions:
                ref, op, next_temp_id = _text_asset_operation(
                    client, customer_id_clean, text, next_temp_id
                )
                operations.append(op)
                asset_refs_by_field.append((ref, "DESCRIPTION"))

            ref, op, next_temp_id = _text_asset_operation(
                client, customer_id_clean, business_name, next_temp_id
            )
            operations.append(op)
            asset_refs_by_field.append((ref, "BUSINESS_NAME"))

            for url, field_type in (
                [(url, "MARKETING_IMAGE") for url in marketing_image_urls or []]
                + [
                    (url, "SQUARE_MARKETING_IMAGE")
                    for url in square_marketing_image_urls or []
                ]
                + [(url, "LOGO") for url in logo_image_urls or []]
            ):
                ref, op, next_temp_id = _image_asset_operation(
                    client, customer_id_clean, url, next_temp_id
                )
                operations.append(op)
                asset_refs_by_field.append((ref, field_type))

            asset_group_mutate = client.get_type("MutateOperation")
            asset_group = asset_group_mutate.asset_group_operation.create
            asset_group.resource_name = asset_group_resource_name
            asset_group.name = name
            asset_group.campaign = campaign_resource_name
            asset_group.final_urls.extend(final_urls)
            asset_group.status = client.enums.AssetGroupStatusEnum.PAUSED
            operations.append(asset_group_mutate)

            for asset_resource_name, field_type in asset_refs_by_field:
                link_mutate = client.get_type("MutateOperation")
                link = link_mutate.asset_group_asset_operation.create
                link.asset_group = asset_group_resource_name
                link.asset = asset_resource_name
                link.field_type = client.enums.AssetFieldTypeEnum[field_type].value
                operations.append(link_mutate)

            return ctx.client.mutate_atomic(customer_id, operations)

        return ctx.safety.propose(
            tool_name="create_asset_group",
            customer_id=customer_id,
            description=description_text,
            payload={
                "campaign_id": campaign_id,
                "name": name,
                "final_urls": final_urls,
                "headlines": headlines,
                "long_headline": long_headline,
                "descriptions": descriptions,
                "business_name": business_name,
                "marketing_image_urls": marketing_image_urls,
                "square_marketing_image_urls": square_marketing_image_urls,
                "logo_image_urls": logo_image_urls,
            },
            execute=execute,
        )

    @mcp.tool()
    def update_asset_group_final_urls(
        customer_id: str, asset_group_id: str, final_urls: list[str]
    ) -> dict:
        """Propose replacing an AssetGroup's final URLs."""
        if not final_urls:
            raise ValueError("Provide at least one final URL.")
        client = ctx.client.raw
        operation = client.get_type("AssetGroupOperation")
        operation.update.resource_name = client.get_service(
            "AssetGroupService"
        ).asset_group_path(customer_id.replace("-", ""), asset_group_id)
        operation.update.final_urls.extend(final_urls)
        operation.update_mask.CopyFrom(field_mask_pb2.FieldMask(paths=["final_urls"]))
        description = f"Update asset group {asset_group_id} final_urls -> {final_urls}"

        def execute():
            return ctx.client.mutate("AssetGroupService", customer_id, [operation])

        return ctx.safety.propose(
            tool_name="update_asset_group_final_urls",
            customer_id=customer_id,
            description=description,
            payload={"asset_group_id": asset_group_id, "final_urls": final_urls},
            execute=execute,
        )

    @mcp.tool()
    def add_asset_group_text_asset(
        customer_id: str, asset_group_id: str, text: str, field_type: str
    ) -> dict:
        """Create a text Asset and link it to an existing PMax AssetGroup atomically."""
        valid = {
            "HEADLINE": 30,
            "LONG_HEADLINE": 90,
            "DESCRIPTION": 90,
            "BUSINESS_NAME": 25,
        }
        if field_type not in valid:
            raise ValueError(f"field_type must be one of {sorted(valid)}.")
        if not text or len(text) > valid[field_type]:
            raise ValueError(
                f"{field_type} text must be 1-{valid[field_type]} characters."
            )

        client = ctx.client.raw
        customer_id_clean = customer_id.replace("-", "")
        asset_group_resource_name = client.get_service(
            "AssetGroupService"
        ).asset_group_path(customer_id_clean, asset_group_id)
        description = f"Add {field_type} text asset to asset group {asset_group_id} atomically"

        def execute():
            asset_ref, asset_mutate, _ = _text_asset_operation(
                client, customer_id_clean, text, -1
            )
            link_mutate = client.get_type("MutateOperation")
            link = link_mutate.asset_group_asset_operation.create
            link.asset_group = asset_group_resource_name
            link.asset = asset_ref
            link.field_type = client.enums.AssetFieldTypeEnum[field_type].value
            return ctx.client.mutate_atomic(customer_id, [asset_mutate, link_mutate])

        return ctx.safety.propose(
            tool_name="add_asset_group_text_asset",
            customer_id=customer_id,
            description=description,
            payload={"asset_group_id": asset_group_id, "text": text, "field_type": field_type},
            execute=execute,
        )

    @mcp.tool()
    def remove_asset_group_asset(
        customer_id: str, asset_group_id: str, asset_id: str, field_type: str
    ) -> dict:
        """Propose unlinking an asset from a PMax AssetGroup."""
        client = ctx.client.raw
        client.enums.AssetFieldTypeEnum[field_type]
        operation = client.get_type("AssetGroupAssetOperation")
        operation.remove = client.get_service(
            "AssetGroupAssetService"
        ).asset_group_asset_path(
            customer_id.replace("-", ""), asset_group_id, asset_id, field_type
        )
        description = (
            f"Unlink {field_type} asset {asset_id} from asset group {asset_group_id}"
        )

        def execute():
            return ctx.client.mutate("AssetGroupAssetService", customer_id, [operation])

        return ctx.safety.propose(
            tool_name="remove_asset_group_asset",
            customer_id=customer_id,
            description=description,
            payload={
                "asset_group_id": asset_group_id,
                "asset_id": asset_id,
                "field_type": field_type,
            },
            execute=execute,
        )

    @mcp.tool()
    def add_asset_group_image_asset(
        customer_id: str, asset_group_id: str, image_url: str, field_type: str
    ) -> dict:
        """Upload an image Asset and link it to PMax atomically."""
        valid_types = {
            "MARKETING_IMAGE",
            "SQUARE_MARKETING_IMAGE",
            "PORTRAIT_MARKETING_IMAGE",
            "LOGO",
            "LANDSCAPE_LOGO",
        }
        if field_type not in valid_types:
            raise ValueError(f"field_type must be one of {sorted(valid_types)}.")
        client = ctx.client.raw
        customer_id_clean = customer_id.replace("-", "")
        asset_group_resource_name = client.get_service(
            "AssetGroupService"
        ).asset_group_path(customer_id_clean, asset_group_id)
        description = (
            f"Add {field_type} image asset from {image_url} to asset group "
            f"{asset_group_id} atomically"
        )

        def execute():
            asset_ref, asset_mutate, _ = _image_asset_operation(
                client, customer_id_clean, image_url, -1
            )
            link_mutate = client.get_type("MutateOperation")
            link = link_mutate.asset_group_asset_operation.create
            link.asset_group = asset_group_resource_name
            link.asset = asset_ref
            link.field_type = client.enums.AssetFieldTypeEnum[field_type].value
            return ctx.client.mutate_atomic(customer_id, [asset_mutate, link_mutate])

        return ctx.safety.propose(
            tool_name="add_asset_group_image_asset",
            customer_id=customer_id,
            description=description,
            payload={"asset_group_id": asset_group_id, "image_url": image_url, "field_type": field_type},
            execute=execute,
        )

    @mcp.tool()
    def add_asset_group_video_asset(
        customer_id: str, asset_group_id: str, youtube_video_id: str
    ) -> dict:
        """Create a YouTube video Asset and link it to PMax atomically."""
        if len(youtube_video_id) != 11:
            raise ValueError("youtube_video_id must be the 11-character YouTube ID.")
        client = ctx.client.raw
        customer_id_clean = customer_id.replace("-", "")
        ga_service = client.get_service("GoogleAdsService")
        asset_group_resource_name = ga_service.asset_group_path(
            customer_id_clean, asset_group_id
        )
        temp_asset_name = ga_service.asset_path(customer_id_clean, -1)
        asset_mutate = client.get_type("MutateOperation")
        asset_mutate.asset_operation.create.resource_name = temp_asset_name
        asset_mutate.asset_operation.create.youtube_video_asset.youtube_video_id = (
            youtube_video_id
        )
        link_mutate = client.get_type("MutateOperation")
        link = link_mutate.asset_group_asset_operation.create
        link.asset_group = asset_group_resource_name
        link.asset = temp_asset_name
        link.field_type = client.enums.AssetFieldTypeEnum.YOUTUBE_VIDEO.value
        description = (
            f"Link YouTube video {youtube_video_id} to asset group {asset_group_id} atomically"
        )

        def execute():
            return ctx.client.mutate_atomic(customer_id, [asset_mutate, link_mutate])

        return ctx.safety.propose(
            tool_name="add_asset_group_video_asset",
            customer_id=customer_id,
            description=description,
            payload={"asset_group_id": asset_group_id, "youtube_video_id": youtube_video_id},
            execute=execute,
        )

    @mcp.tool()
    def update_asset_group_status(
        customer_id: str, asset_group_id: str, status: str
    ) -> dict:
        """Propose pausing or enabling an AssetGroup."""
        if status not in {"ENABLED", "PAUSED"}:
            raise ValueError("status must be ENABLED or PAUSED.")
        client = ctx.client.raw
        operation = client.get_type("AssetGroupOperation")
        operation.update.resource_name = client.get_service(
            "AssetGroupService"
        ).asset_group_path(customer_id.replace("-", ""), asset_group_id)
        operation.update.status = client.enums.AssetGroupStatusEnum[status].value
        operation.update_mask.CopyFrom(field_mask_pb2.FieldMask(paths=["status"]))
        description = f"Set asset group {asset_group_id} status -> {status}"

        def execute():
            return ctx.client.mutate("AssetGroupService", customer_id, [operation])

        return ctx.safety.propose(
            tool_name="update_asset_group_status",
            customer_id=customer_id,
            description=description,
            payload={"asset_group_id": asset_group_id, "status": status},
            execute=execute,
        )

    @mcp.tool()
    def add_asset_group_listing_filter(
        customer_id: str,
        asset_group_id: str,
        campaign_id: str,
        product_condition: str | None = None,
        product_brand: str | None = None,
        product_item_id: str | None = None,
        product_type_l1: str | None = None,
    ) -> dict:
        """Scope a retail PMax AssetGroup to one product dimension."""
        dimensions = [
            value
            for value in (
                product_condition,
                product_brand,
                product_item_id,
                product_type_l1,
            )
            if value is not None
        ]
        if len(dimensions) != 1:
            raise ValueError(
                "Set exactly one of product_condition, product_brand, "
                "product_item_id, product_type_l1."
            )

        client = ctx.client.raw
        customer_id_clean = customer_id.replace("-", "")
        ga_service = client.get_service("GoogleAdsService")
        asset_group_resource_name = ga_service.asset_group_path(
            customer_id_clean, asset_group_id
        )
        root_id, included_id, other_id = -1, -2, -3
        root_name = ga_service.asset_group_listing_group_filter_path(
            customer_id_clean, str(asset_group_id), str(root_id)
        )

        root_mutate = client.get_type("MutateOperation")
        root = root_mutate.asset_group_listing_group_filter_operation.create
        root.resource_name = root_name
        root.asset_group = asset_group_resource_name
        root.type_ = client.enums.ListingGroupFilterTypeEnum.SUBDIVISION.value
        root.listing_source = (
            client.enums.ListingGroupFilterListingSourceEnum.SHOPPING.value
        )

        included_mutate = client.get_type("MutateOperation")
        included = included_mutate.asset_group_listing_group_filter_operation.create
        included.resource_name = ga_service.asset_group_listing_group_filter_path(
            customer_id_clean, str(asset_group_id), str(included_id)
        )
        included.asset_group = asset_group_resource_name
        included.parent_listing_group_filter = root_name
        included.type_ = client.enums.ListingGroupFilterTypeEnum.UNIT_INCLUDED.value
        included.listing_source = (
            client.enums.ListingGroupFilterListingSourceEnum.SHOPPING.value
        )
        dimension_type = _set_listing_dimension(
            client,
            included.case_value,
            product_condition=product_condition,
            product_brand=product_brand,
            product_item_id=product_item_id,
            product_type_l1=product_type_l1,
        )

        other_mutate = client.get_type("MutateOperation")
        other = other_mutate.asset_group_listing_group_filter_operation.create
        other.resource_name = ga_service.asset_group_listing_group_filter_path(
            customer_id_clean, str(asset_group_id), str(other_id)
        )
        other.asset_group = asset_group_resource_name
        other.parent_listing_group_filter = root_name
        other.type_ = client.enums.ListingGroupFilterTypeEnum.UNIT_EXCLUDED.value
        other.listing_source = (
            client.enums.ListingGroupFilterListingSourceEnum.SHOPPING.value
        )
        _set_empty_listing_dimension(client, other.case_value, dimension_type)

        description = (
            f"Scope asset group {asset_group_id} to one {dimension_type} value and "
            "exclude the Other partition atomically"
        )

        def execute():
            return ctx.client.mutate_atomic(
                customer_id, [root_mutate, included_mutate, other_mutate]
            )

        return ctx.safety.propose(
            tool_name="add_asset_group_listing_filter",
            customer_id=customer_id,
            description=description,
            payload={
                "asset_group_id": asset_group_id,
                "campaign_id": campaign_id,
                "product_condition": product_condition,
                "product_brand": product_brand,
                "product_item_id": product_item_id,
                "product_type_l1": product_type_l1,
            },
            execute=execute,
        )

    @mcp.tool()
    def list_asset_group_listing_filters(
        customer_id: str, asset_group_id: str | None = None
    ) -> dict:
        """List PMax listing group filter trees."""
        where = (
            f"WHERE asset_group.id = {int(asset_group_id)}" if asset_group_id else ""
        )
        query = f"""
            SELECT
                asset_group.name, asset_group_listing_group_filter.id,
                asset_group_listing_group_filter.type,
                asset_group_listing_group_filter.case_value.product_brand.value,
                asset_group_listing_group_filter.case_value.product_item_id.value,
                asset_group_listing_group_filter.case_value.product_type.value,
                asset_group_listing_group_filter.parent_listing_group_filter
            FROM asset_group_listing_group_filter
            {where}
        """
        rows = ctx.client.search(customer_id, query)
        return {"filters": rows, "count": len(rows)}

    @mcp.tool()
    def list_asset_groups(customer_id: str, campaign_id: str | None = None) -> dict:
        """List asset groups, optionally for one PMax campaign."""
        where = f"WHERE campaign.id = {int(campaign_id)}" if campaign_id else ""
        query = f"""
            SELECT asset_group.id, asset_group.name, asset_group.status,
                   asset_group.campaign, campaign.name
            FROM asset_group
            {where}
            ORDER BY asset_group.name
        """
        rows = ctx.client.search(customer_id, query)
        return {"asset_groups": rows, "count": len(rows)}

    @mcp.tool()
    def add_asset_group_signal(
        customer_id: str,
        asset_group_id: str,
        signal_type: str,
        audience_resource_name: str | None = None,
        search_theme_text: str | None = None,
    ) -> dict:
        """Propose adding an audience or search-theme signal to PMax."""
        signal_type = signal_type.upper()
        if signal_type == "AUDIENCE":
            if not audience_resource_name:
                raise ValueError("audience_resource_name is required for AUDIENCE.")
        elif signal_type == "SEARCH_THEME":
            if not search_theme_text:
                raise ValueError("search_theme_text is required for SEARCH_THEME.")
        else:
            raise ValueError('signal_type must be "AUDIENCE" or "SEARCH_THEME".')

        client = ctx.client.raw
        operation = client.get_type("AssetGroupSignalOperation")
        signal = operation.create
        signal.asset_group = client.get_service("AssetGroupService").asset_group_path(
            customer_id.replace("-", ""), asset_group_id
        )
        if signal_type == "AUDIENCE":
            signal.audience.audience = audience_resource_name
            description = (
                f"Add audience signal {audience_resource_name} to asset group "
                f"{asset_group_id}"
            )
        else:
            signal.search_theme.text = search_theme_text
            description = (
                f"Add search theme signal '{search_theme_text}' to asset group "
                f"{asset_group_id}"
            )

        def execute():
            return ctx.client.mutate("AssetGroupSignalService", customer_id, [operation])

        return ctx.safety.propose(
            tool_name="add_asset_group_signal",
            customer_id=customer_id,
            description=description,
            payload={
                "asset_group_id": asset_group_id,
                "signal_type": signal_type,
                "audience_resource_name": audience_resource_name,
                "search_theme_text": search_theme_text,
            },
            execute=execute,
        )

    @mcp.tool()
    def list_asset_group_signals(
        customer_id: str, asset_group_id: str | None = None
    ) -> dict:
        """List audience/search-theme signals attached to PMax asset groups."""
        where = (
            f"WHERE asset_group.id = {int(asset_group_id)}" if asset_group_id else ""
        )
        query = f"""
            SELECT
                asset_group.name, asset_group_signal.asset_group,
                asset_group_signal.audience.audience,
                asset_group_signal.search_theme.text
            FROM asset_group_signal
            {where}
        """
        rows = ctx.client.search(customer_id, query)
        return {"signals": rows, "count": len(rows)}


def _validate_asset_group_inputs(
    final_urls,
    headlines,
    long_headline,
    descriptions,
    business_name,
    marketing_image_urls,
    square_marketing_image_urls,
    logo_image_urls,
) -> None:
    if not final_urls:
        raise ValueError("Provide at least one final URL.")
    if not (3 <= len(headlines) <= 15):
        raise ValueError("PMax requires 3-15 headlines.")
    if any(not h or len(h) > 30 for h in headlines):
        raise ValueError("Each PMax headline must be 1-30 characters.")
    if not long_headline or len(long_headline) > 90:
        raise ValueError("long_headline must be 1-90 characters.")
    if not (2 <= len(descriptions) <= 5):
        raise ValueError("PMax requires 2-5 descriptions.")
    if any(not d or len(d) > 90 for d in descriptions):
        raise ValueError("Each PMax description must be 1-90 characters.")
    if not any(len(d) <= 60 for d in descriptions):
        raise ValueError("At least one PMax description must be 60 characters or fewer.")
    if not business_name or len(business_name) > 25:
        raise ValueError("business_name must be 1-25 characters.")
    if not marketing_image_urls:
        raise ValueError("PMax requires at least one landscape marketing image.")
    if not square_marketing_image_urls:
        raise ValueError("PMax requires at least one square marketing image.")
    if not logo_image_urls:
        raise ValueError(
            "This MCP creates PMax with brand guidelines disabled, so at least "
            "one square logo is required in the AssetGroup."
        )


def _text_asset_operation(client, customer_id_clean: str, text: str, temp_id: int):
    ga_service = client.get_service("GoogleAdsService")
    resource_name = ga_service.asset_path(customer_id_clean, temp_id)
    mutate = client.get_type("MutateOperation")
    asset = mutate.asset_operation.create
    asset.resource_name = resource_name
    asset.text_asset.text = text
    return resource_name, mutate, temp_id - 1


def _image_asset_operation(client, customer_id_clean: str, url: str, temp_id: int):
    image_bytes = fetch_public_https_image(url, max_bytes=_PMAX_IMAGE_MAX_BYTES)
    ga_service = client.get_service("GoogleAdsService")
    resource_name = ga_service.asset_path(customer_id_clean, temp_id)
    mutate = client.get_type("MutateOperation")
    asset = mutate.asset_operation.create
    asset.resource_name = resource_name
    asset.type_ = client.enums.AssetTypeEnum.IMAGE.value
    asset.image_asset.data = image_bytes
    asset.image_asset.file_size = len(image_bytes)
    return resource_name, mutate, temp_id - 1


def _set_listing_dimension(
    client,
    case_value,
    *,
    product_condition,
    product_brand,
    product_item_id,
    product_type_l1,
) -> str:
    if product_condition is not None:
        case_value.product_condition.condition = (
            client.enums.ListingGroupFilterProductConditionEnum[
                product_condition.upper()
            ].value
        )
        return "PRODUCT_CONDITION"
    if product_brand is not None:
        case_value.product_brand.value = product_brand
        return "PRODUCT_BRAND"
    if product_item_id is not None:
        case_value.product_item_id.value = product_item_id
        return "PRODUCT_ITEM_ID"
    case_value.product_type.level = (
        client.enums.ListingGroupFilterProductTypeLevelEnum.LEVEL1.value
    )
    case_value.product_type.value = product_type_l1
    return "PRODUCT_TYPE"


def _set_empty_listing_dimension(client, case_value, dimension_type: str) -> None:
    """Set the same dimension with an empty value, representing the Other unit."""
    if dimension_type == "PRODUCT_CONDITION":
        case_value.product_condition.condition = (
            client.enums.ListingGroupFilterProductConditionEnum.UNSPECIFIED.value
        )
    elif dimension_type == "PRODUCT_BRAND":
        case_value.product_brand.value = ""
    elif dimension_type == "PRODUCT_ITEM_ID":
        case_value.product_item_id.value = ""
    else:
        case_value.product_type.level = (
            client.enums.ListingGroupFilterProductTypeLevelEnum.LEVEL1.value
        )
        case_value.product_type.value = ""
