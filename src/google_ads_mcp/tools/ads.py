"""Ad creative tools — Responsive Search Ads plus status management."""

from __future__ import annotations

from google.protobuf import field_mask_pb2

from ..context import AppContext


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
        """Propose creating a Responsive Search Ad.

        Args:
            headlines: 3-15 strings, each <=30 characters.
            descriptions: 2-4 strings, each <=90 characters.
            final_urls: Landing page URL(s).
            path1 / path2: Optional display-URL path segments (<=15 chars each).
        """
        if not (3 <= len(headlines) <= 15):
            raise ValueError("Provide between 3 and 15 headlines.")
        if not (2 <= len(descriptions) <= 4):
            raise ValueError("Provide between 2 and 4 descriptions.")
        if any(len(h) > 30 for h in headlines):
            raise ValueError("Each headline must be 30 characters or fewer.")
        if any(len(d) > 90 for d in descriptions):
            raise ValueError("Each description must be 90 characters or fewer.")

        client = ctx.client.raw
        operation = client.get_type("AdGroupAdOperation")
        ad_group_ad = operation.create
        ad_group_ad.ad_group = client.get_service("AdGroupService").ad_group_path(
            customer_id.replace("-", ""), ad_group_id
        )
        ad_group_ad.status = client.enums.AdGroupAdStatusEnum.PAUSED

        rsa = ad_group_ad.ad.responsive_search_ad
        for text in headlines:
            asset = client.get_type("AdTextAsset")
            asset.text = text
            rsa.headlines.append(asset)
        for text in descriptions:
            asset = client.get_type("AdTextAsset")
            asset.text = text
            rsa.descriptions.append(asset)
        if path1:
            rsa.path1 = path1
        if path2:
            rsa.path2 = path2
        ad_group_ad.ad.final_urls.extend(final_urls)

        description = (
            f"Create Responsive Search Ad in ad group {ad_group_id} "
            f"({len(headlines)} headlines, {len(descriptions)} descriptions), created PAUSED"
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
    ) -> dict:
        """Propose creating a Responsive Display Ad. Created PAUSED.

        Args:
            headlines: 1-5 strings, each <=30 characters.
            long_headline: 1 string, <=90 characters.
            descriptions: 1-5 strings, each <=90 characters.
            marketing_image_urls / logo_image_urls: Optional public HTTPS URLs;
                each is downloaded and uploaded as an image asset at confirm
                time. Google requires at least one marketing image in
                practice — omitting both leaves the ad relying on
                automatically generated images where policy allows, which is
                not guaranteed to pass review.
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

        client = ctx.client.raw

        description_text = (
            f"Create Responsive Display Ad in ad group {ad_group_id} "
            f"({len(headlines)} headlines, {len(marketing_image_urls or [])} marketing "
            f"images), created PAUSED"
        )

        def execute():
            import urllib.request

            def _upload_images(urls, field):
                resource_names = []
                for url in urls or []:
                    with urllib.request.urlopen(url, timeout=30) as response:
                        image_bytes = response.read()
                    op = client.get_type("AssetOperation")
                    op.create.image_asset.data = image_bytes
                    result = ctx.client.mutate("AssetService", customer_id, [op])
                    resource_names.append(result.results[0].resource_name)
                return resource_names

            marketing_images = _upload_images(marketing_image_urls, "marketing")
            logo_images = _upload_images(logo_image_urls, "logo")

            operation = client.get_type("AdGroupAdOperation")
            ad_group_ad = operation.create
            ad_group_ad.ad_group = client.get_service("AdGroupService").ad_group_path(
                customer_id.replace("-", ""), ad_group_id
            )
            ad_group_ad.status = client.enums.AdGroupAdStatusEnum.PAUSED

            rda = ad_group_ad.ad.responsive_display_ad
            for text in headlines:
                asset = client.get_type("AdTextAsset")
                asset.text = text
                rda.headlines.append(asset)
            rda.long_headline.text = long_headline
            for text in descriptions:
                asset = client.get_type("AdTextAsset")
                asset.text = text
                rda.descriptions.append(asset)
            rda.business_name = business_name
            for resource_name in marketing_images:
                asset = client.get_type("AdImageAsset")
                asset.asset = resource_name
                rda.marketing_images.append(asset)
            for resource_name in logo_images:
                asset = client.get_type("AdImageAsset")
                asset.asset = resource_name
                rda.logo_images.append(asset)
            ad_group_ad.ad.final_urls.extend(final_urls)

            return ctx.client.mutate("AdGroupAdService", customer_id, [operation])

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
        """Propose creating an in-stream YouTube video ad. Created PAUSED.

        Requires the video to already be uploaded and public/unlisted on
        YouTube — this tool does not upload video files, only references an
        existing video by ID.

        Args:
            youtube_video_id: The 11-character ID from the YouTube URL
                (e.g. "dQw4w9WgXcQ" from youtube.com/watch?v=dQw4w9WgXcQ).
            headline: <=15 characters (YouTube's in-stream CTA headline limit).
            companion_banner_asset_resource_name: Optional pre-uploaded image
                asset resource name for the companion banner.
        """
        if len(headline) > 15:
            raise ValueError(
                "headline must be 15 characters or fewer (YouTube CTA limit)."
            )

        client = ctx.client.raw
        operation = client.get_type("AdGroupAdOperation")
        ad_group_ad = operation.create
        ad_group_ad.ad_group = client.get_service("AdGroupService").ad_group_path(
            customer_id.replace("-", ""), ad_group_id
        )
        ad_group_ad.status = client.enums.AdGroupAdStatusEnum.PAUSED

        video_ad = ad_group_ad.ad.video_ad
        video_ad.video.video_id = youtube_video_id
        in_stream = video_ad.in_stream
        in_stream.action_button_label = headline
        if final_urls:
            in_stream.action_headline = headline
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
        """Propose replacing the headlines/descriptions/final_urls of an
        EXISTING Responsive Search Ad, in place — no need to remove and
        recreate the ad (which loses its accumulated Ad Strength history
        and serving data).

        Only the fields you pass are changed; omit a field to leave it as-is.
        Note this REPLACES the full headlines/descriptions list, it does not
        append to it — pass the complete new list for whichever field you're
        changing.

        Args:
            headlines: If provided, 3-15 strings, each <=30 characters.
            descriptions: If provided, 2-4 strings, each <=90 characters.
            final_urls: If provided, replaces the landing page URL(s).
            path1 / path2: Optional display-URL path segments (<=15 chars each).
        """
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
        if path1 is not None and len(path1) > 15:
            raise ValueError("path1 must be 15 characters or fewer.")
        if path2 is not None and len(path2) > 15:
            raise ValueError("path2 must be 15 characters or fewer.")
        if not any(
            v is not None
            for v in (headlines, descriptions, final_urls, path1, path2)
        ):
            raise ValueError(
                "Provide at least one of headlines, descriptions, final_urls, "
                "path1, path2 to update."
            )

        client = ctx.client.raw
        operation = client.get_type("AdGroupAdOperation")
        resource_name = client.get_service("AdGroupAdService").ad_group_ad_path(
            customer_id.replace("-", ""), ad_group_id, ad_id
        )
        operation.update.resource_name = resource_name

        update_paths: list[str] = []
        rsa = operation.update.ad.responsive_search_ad
        if headlines is not None:
            for text in headlines:
                asset = client.get_type("AdTextAsset")
                asset.text = text
                rsa.headlines.append(asset)
            update_paths.append("ad.responsive_search_ad.headlines")
        if descriptions is not None:
            for text in descriptions:
                asset = client.get_type("AdTextAsset")
                asset.text = text
                rsa.descriptions.append(asset)
            update_paths.append("ad.responsive_search_ad.descriptions")
        if path1 is not None:
            rsa.path1 = path1
            update_paths.append("ad.responsive_search_ad.path1")
        if path2 is not None:
            rsa.path2 = path2
            update_paths.append("ad.responsive_search_ad.path2")
        if final_urls is not None:
            operation.update.ad.final_urls.extend(final_urls)
            update_paths.append("ad.final_urls")

        operation.update_mask.CopyFrom(field_mask_pb2.FieldMask(paths=update_paths))

        changed = ", ".join(
            name
            for name, val in [
                ("headlines", headlines),
                ("descriptions", descriptions),
                ("final_urls", final_urls),
                ("path1", path1),
                ("path2", path2),
            ]
            if val is not None
        )
        description = f"Update RSA {ad_id} (ad group {ad_group_id}): {changed}"

        def execute():
            return ctx.client.mutate("AdGroupAdService", customer_id, [operation])

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
        customer_id: str, ad_group_id: str | None = None, campaign_id: str | None = None
    ) -> dict:
        """List Responsive Search Ads with their Ad Strength rating
        (PENDING, NO_ADS, POOR, AVERAGE, GOOD, EXCELLENT) plus any policy
        summary — the fastest way to find ads that need better headline/
        description variety without opening the UI.
        """
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
        """Propose creating a Call Ad — an ad type with no link at all, just
        a phone number and a "Call" button, shown only on devices that can
        place calls. High-intent format for services/B2B where a phone
        conversation is the actual conversion (medical, legal, trades,
        anything where the lead prefers to talk before committing). Created
        PAUSED.

        Args:
            country_code: 2-letter ISO code for the phone number, e.g. "AR".
            headlines: 2-15 strings, each <=30 characters.
            descriptions: 2-4 strings, each <=90 characters.
            call_tracking_enabled: If True (default), Google provides a
                forwarding number so call metrics attribute back to this ad.
        """
        if not (2 <= len(headlines) <= 15):
            raise ValueError("Provide between 2 and 15 headlines.")
        if any(len(h) > 30 for h in headlines):
            raise ValueError("Each headline must be 30 characters or fewer.")
        if not (2 <= len(descriptions) <= 4):
            raise ValueError("Provide between 2 and 4 descriptions.")
        if any(len(d) > 90 for d in descriptions):
            raise ValueError("Each description must be 90 characters or fewer.")

        client = ctx.client.raw
        operation = client.get_type("AdGroupAdOperation")
        ad_group_ad = operation.create
        ad_group_ad.ad_group = client.get_service("AdGroupService").ad_group_path(
            customer_id.replace("-", ""), ad_group_id
        )
        ad_group_ad.status = client.enums.AdGroupAdStatusEnum.PAUSED

        call_ad = ad_group_ad.ad.call_ad
        call_ad.country_code = country_code
        call_ad.phone_number = phone_number
        call_ad.business_name = business_name
        for text in headlines:
            call_ad.headlines.append(_call_ad_text_asset(client, text))
        for text in descriptions:
            call_ad.descriptions.append(_call_ad_text_asset(client, text))
        if final_urls:
            call_ad.final_urls.extend(final_urls)
        call_ad.call_tracking_enabled = call_tracking_enabled

        description = (
            f"Create Call Ad in ad group {ad_group_id} ({phone_number}), created PAUSED"
        )

        def execute():
            return ctx.client.mutate("AdGroupAdService", customer_id, [operation])

        return ctx.safety.propose(
            tool_name="create_call_ad",
            customer_id=customer_id,
            description=description,
            payload={
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
    ) -> dict:
        """Propose creating a Demand Gen campaign shell (formerly Discovery
        Ads) — runs on Discover feed, Gmail, and YouTube in-feed/Shorts.
        Distinct from Performance Max: Demand Gen is creative-led (you pick
        the images/video) rather than fully automated across all inventory,
        so it's a good fit when brand control over the visual matters more
        than Google's full automation. Created PAUSED — add an ad group
        and a Demand Gen ad afterward.

        Args:
            target_cpa: Optional Target CPA. If omitted, uses Maximize
                Conversions with no target.
        """
        client = ctx.client.raw
        operation = client.get_type("CampaignOperation")
        campaign = operation.create
        campaign.name = name
        campaign.campaign_budget = campaign_budget_resource_name
        campaign.advertising_channel_type = (
            client.enums.AdvertisingChannelTypeEnum.DEMAND_GEN
        )
        campaign.status = client.enums.CampaignStatusEnum.PAUSED

        if target_cpa is not None:
            from ..client import micros

            campaign.target_cpa.target_cpa_micros = micros(target_cpa)
        else:
            campaign.maximize_conversions.SetInParent()

        description = (
            f"Create Demand Gen campaign '{name}', created PAUSED "
            f"(add an ad group + Demand Gen ad before enabling)"
        )

        def execute():
            return ctx.client.mutate("CampaignService", customer_id, [operation])

        return ctx.safety.propose(
            tool_name="create_demand_gen_campaign",
            customer_id=customer_id,
            description=description,
            payload={"name": name, "target_cpa": target_cpa},
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
        """Propose creating a Demand Gen multi-asset ad — the standard ad
        type for a Demand Gen campaign, single image/carousel-eligible
        creative shown across Discover/Gmail/YouTube. Created PAUSED.

        Args:
            headlines: 1-5 strings, each <=40 characters.
            descriptions: 1-5 strings, each <=90 characters.
            marketing_image_urls: Public HTTPS URLs; downloaded and uploaded
                at confirm time. At least one recommended — Demand Gen relies
                entirely on supplied creative (no automated image generation).
            call_to_action_text: e.g. "LEARN_MORE", "SHOP_NOW", "SIGN_UP" —
                pass the enum name as a string.
        """
        if not (1 <= len(headlines) <= 5):
            raise ValueError("Provide between 1 and 5 headlines.")
        if any(len(h) > 40 for h in headlines):
            raise ValueError("Each headline must be 40 characters or fewer.")
        if not (1 <= len(descriptions) <= 5):
            raise ValueError("Provide between 1 and 5 descriptions.")
        if any(len(d) > 90 for d in descriptions):
            raise ValueError("Each description must be 90 characters or fewer.")

        client = ctx.client.raw

        description_text = (
            f"Create Demand Gen ad in ad group {ad_group_id} "
            f"({len(headlines)} headlines, {len(marketing_image_urls or [])} images), "
            f"created PAUSED"
        )

        def execute():
            import urllib.request

            def _upload_images(urls):
                resource_names = []
                for url in urls or []:
                    with urllib.request.urlopen(url, timeout=30) as response:
                        image_bytes = response.read()
                    op = client.get_type("AssetOperation")
                    op.create.image_asset.data = image_bytes
                    result = ctx.client.mutate("AssetService", customer_id, [op])
                    resource_names.append(result.results[0].resource_name)
                return resource_names

            marketing_images = _upload_images(marketing_image_urls)
            logo_images = _upload_images(logo_image_urls)

            operation = client.get_type("AdGroupAdOperation")
            ad_group_ad = operation.create
            ad_group_ad.ad_group = client.get_service("AdGroupService").ad_group_path(
                customer_id.replace("-", ""), ad_group_id
            )
            ad_group_ad.status = client.enums.AdGroupAdStatusEnum.PAUSED

            dg_ad = ad_group_ad.ad.demand_gen_multi_asset_ad
            for text in headlines:
                dg_ad.headlines.append(_call_ad_text_asset(client, text))
            for text in descriptions:
                dg_ad.descriptions.append(_call_ad_text_asset(client, text))
            dg_ad.business_name = business_name
            for resource_name in marketing_images:
                asset = client.get_type("AdImageAsset")
                asset.asset = resource_name
                dg_ad.marketing_images.append(asset)
            for resource_name in logo_images:
                asset = client.get_type("AdImageAsset")
                asset.asset = resource_name
                dg_ad.logo_images.append(asset)
            if call_to_action_text:
                dg_ad.call_to_action_text = call_to_action_text
            ad_group_ad.ad.final_urls.extend(final_urls)

            return ctx.client.mutate("AdGroupAdService", customer_id, [operation])

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
        customer_id: str, ad_group_id: str, ad_id: str, status: str
    ) -> dict:
        """Propose pausing, enabling, or removing an ad.

        Args:
            status: ENABLED, PAUSED, or REMOVED.
        """
        client = ctx.client.raw
        operation = client.get_type("AdGroupAdOperation")
        resource_name = client.get_service("AdGroupAdService").ad_group_ad_path(
            customer_id.replace("-", ""), ad_group_id, ad_id
        )
        operation.update.resource_name = resource_name
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


def _call_ad_text_asset(client, text: str):
    asset = client.get_type("AdTextAsset")
    asset.text = text
    return asset
