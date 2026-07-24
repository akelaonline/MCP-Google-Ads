"""Performance Max: campaign creation and asset groups.

PMax is structurally different from Search: there are no ad groups or
keywords. A campaign holds one or more Asset Groups, each a self-contained
bundle of creative (headlines, descriptions, images, logos) plus its own
final URL, that Google's automation assembles into ads across all
Google inventory (Search, Display, YouTube, Discover, Gmail, Maps).

This module covers the create-and-launch basics. It intentionally does NOT
wrap listing group filters (product-level Shopping targeting within PMax)
or asset group signals (audience/search-theme signals) — those are common
enough to warrant their own careful design later, but a half-built version
here would be more dangerous than useful for a first PMax campaign.
"""

from __future__ import annotations

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
            ag_result = ctx.client.mutate("AssetGroupService", customer_id, [ag_operation])
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
