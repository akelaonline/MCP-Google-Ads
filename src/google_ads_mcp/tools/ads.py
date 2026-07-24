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
                    with urllib.request.urlopen(url, timeout=30) as response:  # noqa: S310
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
            raise ValueError("headline must be 15 characters or fewer (YouTube CTA limit).")

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
    def update_ad_status(customer_id: str, ad_group_id: str, ad_id: str, status: str) -> dict:
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
