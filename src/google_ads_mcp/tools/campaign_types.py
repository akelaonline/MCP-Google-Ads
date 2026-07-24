"""Specialized campaign-type creators: Shopping and Local.

Neither of these is a drop-in variant of create_campaign (campaigns.py) —
each requires its own advertising_channel_type/sub_type and, for Shopping,
an external prerequisite this MCP does not manage.
"""

from __future__ import annotations

from ..context import AppContext


def register(mcp, ctx: AppContext) -> None:
    @mcp.tool()
    def create_shopping_campaign(
        customer_id: str,
        name: str,
        campaign_budget_resource_name: str,
        merchant_center_id: str,
        sales_country: str = "AR",
        campaign_type: str = "STANDARD_SHOPPING",
        target_roas: float | None = None,
    ) -> dict:
        """Propose creating a Shopping campaign. Created PAUSED.

        PREREQUISITE this tool does NOT set up: a product feed already live
        in Google Merchant Center, linked to this Google Ads account. Product
        feed management (uploading products, categories, pricing) happens in
        Merchant Center / the Content API for Shopping — a different API this
        MCP does not wrap. If merchant_center_id isn't already linked in the
        Google Ads UI (Tools > Linked accounts), this call will fail even
        though the campaign shell itself is valid.

        Args:
            merchant_center_id: The linked Merchant Center account ID.
            sales_country: ISO 3166-1 alpha-2 country the products ship to.
            campaign_type: STANDARD_SHOPPING or SMART_SHOPPING (SMART_SHOPPING
                is deprecated by Google in favor of Performance Max — prefer
                create_performance_max_campaign for new smart-shopping-style
                campaigns unless you specifically need legacy Smart Shopping).
            target_roas: Optional, e.g. 4.0 for 400%. If omitted, uses
                Maximize Clicks (manual-ish default for Standard Shopping).
        """
        client = ctx.client.raw
        operation = client.get_type("CampaignOperation")
        campaign = operation.create
        campaign.name = name
        campaign.campaign_budget = campaign_budget_resource_name
        campaign.advertising_channel_type = client.enums.AdvertisingChannelTypeEnum.SHOPPING
        campaign.advertising_channel_sub_type = client.enums.AdvertisingChannelSubTypeEnum[
            campaign_type
        ].value
        campaign.status = client.enums.CampaignStatusEnum.PAUSED
        campaign.shopping_setting.merchant_id = int(merchant_center_id)
        campaign.shopping_setting.sales_country = sales_country
        campaign.shopping_setting.feed_label = sales_country

        if target_roas is not None:
            campaign.target_roas.target_roas = target_roas
        else:
            campaign.manual_cpc.SetInParent()

        description = (
            f"Create Shopping campaign '{name}' ({campaign_type}, Merchant Center "
            f"{merchant_center_id}), created PAUSED — requires the product feed to "
            f"already be live and linked"
        )

        def execute():
            return ctx.client.mutate("CampaignService", customer_id, [operation])

        return ctx.safety.propose(
            tool_name="create_shopping_campaign",
            customer_id=customer_id,
            description=description,
            payload={
                "name": name,
                "merchant_center_id": merchant_center_id,
                "sales_country": sales_country,
                "campaign_type": campaign_type,
                "target_roas": target_roas,
            },
            execute=execute,
        )

    @mcp.tool()
    def create_local_campaign(
        customer_id: str,
        name: str,
        campaign_budget_resource_name: str,
        business_name: str,
        headlines: list[str],
        descriptions: list[str],
        final_url: str,
        target_cpa: float | None = None,
    ) -> dict:
        """Propose creating a Local campaign (drives visits to a physical
        location across Search, Display, Maps, and YouTube). Created PAUSED.

        Requires a Google Business Profile linked to the account for the
        location targeting to actually resolve to a place — this tool
        creates the campaign shell and its ad assets, not the Business
        Profile link itself (set up separately in the Google Ads UI under
        Locations, or already inherited from a linked Business Profile account).

        Args:
            headlines: 1-5 strings, each <=30 characters.
            descriptions: 1-5 strings, each <=90 characters.
        """
        if not (1 <= len(headlines) <= 5):
            raise ValueError("Provide between 1 and 5 headlines.")
        if any(len(h) > 30 for h in headlines):
            raise ValueError("Each headline must be 30 characters or fewer.")
        if not (1 <= len(descriptions) <= 5):
            raise ValueError("Provide between 1 and 5 descriptions.")
        if any(len(d) > 90 for d in descriptions):
            raise ValueError("Each description must be 90 characters or fewer.")

        client = ctx.client.raw
        operation = client.get_type("CampaignOperation")
        campaign = operation.create
        campaign.name = name
        campaign.campaign_budget = campaign_budget_resource_name
        campaign.advertising_channel_type = client.enums.AdvertisingChannelTypeEnum.LOCAL
        campaign.status = client.enums.CampaignStatusEnum.PAUSED

        if target_cpa is not None:
            from ..client import micros

            campaign.target_cpa.target_cpa_micros = micros(target_cpa)
        else:
            campaign.maximize_conversions.SetInParent()

        description = (
            f"Create Local campaign '{name}' for '{business_name}', created PAUSED — "
            f"requires a linked Google Business Profile for location targeting to resolve"
        )

        def execute():
            campaign_result = ctx.client.mutate("CampaignService", customer_id, [operation])
            campaign_resource_name = campaign_result.results[0].resource_name

            asset_operation = client.get_type("AssetOperation")
            asset = asset_operation.create
            asset.local_ad.business_name = business_name
            for text in headlines:
                asset.local_ad.headlines.append(_ad_text_asset(client, text))
            for text in descriptions:
                asset.local_ad.descriptions.append(_ad_text_asset(client, text))
            asset.local_ad.final_urls.append(final_url)

            # Note: as of API v20, Local campaign creative is asset-group-like
            # but simpler — attaching via CampaignAsset with field_type LOCAL
            # is the supported path for the core text assets.
            asset_result = ctx.client.mutate("AssetService", customer_id, [asset_operation])
            asset_resource_name = asset_result.results[0].resource_name

            campaign_asset_operation = client.get_type("CampaignAssetOperation")
            campaign_asset = campaign_asset_operation.create
            campaign_asset.campaign = campaign_resource_name
            campaign_asset.asset = asset_resource_name
            campaign_asset.field_type = client.enums.AssetFieldTypeEnum.LOCAL

            link_result = ctx.client.mutate(
                "CampaignAssetService", customer_id, [campaign_asset_operation]
            )

            return {
                "campaign_resource_name": campaign_resource_name,
                "asset_resource_name": asset_resource_name,
                "campaign_asset_resource_name": link_result.results[0].resource_name,
            }

        return ctx.safety.propose(
            tool_name="create_local_campaign",
            customer_id=customer_id,
            description=description,
            payload={
                "name": name,
                "business_name": business_name,
                "headlines": headlines,
                "descriptions": descriptions,
                "final_url": final_url,
                "target_cpa": target_cpa,
            },
            execute=execute,
        )


def _ad_text_asset(client, text: str):
    asset = client.get_type("AdTextAsset")
    asset.text = text
    return asset
