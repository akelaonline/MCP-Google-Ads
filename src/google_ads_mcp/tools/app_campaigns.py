"""App campaign creation for Google Ads API v25.

App campaigns (ACi/ACe) are created through the generic CampaignService with
``advertising_channel_type = MULTI_CHANNEL`` (the v25 channel for app
campaigns; ``APP`` no longer exists as a channel value), plus
``advertising_channel_sub_type`` set to ``APP_CAMPAIGN`` /
``APP_CAMPAIGN_FOR_ENGAGEMENT`` and an ``app_campaign_setting`` describing the
store listing. Bidding is expressed by pairing the v25
``bidding_strategy_goal_type`` with the matching campaign bidding strategy.
Ad groups for app campaigns carry no type in v25 (Google derives it), so
``create_ad_group`` with ``ad_group_type='AUTO'`` handles them after this
module's campaign exists.
"""

from __future__ import annotations

from ..campaign_compat import (
    DEFAULT_EU_POLITICAL_ADVERTISING,
    apply_campaign_dates,
    apply_required_campaign_fields,
)
from ..client import micros
from ..context import AppContext

_GOAL_BIDDING = {
    # goal type -> (campaign bidding strategy, requires target)
    "OPTIMIZE_INSTALLS_TARGET_INSTALL_COST": ("target_cpa", True),
    "OPTIMIZE_IN_APP_CONVERSIONS_TARGET_INSTALL_COST": ("target_cpa", True),
    "OPTIMIZE_IN_APP_CONVERSIONS_TARGET_CONVERSION_COST": ("target_cpa", True),
    "OPTIMIZE_RETURN_ON_ADVERTISING_SPEND": ("target_roas", True),
    "OPTIMIZE_PRE_REGISTRATION_CONVERSION_VOLUME": ("maximize_conversions", False),
    "OPTIMIZE_INSTALLS_WITHOUT_TARGET_INSTALL_COST": ("maximize_conversions", False),
    "OPTIMIZE_IN_APP_CONVERSIONS_WITHOUT_TARGET_CPA": ("maximize_conversions", False),
    "OPTIMIZE_TOTAL_VALUE_WITHOUT_TARGET_ROAS": ("maximize_conversion_value", False),
}


def register(mcp, ctx: AppContext) -> None:
    @mcp.tool()
    def create_app_campaign(
        customer_id: str,
        name: str,
        campaign_budget_resource_name: str,
        app_id: str,
        app_store: str,
        bidding_strategy_goal_type: str,
        target_cpa: float | None = None,
        target_roas: float | None = None,
        campaign_sub_type: str = "APP_CAMPAIGN",
        campaign_group_id: str | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        contains_eu_political_advertising: str = DEFAULT_EU_POLITICAL_ADVERTISING,
    ) -> dict:
        """Propose creating an app campaign (app installs or app engagement).
        Created PAUSED.

        ``app_store`` must be ``APPLE_APP_STORE`` or ``GOOGLE_APP_STORE``.
        ``bidding_strategy_goal_type`` picks the v25 goal and therefore the
        bidding strategy; goals that need a target require it:

        - ``OPTIMIZE_INSTALLS_TARGET_INSTALL_COST`` / ``OPTIMIZE_IN_APP_CONVERSIONS_TARGET_INSTALL_COST``
          / ``OPTIMIZE_IN_APP_CONVERSIONS_TARGET_CONVERSION_COST`` -> ``target_cpa``
        - ``OPTIMIZE_RETURN_ON_ADVERTISING_SPEND`` -> ``target_roas``
        - ``OPTIMIZE_INSTALLS_WITHOUT_TARGET_INSTALL_COST`` /
          ``OPTIMIZE_IN_APP_CONVERSIONS_WITHOUT_TARGET_CPA`` -> Maximize Conversions
        - ``OPTIMIZE_TOTAL_VALUE_WITHOUT_TARGET_ROAS`` -> Maximize Conversion Value
        - ``OPTIMIZE_PRE_REGISTRATION_CONVERSION_VOLUME`` -> Maximize Conversions
        """
        if not name.strip():
            raise ValueError("name must not be empty.")
        if app_store not in {"APPLE_APP_STORE", "GOOGLE_APP_STORE"}:
            raise ValueError("app_store must be APPLE_APP_STORE or GOOGLE_APP_STORE.")
        if not app_id.strip():
            raise ValueError("app_id must not be empty.")
        if campaign_sub_type not in {"APP_CAMPAIGN", "APP_CAMPAIGN_FOR_ENGAGEMENT"}:
            raise ValueError(
                "campaign_sub_type must be APP_CAMPAIGN or APP_CAMPAIGN_FOR_ENGAGEMENT."
            )
        if bidding_strategy_goal_type not in _GOAL_BIDDING:
            raise ValueError(
                f"Unknown bidding_strategy_goal_type {bidding_strategy_goal_type!r}. "
                f"Valid values: {sorted(_GOAL_BIDDING)}"
            )
        strategy, requires_target = _GOAL_BIDDING[bidding_strategy_goal_type]
        if requires_target and strategy == "target_cpa" and target_cpa is None:
            raise ValueError(
                f"{bidding_strategy_goal_type} requires target_cpa (target cost)."
            )
        if requires_target and strategy == "target_roas" and target_roas is None:
            raise ValueError(
                f"{bidding_strategy_goal_type} requires target_roas."
            )
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
            client.enums.AdvertisingChannelTypeEnum.MULTI_CHANNEL
        )
        campaign.advertising_channel_sub_type = (
            client.enums.AdvertisingChannelSubTypeEnum[campaign_sub_type].value
        )
        campaign.status = client.enums.CampaignStatusEnum.PAUSED
        campaign.app_campaign_setting.app_id = app_id.strip()
        campaign.app_campaign_setting.app_store = (
            client.enums.AppCampaignAppStoreEnum[app_store].value
        )
        campaign.app_campaign_setting.bidding_strategy_goal_type = (
            client.enums.AppCampaignBiddingStrategyGoalTypeEnum[
                bidding_strategy_goal_type
            ].value
        )
        if strategy == "target_cpa":
            campaign.target_cpa.target_cpa_micros = micros(target_cpa)
        elif strategy == "target_roas":
            campaign.target_roas.target_roas = target_roas
        elif strategy == "maximize_conversions":
            client.copy_from(
                campaign.maximize_conversions, client.get_type("MaximizeConversions")
            )
        else:  # maximize_conversion_value
            client.copy_from(
                campaign.maximize_conversion_value,
                client.get_type("MaximizeConversionValue"),
            )
        if campaign_group_id is not None:
            campaign.campaign_group = client.get_service(
                "CampaignGroupService"
            ).campaign_group_path(
                customer_id.replace("-", ""), str(campaign_group_id)
            )
        apply_campaign_dates(campaign, start_date=start_date, end_date=end_date)
        apply_required_campaign_fields(
            client,
            campaign,
            contains_eu_political_advertising=contains_eu_political_advertising,
        )

        description = (
            f"Create app campaign '{name}' (app {app_store}/{app_id}, "
            f"goal {bidding_strategy_goal_type}), created PAUSED"
        )

        def execute():
            return ctx.client.mutate("CampaignService", customer_id, [operation])

        return ctx.safety.propose(
            tool_name="create_app_campaign",
            customer_id=customer_id,
            description=description,
            payload={
                "name": name,
                "app_id": app_id,
                "app_store": app_store,
                "bidding_strategy_goal_type": bidding_strategy_goal_type,
                "target_cpa": target_cpa,
                "target_roas": target_roas,
                "campaign_sub_type": campaign_sub_type,
                "campaign_group_id": campaign_group_id,
                "start_date": start_date,
                "end_date": end_date,
                "contains_eu_political_advertising": contains_eu_political_advertising,
            },
            execute=execute,
        )
