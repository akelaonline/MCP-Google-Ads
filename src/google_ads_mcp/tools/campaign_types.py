"""Specialized campaign-type creators.

Google migrated legacy Local and Smart Shopping campaign creation toward
Performance Max. This module keeps Standard Shopping creation and turns the
old Local creator into an explicit compatibility error instead of sending an
invalid/obsolete mutation to a live account.
"""

from __future__ import annotations

from ..campaign_compat import (
    DEFAULT_EU_POLITICAL_ADVERTISING,
    apply_required_campaign_fields,
)
from ..context import AppContext
from ..errors import GoogleAdsMcpError


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
        contains_eu_political_advertising: str = DEFAULT_EU_POLITICAL_ADVERTISING,
    ) -> dict:
        """Propose creating a Standard Shopping campaign. Created PAUSED.

        ``sales_country`` is retained as a backwards-compatible MCP parameter,
        but API v25 uses it as ``shopping_setting.feed_label``; the deprecated
        ``shopping_setting.sales_country`` field is not written.
        """
        if campaign_type != "STANDARD_SHOPPING":
            raise ValueError(
                "Only STANDARD_SHOPPING can be created here. Smart Shopping is "
                "legacy; use create_performance_max_campaign for new automated "
                "retail campaigns."
            )
        if not sales_country or len(sales_country) > 20:
            raise ValueError("sales_country/feed label must be 1-20 characters.")

        client = ctx.client.raw
        operation = client.get_type("CampaignOperation")
        campaign = operation.create
        campaign.name = name
        campaign.campaign_budget = campaign_budget_resource_name
        campaign.advertising_channel_type = (
            client.enums.AdvertisingChannelTypeEnum.SHOPPING
        )
        campaign.advertising_channel_sub_type = (
            client.enums.AdvertisingChannelSubTypeEnum.STANDARD_SHOPPING
        )
        campaign.status = client.enums.CampaignStatusEnum.PAUSED
        campaign.shopping_setting.merchant_id = int(merchant_center_id)
        campaign.shopping_setting.feed_label = sales_country.upper()
        apply_required_campaign_fields(
            client,
            campaign,
            contains_eu_political_advertising=contains_eu_political_advertising,
        )

        if target_roas is not None:
            campaign.target_roas.target_roas = target_roas
        else:
            client.copy_from(campaign.manual_cpc, client.get_type("ManualCpc"))

        description = (
            f"Create Standard Shopping campaign '{name}' (Merchant Center "
            f"{merchant_center_id}, feed label {sales_country.upper()}), created PAUSED"
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
                "feed_label": sales_country.upper(),
                "campaign_type": campaign_type,
                "target_roas": target_roas,
                "contains_eu_political_advertising": contains_eu_political_advertising,
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
        """Legacy compatibility entrypoint.

        New legacy Local campaigns are no longer the supported path. Google
        automatically migrated Local campaigns to Performance Max; create a
        Performance Max campaign and use location/business assets instead.
        This tool intentionally refuses to send a legacy mutation.
        """
        raise GoogleAdsMcpError(
            "Legacy Local campaign creation is not supported on the current "
            "Google Ads API. Use create_performance_max_campaign and attach the "
            "appropriate location/business assets. No account change was made."
        )
