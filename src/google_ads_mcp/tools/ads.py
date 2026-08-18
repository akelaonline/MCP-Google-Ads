"""Ad creative tools compatible with Google Ads API v25."""

from __future__ import annotations

from google.protobuf import field_mask_pb2

from ..campaign_compat import (
    DEFAULT_EU_POLITICAL_ADVERTISING,
    apply_required_campaign_fields,
)
from ..context import AppContext
from ..net import fetch_public_https_image


def register(mcp, ctx: AppContext) -> None:
    @mcp.tool()
    def create_responsive_search_ad(
        customer_id: str,
        ad_group_id: str,
        headlines: list[str],
        descriptions: list[str],
        final_urls: list[str],
        path1: str | None = None,
        path2: str | None = None,
    ) -> dict:
        """Propose creating a Responsive Search Ad. Created PAUSED."""
        _validate_rsa(headlines, descriptions, final_urls, path1, path2)

        client = ctx.client.raw
        operation = client.get_type("AdGroupAdOperation")
        ad_group_ad = operation.create
        ad_group_ad.ad_group = client.get_service("AdGroupService").ad_group_path(
            customer_id.replace("-", ""), ad_group_id
        )
        ad_group_ad.status = client.enums.AdGroupAdStatusEnum.PAUSED
        _populate_rsa(
            client,
            ad_group_ad.ad,
            headlines=headlines,
            descriptions=descriptions,
            final_urls=final_urls,
            path1=path1,
            path2=path2,
        )

        description = (
            f"Create Responsive Search Ad in ad group {ad_group_id} "
            f"({len(headlines)} headlines, {len(descriptions)} descriptions), "
            "created PAUSED"
        )

        def execute():
            return ctx.client.mutate("AdGroupAdService", customer_id, [operation])

        return ctx.safety.propose(
            tool_name="create_responsive_search_ad",
            customer_id=customer_id,
            description=description,
            payload={
                "ad_group_id": ad_group_id,
                "headlines": headlines,
                "descriptions": descriptions,
                "final_urls": final_urls,
                "path1": path1,
                "path2": path2,
            },
            execute=execute,
        )

    @mcp.tool()
    def create_responsive_display_ad(
        customer_id: str,
        ad_group_id: str,
        headlines: list[str],
        long_headline: str,
        descriptions: list[str],
        business_name: str,
        final_urls: list[str],
        marketing_image_urls: list[str] | None = None,
        logo_image_urls: list[str] | None = None,
        square_marketing_image_urls: list[str] | None = None,
    ) -> dict:
        """Propose creating a Responsive Display Ad atomically. Created PAUSED.

        API v25 requires at least one landscape marketing image and one square
        marketing image. Images are fetched before confirmation is sent to
        Google; the Asset resources and ad itself are then created in one
        atomic GoogleAdsService.Mutate request, so failed ad creation cannot
        leave orphan image assets behind.
        """
        if not (1 <= len(headlines) <= 5):
            raise ValueError("Provide between 1 and 5 headlines.")
        if any(len(h) > 30 for h in headlines):
            raise ValueError("Each headline must be 30 characters or fewer.")
        if len(long_headline) > 90:
            raise ValueError("long_headline must be 90 characters or fewer.")
        if not (1 <= len(descriptions) <= 5):
            raise ValueError("Provide between 1 and 5 descriptions.")
        if any(len(d) > 90 for d in descriptions):
            raise ValueError("Each description must be 90 characters or fewer.")
        if not business_name or len(business_name) > 25:
            raise ValueError("business_name is required and must be 25 characters or fewer.")
        if not final_urls:
            raise ValueError("Provide at least one final URL.")
        if not marketing_image_urls:
            raise ValueError(
                "API v25 Responsive Display Ads require at least one landscape "
                "marketing_image_urls entry."
            )
        if not square_marketing_image_urls:
            raise ValueError(
                "API v25 Responsive Display Ads require at least one "
                "square_marketing_image_urls entry."
            )

        client = ctx.client.raw
        customer_id_clean = customer_id.replace("-", "")
        ad_group_resource_name = client.get_service("AdGroupService").ad_group_path(
            customer_id_clean, ad_group_id
        )
        description_text = (
            f"Create Responsive Display Ad in ad group {ad_group_id} "
            f"({len(headlines)} headlines, {len(marketing_image_urls)} landscape, "
            f"{len(square_marketing_image_urls)} square images), created PAUSED"
        )

        def execute():
            operations = []
            next_temp_id = -1

            landscape_refs, landscape_ops, next_temp_id = _build_image_asset_operations(
                client,
                customer_id_clean,
                marketing_image_urls,
                next_temp_id,
            )
            operations.extend(landscape_ops)
            square_refs, square_ops, next_temp_id = _build_image_asset_operations(
                client,
                customer_id_clean,
                square_marketing_image_urls,
                next_temp_id,
            )
            operations.extend(square_ops)
            logo_refs, logo_ops, next_temp_id = _build_image_asset_operations(
                client,
                customer_id_clean,
                logo_image_urls or [],
                next_temp_id,
            )
            operations.extend(logo_ops)

            ad_operation = client.get_type("AdGroupAdOperation")
            ad_group_ad = ad_operation.create
            ad_group_ad.ad_group = ad_group_resource_name
            ad_group_ad.status = client.enums.AdGroupAdStatusEnum.PAUSED
            rda = ad_group_ad.ad.responsive_display_ad
            for text in headlines:
                rda.headlines.append(_text_asset(client, text))
            rda.long_headline.text = long_headline
            for text in descriptions:
                rda.descriptions.append(_text_asset(client, text))
            rda.business_name = business_name
            for resource_name in landscape_refs:
                rda.marketing_images.append(_image_ref(client, resource_name))
            for resource_name in square_refs:
                rda.square_marketing_images.append(_image_ref(client, resource_name))
            for resource_name in logo_refs:
                rda.logo_images.append(_image_ref(client, resource_name))
            ad_group_ad.ad.final_urls.extend(final_urls)
            operations.append(_wrap_mutate(client, "ad_group_ad_operation", ad_operation))

            return ctx.client.mutate_atomic(customer_id, operations)

        return ctx.safety.propose(
            tool_name="create_responsive_display_ad",
            customer_id=customer_id,
            description=description_text,
            payload={
                "ad_group_id": ad_group_id,
                "headlines": headlines,
                "long_headline": long_headline,
                "descriptions": descriptions,
                "business_name": business_name,
                "final_urls": final_urls,
                "marketing_image_urls": marketing_image_urls,
                "square_marketing_image_urls": square_marketing_image_urls,
                "logo_image_urls": logo_image_urls,
            },
            execute=execute,
        )

    @mcp.tool()
    def create_video_ad(
        customer_id: str,
        ad_group_id: str,
        youtube_video_id: str,
        headline: str,
        final_urls: list[str],
        description1: str | None = None,
        description2: str | None = None,
        companion_banner_asset_resource_name: str | None = None,
    ) -> dict:
        """Propose creating an in-stream YouTube video ad. Created PAUSED."""
        if len(youtube_video_id) != 11:
            raise ValueError("youtube_video_id must be the 11-character YouTube video ID.")
        if not headline or len(headline) > 15:
            raise ValueError("headline must be 1-15 characters.")
        if not final_urls:
            raise ValueError("Provide at least one final URL.")

        client = ctx.client.raw
        operation = client.get_type("AdGroupAdOperation")
        ad_group_ad = operation.create
        ad_group_ad.ad_group = client.get_service("AdGroupService").ad_group_path(
            customer_id.replace("-", ""), ad_group_id
        )
        ad_group_ad.status = client.enums.AdGroupAdStatusEnum.PAUSED

        video_ad = ad_group_ad.ad.video_ad
        video_ad.video.video_id = youtube_video_id
        video_ad.in_stream.action_button_label = headline
        video_ad.in_stream.action_headline = description1 or headline
        if companion_banner_asset_resource_name:
            video_ad.companion_banner.asset = companion_banner_asset_resource_name
        ad_group_ad.ad.final_urls.extend(final_urls)

        description = (
            f"Create in-stream video ad in ad group {ad_group_id} "
            f"(YouTube video {youtube_video_id}), created PAUSED"
        )

        def execute():
            return ctx.client.mutate("AdGroupAdService", customer_id, [operation])

        return ctx.safety.propose(
            tool_name="create_video_ad",
            customer_id=customer_id,
            description=description,
            payload={
                "ad_group_id": ad_group_id,
                "youtube_video_id": youtube_video_id,
                "headline": headline,
                "final_urls": final_urls,
                "description1": description1,
                "description2": description2,
                "companion_banner_asset_resource_name": companion_banner_asset_resource_name,
            },
            execute=execute,
        )

    @mcp.tool()
    def update_responsive_search_ad(
        customer_id: str,
        ad_group_id: str,
        ad_id: str,
        headlines: list[str] | None = None,
        descriptions: list[str] | None = None,
        final_urls: list[str] | None = None,
        path1: str | None = None,
        path2: str | None = None,
    ) -> dict:
        """Propose editing an existing RSA through AdService (API v25 path)."""
        if headlines is not None:
            if not (3 <= len(headlines) <= 15):
                raise ValueError("Provide between 3 and 15 headlines.")
            if any(len(h) > 30 for h in headlines):
                raise ValueError("Each headline must be 30 characters or fewer.")
        if descriptions is not None:
            if not (2 <= len(descriptions) <= 4):
                raise ValueError("Provide between 2 and 4 descriptions.")
            if any(len(d) > 90 for d in descriptions):
                raise ValueError("Each description must be 90 characters or fewer.")
        if final_urls is not None and not final_urls:
            raise ValueError("final_urls cannot be an empty list when supplied.")
        if path1 is not None and len(path1) > 15:
            raise ValueError("path1 must be 15 characters or fewer.")
        if path2 is not None and len(path2) > 15:
            raise ValueError("path2 must be 15 characters or fewer.")
        if not any(
            value is not None
            for value in (headlines, descriptions, final_urls, path1, path2)
        ):
            raise ValueError(
                "Provide at least one of headlines, descriptions, final_urls, path1, path2."
            )

        client = ctx.client.raw
        operation = client.get_type("AdOperation")
        operation.update.resource_name = client.get_service("AdService").ad_path(
            customer_id.replace("-", ""), ad_id
        )
        update_paths: list[str] = []
        rsa = operation.update.responsive_search_ad

        if headlines is not None:
            for text in headlines:
                rsa.headlines.append(_text_asset(client, text))
            update_paths.append("responsive_search_ad.headlines")
        if descriptions is not None:
            for text in descriptions:
                rsa.descriptions.append(_text_asset(client, text))
            update_paths.append("responsive_search_ad.descriptions")
        if path1 is not None:
            rsa.path1 = path1
            update_paths.append("responsive_search_ad.path1")
        if path2 is not None:
            rsa.path2 = path2
            update_paths.append("responsive_search_ad.path2")
        if final_urls is not None:
            operation.update.final_urls.extend(final_urls)
            update_paths.append("final_urls")

        operation.update_mask.CopyFrom(field_mask_pb2.FieldMask(paths=update_paths))
        changed = ", ".join(
            name
            for name, value in (
                ("headlines", headlines),
                ("descriptions", descriptions),
                ("final_urls", final_urls),
                ("path1", path1),
                ("path2", path2),
            )
            if value is not None
        )
        description = f"Update RSA {ad_id} (ad group {ad_group_id}): {changed}"

        def execute():
            return ctx.client.mutate("AdService", customer_id, [operation])

        return ctx.safety.propose(
            tool_name="update_responsive_search_ad",
            customer_id=customer_id,
            description=description,
            payload={
                "ad_group_id": ad_group_id,
                "ad_id": ad_id,
                "headlines": headlines,
                "descriptions": descriptions,
                "final_urls": final_urls,
                "path1": path1,
                "path2": path2,
            },
            execute=execute,
        )

    @mcp.tool()
    def get_ad_strength(
        customer_id: str,
        ad_group_id: str | None = None,
        campaign_id: str | None = None,
    ) -> dict:
        """List Responsive Search Ads with Ad Strength and policy status."""
        where_parts = ["ad_group_ad.ad.type = RESPONSIVE_SEARCH_AD"]
        if ad_group_id:
            where_parts.append(f"ad_group.id = {int(ad_group_id)}")
        if campaign_id:
            where_parts.append(f"campaign.id = {int(campaign_id)}")
        query = f"""
            SELECT
                campaign.name, ad_group.name, ad_group_ad.ad.id,
                ad_group_ad.ad_strength, ad_group_ad.status,
                ad_group_ad.policy_summary.approval_status
            FROM ad_group_ad
            WHERE {" AND ".join(where_parts)}
            ORDER BY ad_group_ad.ad_strength
        """
        rows = ctx.client.search(customer_id, query)
        return {"ads": rows, "count": len(rows)}

    @mcp.tool()
    def create_call_ad(
        customer_id: str,
        ad_group_id: str,
        country_code: str,
        phone_number: str,
        business_name: str,
        headlines: list[str],
        descriptions: list[str],
        final_urls: list[str] | None = None,
        call_tracking_enabled: bool = True,
    ) -> dict:
        """Create the supported v25 replacement for a removed Call Ad.

        Google removed CallAd. This compatibility tool now creates a PAUSED
        Responsive Search Ad plus a Call Asset linked to the same ad group in
        one atomic mutation. Existing callers can keep the old tool name.
        """
        if final_urls is None:
            raise ValueError(
                "Call Ads were removed. Their v25 replacement is RSA + Call Asset, "
                "which requires at least one final URL."
            )
        _validate_rsa(headlines, descriptions, final_urls, None, None)
        if len(country_code) != 2:
            raise ValueError("country_code must be a two-letter country code.")
        if not phone_number.strip():
            raise ValueError("phone_number is required.")

        client = ctx.client.raw
        customer_id_clean = customer_id.replace("-", "")
        ad_group_resource_name = client.get_service("AdGroupService").ad_group_path(
            customer_id_clean, ad_group_id
        )
        temp_asset_name = client.get_service("AssetService").asset_path(
            customer_id_clean, -1
        )

        asset_operation = client.get_type("AssetOperation")
        call_asset = asset_operation.create
        call_asset.resource_name = temp_asset_name
        call_asset.call_asset.country_code = country_code.upper()
        call_asset.call_asset.phone_number = phone_number
        reporting_state = (
            "USE_ACCOUNT_LEVEL_CALL_CONVERSION_ACTION"
            if call_tracking_enabled
            else "DISABLED"
        )
        call_asset.call_asset.call_conversion_reporting_state = (
            client.enums.CallConversionReportingStateEnum[reporting_state].value
        )

        ad_operation = client.get_type("AdGroupAdOperation")
        ad_group_ad = ad_operation.create
        ad_group_ad.ad_group = ad_group_resource_name
        ad_group_ad.status = client.enums.AdGroupAdStatusEnum.PAUSED
        _populate_rsa(
            client,
            ad_group_ad.ad,
            headlines=headlines,
            descriptions=descriptions,
            final_urls=final_urls,
            path1=None,
            path2=None,
        )

        link_operation = client.get_type("AdGroupAssetOperation")
        link = link_operation.create
        link.ad_group = ad_group_resource_name
        link.asset = temp_asset_name
        link.field_type = client.enums.AssetFieldTypeEnum.CALL.value

        operations = [
            _wrap_mutate(client, "asset_operation", asset_operation),
            _wrap_mutate(client, "ad_group_ad_operation", ad_operation),
            _wrap_mutate(client, "ad_group_asset_operation", link_operation),
        ]
        description = (
            f"Replace legacy Call Ad with PAUSED RSA + Call Asset in ad group "
            f"{ad_group_id} ({phone_number}); atomic v25 mutation"
        )

        def execute():
            return ctx.client.mutate_atomic(customer_id, operations)

        return ctx.safety.propose(
            tool_name="create_call_ad",
            customer_id=customer_id,
            description=description,
            payload={
                "compatibility_mode": "RSA_PLUS_CALL_ASSET",
                "ad_group_id": ad_group_id,
                "country_code": country_code,
                "phone_number": phone_number,
                "business_name": business_name,
                "headlines": headlines,
                "descriptions": descriptions,
                "final_urls": final_urls,
                "call_tracking_enabled": call_tracking_enabled,
            },
            execute=execute,
        )

    @mcp.tool()
    def create_demand_gen_campaign(
        customer_id: str,
        name: str,
        campaign_budget_resource_name: str,
        target_cpa: float | None = None,
        contains_eu_political_advertising: str = DEFAULT_EU_POLITICAL_ADVERTISING,
    ) -> dict:
        """Propose creating a Demand Gen campaign shell. Created PAUSED."""
        client = ctx.client.raw
        operation = client.get_type("CampaignOperation")
        campaign = operation.create
        campaign.name = name
        campaign.campaign_budget = campaign_budget_resource_name
        campaign.advertising_channel_type = (
            client.enums.AdvertisingChannelTypeEnum.DEMAND_GEN
        )
        campaign.status = client.enums.CampaignStatusEnum.PAUSED
        apply_required_campaign_fields(
            client,
            campaign,
            contains_eu_political_advertising=contains_eu_political_advertising,
        )
        if target_cpa is not None:
            from ..client import micros

            campaign.target_cpa.target_cpa_micros = micros(target_cpa)
        else:
            campaign.maximize_conversions.SetInParent()

        description = (
            f"Create Demand Gen campaign '{name}', created PAUSED "
            "(add an ad group + Demand Gen ad before enabling)"
        )

        def execute():
            return ctx.client.mutate("CampaignService", customer_id, [operation])

        return ctx.safety.propose(
            tool_name="create_demand_gen_campaign",
            customer_id=customer_id,
            description=description,
            payload={
                "name": name,
                "target_cpa": target_cpa,
                "contains_eu_political_advertising": contains_eu_political_advertising,
            },
            execute=execute,
        )

    @mcp.tool()
    def create_demand_gen_ad(
        customer_id: str,
        ad_group_id: str,
        headlines: list[str],
        descriptions: list[str],
        business_name: str,
        final_urls: list[str],
        marketing_image_urls: list[str] | None = None,
        logo_image_urls: list[str] | None = None,
        call_to_action_text: str | None = None,
    ) -> dict:
        """Propose creating a Demand Gen multi-asset ad atomically."""
        if not (1 <= len(headlines) <= 5):
            raise ValueError("Provide between 1 and 5 headlines.")
        if any(len(h) > 30 for h in headlines):
            raise ValueError("Each Demand Gen headline must be 30 characters or fewer.")
        if not (1 <= len(descriptions) <= 5):
            raise ValueError("Provide between 1 and 5 descriptions.")
        if any(len(d) > 90 for d in descriptions):
            raise ValueError("Each description must be 90 characters or fewer.")
        if not business_name or len(business_name) > 25:
            raise ValueError("business_name is required and must be 25 characters or fewer.")
        if not final_urls:
            raise ValueError("Provide at least one final URL.")
        if not marketing_image_urls:
            raise ValueError(
                "Provide at least one marketing image for this Demand Gen multi-asset ad."
            )
        if not logo_image_urls:
            raise ValueError("Demand Gen multi-asset ads require at least one logo image.")

        client = ctx.client.raw
        customer_id_clean = customer_id.replace("-", "")
        ad_group_resource_name = client.get_service("AdGroupService").ad_group_path(
            customer_id_clean, ad_group_id
        )
        description_text = (
            f"Create Demand Gen ad in ad group {ad_group_id} "
            f"({len(headlines)} headlines, {len(marketing_image_urls)} images), "
            "created PAUSED"
        )

        def execute():
            operations = []
            next_temp_id = -1
            marketing_refs, image_ops, next_temp_id = _build_image_asset_operations(
                client,
                customer_id_clean,
                marketing_image_urls,
                next_temp_id,
            )
            operations.extend(image_ops)
            logo_refs, logo_ops, next_temp_id = _build_image_asset_operations(
                client,
                customer_id_clean,
                logo_image_urls,
                next_temp_id,
            )
            operations.extend(logo_ops)

            ad_operation = client.get_type("AdGroupAdOperation")
            ad_group_ad = ad_operation.create
            ad_group_ad.ad_group = ad_group_resource_name
            ad_group_ad.status = client.enums.AdGroupAdStatusEnum.PAUSED
            dg_ad = ad_group_ad.ad.demand_gen_multi_asset_ad
            for text in headlines:
                dg_ad.headlines.append(_text_asset(client, text))
            for text in descriptions:
                dg_ad.descriptions.append(_text_asset(client, text))
            dg_ad.business_name = business_name
            for resource_name in marketing_refs:
                dg_ad.marketing_images.append(_image_ref(client, resource_name))
            for resource_name in logo_refs:
                dg_ad.logo_images.append(_image_ref(client, resource_name))
            if call_to_action_text:
                dg_ad.call_to_action_text = call_to_action_text
            ad_group_ad.ad.final_urls.extend(final_urls)
            operations.append(_wrap_mutate(client, "ad_group_ad_operation", ad_operation))
            return ctx.client.mutate_atomic(customer_id, operations)

        return ctx.safety.propose(
            tool_name="create_demand_gen_ad",
            customer_id=customer_id,
            description=description_text,
            payload={
                "ad_group_id": ad_group_id,
                "headlines": headlines,
                "descriptions": descriptions,
                "business_name": business_name,
                "final_urls": final_urls,
                "marketing_image_urls": marketing_image_urls,
                "logo_image_urls": logo_image_urls,
                "call_to_action_text": call_to_action_text,
            },
            execute=execute,
        )

    @mcp.tool()
    def update_ad_status(
        customer_id: str,
        ad_group_id: str,
        ad_id: str,
        status: str,
    ) -> dict:
        """Propose pausing, enabling, or removing an ad."""
        if status not in {"ENABLED", "PAUSED", "REMOVED"}:
            raise ValueError("status must be ENABLED, PAUSED, or REMOVED.")
        client = ctx.client.raw
        operation = client.get_type("AdGroupAdOperation")
        operation.update.resource_name = client.get_service(
            "AdGroupAdService"
        ).ad_group_ad_path(customer_id.replace("-", ""), ad_group_id, ad_id)
        operation.update.status = client.enums.AdGroupAdStatusEnum[status].value
        operation.update_mask.CopyFrom(field_mask_pb2.FieldMask(paths=["status"]))
        description = f"Set ad {ad_id} (ad group {ad_group_id}) status -> {status}"

        def execute():
            return ctx.client.mutate("AdGroupAdService", customer_id, [operation])

        return ctx.safety.propose(
            tool_name="update_ad_status",
            customer_id=customer_id,
            description=description,
            payload={"ad_group_id": ad_group_id, "ad_id": ad_id, "status": status},
            execute=execute,
        )

    @mcp.tool()
    def remove_ad(customer_id: str, ad_group_id: str, ad_id: str) -> dict:
        """Propose permanently removing an ad."""
        client = ctx.client.raw
        operation = client.get_type("AdGroupAdOperation")
        operation.remove = client.get_service("AdGroupAdService").ad_group_ad_path(
            customer_id.replace("-", ""), ad_group_id, ad_id
        )
        description = f"REMOVE ad {ad_id} from ad group {ad_group_id} (irreversible)"

        def execute():
            return ctx.client.mutate("AdGroupAdService", customer_id, [operation])

        return ctx.safety.propose(
            tool_name="remove_ad",
            customer_id=customer_id,
            description=description,
            payload={"ad_group_id": ad_group_id, "ad_id": ad_id},
            execute=execute,
        )


def _validate_rsa(
    headlines: list[str],
    descriptions: list[str],
    final_urls: list[str],
    path1: str | None,
    path2: str | None,
) -> None:
    if not (3 <= len(headlines) <= 15):
        raise ValueError("Provide between 3 and 15 headlines.")
    if any(len(h) > 30 for h in headlines):
        raise ValueError("Each headline must be 30 characters or fewer.")
    if not (2 <= len(descriptions) <= 4):
        raise ValueError("Provide between 2 and 4 descriptions.")
    if any(len(d) > 90 for d in descriptions):
        raise ValueError("Each description must be 90 characters or fewer.")
    if not final_urls:
        raise ValueError("Provide at least one final URL.")
    if path1 is not None and len(path1) > 15:
        raise ValueError("path1 must be 15 characters or fewer.")
    if path2 is not None and len(path2) > 15:
        raise ValueError("path2 must be 15 characters or fewer.")


def _populate_rsa(
    client,
    ad,
    *,
    headlines: list[str],
    descriptions: list[str],
    final_urls: list[str],
    path1: str | None,
    path2: str | None,
) -> None:
    rsa = ad.responsive_search_ad
    for text in headlines:
        rsa.headlines.append(_text_asset(client, text))
    for text in descriptions:
        rsa.descriptions.append(_text_asset(client, text))
    if path1:
        rsa.path1 = path1
    if path2:
        rsa.path2 = path2
    ad.final_urls.extend(final_urls)


def _text_asset(client, text: str):
    asset = client.get_type("AdTextAsset")
    asset.text = text
    return asset


def _image_ref(client, resource_name: str):
    asset = client.get_type("AdImageAsset")
    asset.asset = resource_name
    return asset


def _wrap_mutate(client, field_name: str, operation):
    mutate_operation = client.get_type("MutateOperation")
    client.copy_from(getattr(mutate_operation, field_name), operation)
    return mutate_operation


def _build_image_asset_operations(
    client,
    customer_id_clean: str,
    urls: list[str],
    next_temp_id: int,
):
    resource_names: list[str] = []
    mutate_operations = []
    for url in urls:
        image_bytes = fetch_public_https_image(url)
        resource_name = client.get_service("AssetService").asset_path(
            customer_id_clean, next_temp_id
        )
        next_temp_id -= 1
        operation = client.get_type("AssetOperation")
        operation.create.resource_name = resource_name
        operation.create.image_asset.data = image_bytes
        mutate_operations.append(_wrap_mutate(client, "asset_operation", operation))
        resource_names.append(resource_name)
    return resource_names, mutate_operations, next_temp_id
