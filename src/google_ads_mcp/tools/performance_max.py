"""Performance Max: campaign creation and asset groups.

PMax is structurally different from Search: there are no ad groups or
keywords. A campaign holds one or more Asset Groups, each a self-contained
bundle of creative (headlines, descriptions, images, logos) plus its own
final URL, that Google's automation assembles into ads across all
Google inventory (Search, Display, YouTube, Discover, Gmail, Maps).

This module covers create-and-launch, asset group editing (text, image,
video), status control, Shopping-listing scoping via listing group filters
(add_asset_group_listing_filter), and audience/search-theme signals used
to steer PMax's automated targeting (add_asset_group_signal).
"""

from __future__ import annotations

from google.protobuf import field_mask_pb2

from ..context import AppContext


def register(mcp, ctx: AppContext) -> None:
    @mcp.tool()
    def create_performance_max_campaign(
        customer_id: str,
        name: str,
        campaign_budget_resource_name: str,
        target_cpa: float | None = None,
        target_roas: float | None = None,
    ) -> dict:
        """Propose creating a Performance Max campaign shell. Created PAUSED.

        A PMax campaign needs at least one Asset Group before it can serve —
        follow up with create_asset_group. Create a budget first with
        create_campaign_budget.

        Args:
            target_cpa / target_roas: At most one may be set. If neither is
                set, the campaign uses Maximize Conversions with no target.
        """
        if target_cpa is not None and target_roas is not None:
            raise ValueError("Set at most one of target_cpa or target_roas, not both.")

        client = ctx.client.raw
        operation = client.get_type("CampaignOperation")
        campaign = operation.create
        campaign.name = name
        campaign.campaign_budget = campaign_budget_resource_name
        campaign.advertising_channel_type = (
            client.enums.AdvertisingChannelTypeEnum.PERFORMANCE_MAX
        )
        campaign.status = client.enums.CampaignStatusEnum.PAUSED

        if target_cpa is not None:
            from ..client import micros

            campaign.target_cpa.target_cpa_micros = micros(target_cpa)
        elif target_roas is not None:
            campaign.target_roas.target_roas = target_roas
        else:
            campaign.maximize_conversions.SetInParent()

        description = (
            f"Create Performance Max campaign '{name}', created PAUSED "
            f"(add an asset group before enabling)"
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
    ) -> dict:
        """Propose creating an Asset Group inside a Performance Max campaign.
        Created PAUSED.

        This is text-only (no image/logo assets attached) — a workable
        starting point Google's automation can serve with generic imagery
        pulled from the landing page, but a full creative build should add
        image assets afterward (list_campaign_assets / create_sitelink_asset
        style tools don't cover PMax image assets yet — attach via the UI
        for now).

        Args:
            headlines: 3-5 strings, each <=30 characters.
            long_headline: 1 string, <=90 characters.
            descriptions: 1-5 strings, each <=90 characters.
        """
        if not (3 <= len(headlines) <= 5):
            raise ValueError("Provide between 3 and 5 headlines.")
        if any(len(h) > 30 for h in headlines):
            raise ValueError("Each headline must be 30 characters or fewer.")
        if len(long_headline) > 90:
            raise ValueError("long_headline must be 90 characters or fewer.")
        if not (1 <= len(descriptions) <= 5):
            raise ValueError("Provide between 1 and 5 descriptions.")
        if any(len(d) > 90 for d in descriptions):
            raise ValueError("Each description must be 90 characters or fewer.")

        client = ctx.client.raw
        customer_id_clean = customer_id.replace("-", "")

        campaign_resource_name = client.get_service("CampaignService").campaign_path(
            customer_id_clean, campaign_id
        )

        description_text = (
            f"Create Asset Group '{name}' in PMax campaign {campaign_id}, created PAUSED "
            f"({len(headlines)} headlines, {len(descriptions)} descriptions)"
        )

        def execute():
            # Step 1: create the text assets (headline / long headline /
            # description / business name are all Asset resources in PMax).
            text_values = (
                [(h, "headline") for h in headlines]
                + [(long_headline, "long_headline")]
                + [(d, "description") for d in descriptions]
                + [(business_name, "business_name")]
            )
            asset_ops = []
            for text, _kind in text_values:
                op = client.get_type("AssetOperation")
                op.create.text_asset.text = text
                asset_ops.append(op)

            asset_result = ctx.client.mutate("AssetService", customer_id, asset_ops)
            created_resource_names = [r.resource_name for r in asset_result.results]

            n_headlines = len(headlines)
            headline_assets = created_resource_names[:n_headlines]
            long_headline_asset = created_resource_names[n_headlines]
            n_descriptions = len(descriptions)
            description_assets = created_resource_names[
                n_headlines + 1 : n_headlines + 1 + n_descriptions
            ]
            business_name_asset = created_resource_names[-1]

            # Step 2: create the asset group itself.
            ag_operation = client.get_type("AssetGroupOperation")
            asset_group = ag_operation.create
            asset_group.name = name
            asset_group.campaign = campaign_resource_name
            asset_group.final_urls.extend(final_urls)
            asset_group.status = client.enums.AssetGroupStatusEnum.PAUSED
            ag_result = ctx.client.mutate(
                "AssetGroupService", customer_id, [ag_operation]
            )
            asset_group_resource_name = ag_result.results[0].resource_name

            # Step 3: link each text asset to the asset group with its field type.
            field_map = (
                [(a, "HEADLINE") for a in headline_assets]
                + [(long_headline_asset, "LONG_HEADLINE")]
                + [(a, "DESCRIPTION") for a in description_assets]
                + [(business_name_asset, "BUSINESS_NAME")]
            )
            link_ops = []
            for asset_resource_name, field_type in field_map:
                link_op = client.get_type("AssetGroupAssetOperation")
                link = link_op.create
                link.asset_group = asset_group_resource_name
                link.asset = asset_resource_name
                link.field_type = client.enums.AssetFieldTypeEnum[field_type].value
                link_ops.append(link_op)

            ctx.client.mutate("AssetGroupAssetService", customer_id, link_ops)

            return {
                "asset_group_resource_name": asset_group_resource_name,
                "assets_created": len(created_resource_names),
                "assets_linked": len(link_ops),
            }

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
            },
            execute=execute,
        )

    @mcp.tool()
    def update_asset_group_final_urls(
        customer_id: str, asset_group_id: str, final_urls: list[str]
    ) -> dict:
        """Propose replacing an existing Asset Group's final URL(s) (the
        landing page it sends traffic to). Use this instead of
        create_asset_group when the asset group already exists and only
        the destination URL needs to change (e.g. after a site migration)."""
        client = ctx.client.raw
        customer_id_clean = customer_id.replace("-", "")

        operation = client.get_type("AssetGroupOperation")
        resource_name = client.get_service("AssetGroupService").asset_group_path(
            customer_id_clean, asset_group_id
        )
        operation.update.resource_name = resource_name
        operation.update.final_urls.extend(final_urls)
        operation.update_mask.CopyFrom(
            field_mask_pb2.FieldMask(paths=["final_urls"])
        )

        description = (
            f"Update asset group {asset_group_id} final_urls -> {final_urls}"
        )

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
        customer_id: str,
        asset_group_id: str,
        text: str,
        field_type: str,
    ) -> dict:
        """Propose creating a new text asset (headline / long_headline /
        description / business_name) and linking it into an existing
        Performance Max Asset Group.

        Args:
            field_type: One of HEADLINE, LONG_HEADLINE, DESCRIPTION,
                BUSINESS_NAME. Character limits: HEADLINE <=30,
                LONG_HEADLINE <=90, DESCRIPTION <=90.
        """
        limits = {"HEADLINE": 30, "LONG_HEADLINE": 90, "DESCRIPTION": 90}
        if field_type in limits and len(text) > limits[field_type]:
            raise ValueError(
                f"{field_type} text must be {limits[field_type]} characters or fewer."
            )

        client = ctx.client.raw
        customer_id_clean = customer_id.replace("-", "")

        asset_group_resource_name = client.get_service(
            "AssetGroupService"
        ).asset_group_path(customer_id_clean, asset_group_id)

        description = (
            f"Add {field_type} text asset '{text}' to asset group {asset_group_id}"
        )

        def execute():
            asset_operation = client.get_type("AssetOperation")
            asset_operation.create.text_asset.text = text
            asset_result = ctx.client.mutate(
                "AssetService", customer_id, [asset_operation]
            )
            asset_resource_name = asset_result.results[0].resource_name

            link_operation = client.get_type("AssetGroupAssetOperation")
            link = link_operation.create
            link.asset_group = asset_group_resource_name
            link.asset = asset_resource_name
            link.field_type = client.enums.AssetFieldTypeEnum[field_type].value

            link_result = ctx.client.mutate(
                "AssetGroupAssetService", customer_id, [link_operation]
            )
            return {
                "asset_resource_name": asset_resource_name,
                "asset_group_asset_resource_name": link_result.results[0].resource_name,
            }

        return ctx.safety.propose(
            tool_name="add_asset_group_text_asset",
            customer_id=customer_id,
            description=description,
            payload={
                "asset_group_id": asset_group_id,
                "text": text,
                "field_type": field_type,
            },
            execute=execute,
        )

    @mcp.tool()
    def remove_asset_group_asset(
        customer_id: str,
        asset_group_id: str,
        asset_id: str,
        field_type: str,
    ) -> dict:
        """Propose unlinking a text/image asset from a Performance Max
        Asset Group (does not delete the underlying Asset resource, just
        detaches it from this asset group).

        Args:
            field_type: The AssetFieldType the asset is linked as (e.g.
                HEADLINE, LONG_HEADLINE, DESCRIPTION, MARKETING_IMAGE) —
                must match how it was attached.
        """
        client = ctx.client.raw
        customer_id_clean = customer_id.replace("-", "")

        # Validate the name is a real AssetFieldType before using it —
        # the path builder wants the enum *name* (str), not its numeric value.
        client.enums.AssetFieldTypeEnum[field_type]

        operation = client.get_type("AssetGroupAssetOperation")
        operation.remove = client.get_service(
            "AssetGroupAssetService"
        ).asset_group_asset_path(
            customer_id_clean, asset_group_id, asset_id, field_type
        )

        description = (
            f"Unlink {field_type} asset {asset_id} from asset group {asset_group_id}"
        )

        def execute():
            return ctx.client.mutate(
                "AssetGroupAssetService", customer_id, [operation]
            )

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
        customer_id: str,
        asset_group_id: str,
        image_url: str,
        field_type: str,
    ) -> dict:
        """Propose downloading an image from a public HTTPS URL, uploading it
        as an Asset, and linking it into an existing Performance Max Asset
        Group. This is what was missing to add real creative (not just text)
        to a PMax asset group after create_asset_group.

        Args:
            image_url: Public HTTPS URL of the image. Downloaded server-side
                at confirm time.
            field_type: One of MARKETING_IMAGE (min 1200x628, landscape),
                SQUARE_MARKETING_IMAGE (1:1), PORTRAIT_MARKETING_IMAGE (4:5),
                LOGO (min 1200x1200, 1:1), LANDSCAPE_LOGO (4:1).
        """
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
            f"Add {field_type} image asset (from {image_url}) to asset group "
            f"{asset_group_id}"
        )

        def execute():
            import urllib.request

            with urllib.request.urlopen(image_url, timeout=30) as response:
                image_bytes = response.read()

            asset_operation = client.get_type("AssetOperation")
            asset_operation.create.image_asset.data = image_bytes
            asset_result = ctx.client.mutate(
                "AssetService", customer_id, [asset_operation]
            )
            asset_resource_name = asset_result.results[0].resource_name

            link_operation = client.get_type("AssetGroupAssetOperation")
            link = link_operation.create
            link.asset_group = asset_group_resource_name
            link.asset = asset_resource_name
            link.field_type = client.enums.AssetFieldTypeEnum[field_type].value

            link_result = ctx.client.mutate(
                "AssetGroupAssetService", customer_id, [link_operation]
            )
            return {
                "asset_resource_name": asset_resource_name,
                "asset_group_asset_resource_name": link_result.results[0].resource_name,
            }

        return ctx.safety.propose(
            tool_name="add_asset_group_image_asset",
            customer_id=customer_id,
            description=description,
            payload={
                "asset_group_id": asset_group_id,
                "image_url": image_url,
                "field_type": field_type,
            },
            execute=execute,
        )

    @mcp.tool()
    def add_asset_group_video_asset(
        customer_id: str,
        asset_group_id: str,
        youtube_video_id: str,
    ) -> dict:
        """Propose linking an existing YouTube video into a Performance Max
        Asset Group as a VIDEO asset. The video must already be public or
        unlisted on YouTube — this does not upload video files.

        Args:
            youtube_video_id: The 11-character ID from the YouTube URL.
        """
        client = ctx.client.raw
        customer_id_clean = customer_id.replace("-", "")

        asset_group_resource_name = client.get_service(
            "AssetGroupService"
        ).asset_group_path(customer_id_clean, asset_group_id)

        description = (
            f"Link YouTube video {youtube_video_id} to asset group {asset_group_id}"
        )

        def execute():
            asset_operation = client.get_type("AssetOperation")
            asset_operation.create.youtube_video_asset.youtube_video_id = (
                youtube_video_id
            )
            asset_result = ctx.client.mutate(
                "AssetService", customer_id, [asset_operation]
            )
            asset_resource_name = asset_result.results[0].resource_name

            link_operation = client.get_type("AssetGroupAssetOperation")
            link = link_operation.create
            link.asset_group = asset_group_resource_name
            link.asset = asset_resource_name
            link.field_type = client.enums.AssetFieldTypeEnum.VIDEO.value

            link_result = ctx.client.mutate(
                "AssetGroupAssetService", customer_id, [link_operation]
            )
            return {
                "asset_resource_name": asset_resource_name,
                "asset_group_asset_resource_name": link_result.results[0].resource_name,
            }

        return ctx.safety.propose(
            tool_name="add_asset_group_video_asset",
            customer_id=customer_id,
            description=description,
            payload={
                "asset_group_id": asset_group_id,
                "youtube_video_id": youtube_video_id,
            },
            execute=execute,
        )

    @mcp.tool()
    def update_asset_group_status(
        customer_id: str, asset_group_id: str, status: str
    ) -> dict:
        """Propose pausing or enabling a single Asset Group within a PMax
        campaign, without touching the campaign itself or other asset groups.

        Args:
            status: ENABLED or PAUSED.
        """
        client = ctx.client.raw
        customer_id_clean = customer_id.replace("-", "")

        operation = client.get_type("AssetGroupOperation")
        resource_name = client.get_service("AssetGroupService").asset_group_path(
            customer_id_clean, asset_group_id
        )
        operation.update.resource_name = resource_name
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
        """Propose adding a Listing Group Filter to a Performance Max Asset
        Group, restricting which products from the linked Shopping/Merchant
        Center feed that asset group is allowed to advertise.

        Without any listing group filter, a PMax asset group with a Shopping
        listing source can advertise the ENTIRE product catalog — this is
        how you scope one asset group to (for example) only one brand or
        product line, so its creative/messaging matches what it's actually
        selling.

        This creates a two-level tree under the asset group's root: a
        top-level "everything else" subdivision plus one filtered unit for
        the dimension you specify. For multi-dimension trees (e.g. brand AND
        product type together), build them one call at a time and refer to
        Google's Listing Group Filter documentation for tree structure rules.

        Args:
            product_condition: One of NEW, USED, REFURBISHED. Exactly one of
                product_condition / product_brand / product_item_id /
                product_type_l1 should be set per call.
            product_brand: Exact brand string as it appears in the feed.
            product_item_id: Exact Merchant Center item ID.
            product_type_l1: Top-level product type/category string from the feed.
        """
        dims_set = [
            d
            for d in (product_condition, product_brand, product_item_id, product_type_l1)
            if d is not None
        ]
        if len(dims_set) != 1:
            raise ValueError(
                "Set exactly one of product_condition, product_brand, "
                "product_item_id, product_type_l1 per call."
            )

        client = ctx.client.raw
        customer_id_clean = customer_id.replace("-", "")

        asset_group_resource_name = client.get_service(
            "AssetGroupService"
        ).asset_group_path(customer_id_clean, asset_group_id)

        description = (
            f"Add listing group filter to asset group {asset_group_id}: "
            f"condition={product_condition} brand={product_brand} "
            f"item_id={product_item_id} type_l1={product_type_l1}"
        )

        def execute():
            # Root "everything" subdivision for this asset group (required
            # before any filtered unit can be added under it).
            root_op = client.get_type("AssetGroupListingGroupFilterOperation")
            root = root_op.create
            root.asset_group = asset_group_resource_name
            root.type_ = client.enums.ListingGroupFilterTypeEnum.SUBDIVISION
            root.listing_source = (
                client.enums.ListingGroupFilterListingSourceEnum.SHOPPING
            )
            root_result = ctx.client.mutate(
                "AssetGroupListingGroupFilterService", customer_id, [root_op]
            )
            root_resource_name = root_result.results[0].resource_name

            unit_op = client.get_type("AssetGroupListingGroupFilterOperation")
            unit = unit_op.create
            unit.asset_group = asset_group_resource_name
            unit.type_ = client.enums.ListingGroupFilterTypeEnum.UNIT
            unit.listing_source = (
                client.enums.ListingGroupFilterListingSourceEnum.SHOPPING
            )
            unit.parent_listing_group_filter = root_resource_name

            case_value = unit.case_value
            if product_condition is not None:
                case_value.product_condition.condition = (
                    client.enums.ListingGroupFilterProductConditionEnum[
                        product_condition
                    ].value
                )
            elif product_brand is not None:
                case_value.product_brand.value = product_brand
            elif product_item_id is not None:
                case_value.product_item_id.value = product_item_id
            elif product_type_l1 is not None:
                case_value.product_type.level = (
                    client.enums.ListingGroupFilterProductTypeLevelEnum.LEVEL1
                )
                case_value.product_type.value = product_type_l1

            unit_result = ctx.client.mutate(
                "AssetGroupListingGroupFilterService", customer_id, [unit_op]
            )

            return {
                "root_subdivision_resource_name": root_resource_name,
                "unit_resource_name": unit_result.results[0].resource_name,
            }

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
        """List the listing group filter tree(s) for PMax asset groups —
        shows how each asset group's Shopping product scope is subdivided."""
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
        """List asset groups, optionally filtered to one PMax campaign."""
        where = f"WHERE campaign.id = {campaign_id}" if campaign_id else ""
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
        """Propose adding an audience or search-theme signal to a PMax asset
        group — this is how you point Google's automation toward the
        customers/intent most likely to convert, since PMax has no manual
        keyword or audience targeting otherwise. Signals are a starting
        point/hint, not a hard restriction — PMax can still serve beyond them.

        Args:
            signal_type: "AUDIENCE" (pass audience_resource_name — a user
                list, custom audience, or affinity/in-market segment
                resource name) or "SEARCH_THEME" (pass search_theme_text —
                a short phrase describing likely search intent, similar to
                a broad-match keyword).
        """
        if signal_type == "AUDIENCE":
            if not audience_resource_name:
                raise ValueError(
                    "audience_resource_name is required when signal_type='AUDIENCE'."
                )
        elif signal_type == "SEARCH_THEME":
            if not search_theme_text:
                raise ValueError(
                    "search_theme_text is required when signal_type='SEARCH_THEME'."
                )
        else:
            raise ValueError('signal_type must be "AUDIENCE" or "SEARCH_THEME".')

        client = ctx.client.raw
        customer_id_clean = customer_id.replace("-", "")
        asset_group_resource_name = client.get_service(
            "AssetGroupService"
        ).asset_group_path(customer_id_clean, asset_group_id)

        operation = client.get_type("AssetGroupSignalOperation")
        signal = operation.create
        signal.asset_group = asset_group_resource_name

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
            return ctx.client.mutate(
                "AssetGroupSignalService", customer_id, [operation]
            )

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
        """List the audience/search-theme signals attached to PMax asset groups."""
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
