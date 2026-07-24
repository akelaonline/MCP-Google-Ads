"""Geo-targeting, language targeting, ad scheduling, and bid modifiers
(device / location / ad schedule).

Every campaign created by this MCP (create_campaign, create_performance_max_campaign)
starts with NO location or language targeting configured — Google Ads
defaults a brand-new campaign to "All countries and territories" if you
never set anything, which is almost never what an agency actually wants.
This module is what closes that gap.
"""

from __future__ import annotations

from ..context import AppContext

# A small, commonly-used set of Google Ads geo target constant IDs so callers
# don't have to look them up via the separate GeoTargetConstantService for
# the obvious cases. Not exhaustive — for anything else, pass the numeric
# criterion ID directly (found via Google's geotargets CSV or GAQL on
# geo_target_constant).
COMMON_GEO_TARGET_IDS: dict[str, int] = {
    "argentina": 2032,
    "buenos aires": 20101,  # CABA (Ciudad Autónoma de Buenos Aires)
    "cordoba": 20102,
    "uruguay": 2858,
    "chile": 2152,
    "mexico": 2484,
    "spain": 2724,
    "united states": 2840,
    "brazil": 2076,
}


def register(mcp, ctx: AppContext) -> None:
    @mcp.tool()
    def add_location_targeting(
        customer_id: str,
        campaign_id: str,
        locations: list[str],
        negative: bool = False,
    ) -> dict:
        """Propose adding location targeting to a campaign.

        Args:
            locations: Each entry is either a key from COMMON_GEO_TARGET_IDS
                (e.g. "argentina", "buenos aires") or a numeric geo target
                constant ID as a string (e.g. "1000073" for a specific city —
                look these up via GAQL on geo_target_constant if not in the
                common list).
            negative: If True, these locations are EXCLUDED instead of targeted.
        """
        client = ctx.client.raw
        customer_id_clean = customer_id.replace("-", "")
        campaign_resource_name = client.get_service("CampaignService").campaign_path(
            customer_id_clean, campaign_id
        )
        geo_service = client.get_service("GeoTargetConstantService")

        operations = []
        resolved = []
        for loc in locations:
            geo_id = COMMON_GEO_TARGET_IDS.get(loc.lower(), loc)
            resolved.append(str(geo_id))
            operation = client.get_type("CampaignCriterionOperation")
            criterion = operation.create
            criterion.campaign = campaign_resource_name
            criterion.negative = negative
            criterion.location.geo_target_constant = geo_service.geo_target_constant_path(
                str(geo_id)
            )
            operations.append(operation)

        verb = "Exclude" if negative else "Target"
        description = f"{verb} location(s) {resolved} on campaign {campaign_id}"

        def execute():
            return ctx.client.mutate("CampaignCriterionService", customer_id, operations)

        return ctx.safety.propose(
            tool_name="add_location_targeting",
            customer_id=customer_id,
            description=description,
            payload={"campaign_id": campaign_id, "locations": locations, "negative": negative},
            execute=execute,
        )

    @mcp.tool()
    def set_language_targeting(customer_id: str, campaign_id: str, language_codes: list[str]) -> dict:
        """Propose setting language targeting on a campaign.

        Args:
            language_codes: Google Ads language constant criterion IDs as
                strings for the common ones: "1003" Spanish, "1000" English,
                "1014" Portuguese. Full list via GAQL on language_constant.
        """
        client = ctx.client.raw
        customer_id_clean = customer_id.replace("-", "")
        campaign_resource_name = client.get_service("CampaignService").campaign_path(
            customer_id_clean, campaign_id
        )
        language_service = client.get_service("LanguageConstantService")

        operations = []
        for code in language_codes:
            operation = client.get_type("CampaignCriterionOperation")
            criterion = operation.create
            criterion.campaign = campaign_resource_name
            criterion.language.language_constant = language_service.language_constant_path(code)
            operations.append(operation)

        description = f"Set language targeting {language_codes} on campaign {campaign_id}"

        def execute():
            return ctx.client.mutate("CampaignCriterionService", customer_id, operations)

        return ctx.safety.propose(
            tool_name="set_language_targeting",
            customer_id=customer_id,
            description=description,
            payload={"campaign_id": campaign_id, "language_codes": language_codes},
            execute=execute,
        )

    @mcp.tool()
    def add_ad_schedule(
        customer_id: str,
        campaign_id: str,
        day_of_week: str,
        start_hour: int,
        end_hour: int,
        bid_modifier: float | None = None,
    ) -> dict:
        """Propose adding an ad schedule (dayparting) entry to a campaign.

        Args:
            day_of_week: MONDAY, TUESDAY, WEDNESDAY, THURSDAY, FRIDAY,
                SATURDAY, or SUNDAY.
            start_hour / end_hour: 0-24, e.g. 9 to 18 for "9am to 6pm".
            bid_modifier: Optional, e.g. 1.2 for +20% bids in this window.
        """
        if not (0 <= start_hour <= 24) or not (0 <= end_hour <= 24):
            raise ValueError("start_hour and end_hour must be between 0 and 24.")
        if start_hour >= end_hour:
            raise ValueError("start_hour must be before end_hour.")

        client = ctx.client.raw
        customer_id_clean = customer_id.replace("-", "")
        campaign_resource_name = client.get_service("CampaignService").campaign_path(
            customer_id_clean, campaign_id
        )

        operation = client.get_type("CampaignCriterionOperation")
        criterion = operation.create
        criterion.campaign = campaign_resource_name
        criterion.ad_schedule.day_of_week = client.enums.DayOfWeekEnum[day_of_week].value
        criterion.ad_schedule.start_hour = start_hour
        criterion.ad_schedule.start_minute = client.enums.MinuteOfHourEnum.ZERO
        criterion.ad_schedule.end_hour = end_hour
        criterion.ad_schedule.end_minute = client.enums.MinuteOfHourEnum.ZERO
        if bid_modifier is not None:
            criterion.bid_modifier = bid_modifier

        description = (
            f"Add ad schedule {day_of_week} {start_hour}:00-{end_hour}:00 to campaign "
            f"{campaign_id}" + (f" (bid modifier x{bid_modifier})" if bid_modifier else "")
        )

        def execute():
            return ctx.client.mutate("CampaignCriterionService", customer_id, [operation])

        return ctx.safety.propose(
            tool_name="add_ad_schedule",
            customer_id=customer_id,
            description=description,
            payload={
                "campaign_id": campaign_id,
                "day_of_week": day_of_week,
                "start_hour": start_hour,
                "end_hour": end_hour,
                "bid_modifier": bid_modifier,
            },
            execute=execute,
        )

    @mcp.tool()
    def set_device_bid_modifier(
        customer_id: str, campaign_id: str, device: str, bid_modifier: float
    ) -> dict:
        """Propose setting a bid modifier for a device type on a campaign.

        Args:
            device: MOBILE, DESKTOP, or TABLET.
            bid_modifier: e.g. 1.3 for +30%, 0.8 for -20%.
        """
        client = ctx.client.raw
        customer_id_clean = customer_id.replace("-", "")
        campaign_resource_name = client.get_service("CampaignService").campaign_path(
            customer_id_clean, campaign_id
        )

        operation = client.get_type("CampaignCriterionOperation")
        criterion = operation.create
        criterion.campaign = campaign_resource_name
        criterion.device.type_ = client.enums.DeviceEnum[device].value
        criterion.bid_modifier = bid_modifier

        description = f"Set {device} bid modifier x{bid_modifier} on campaign {campaign_id}"

        def execute():
            return ctx.client.mutate("CampaignCriterionService", customer_id, [operation])

        return ctx.safety.propose(
            tool_name="set_device_bid_modifier",
            customer_id=customer_id,
            description=description,
            payload={"campaign_id": campaign_id, "device": device, "bid_modifier": bid_modifier},
            execute=execute,
        )

    @mcp.tool()
    def list_campaign_criteria(customer_id: str, campaign_id: str) -> dict:
        """List all targeting criteria on a campaign — locations, languages,
        ad schedules, device modifiers, and negative keywords together."""
        query = f"""
            SELECT campaign_criterion.criterion_id, campaign_criterion.type,
                   campaign_criterion.negative, campaign_criterion.bid_modifier,
                   campaign_criterion.location.geo_target_constant,
                   campaign_criterion.language.language_constant,
                   campaign_criterion.device.type,
                   campaign_criterion.ad_schedule.day_of_week,
                   campaign_criterion.ad_schedule.start_hour,
                   campaign_criterion.ad_schedule.end_hour,
                   campaign_criterion.keyword.text
            FROM campaign_criterion
            WHERE campaign.id = {campaign_id}
        """
        rows = ctx.client.search(customer_id, query)
        return {"campaign_id": campaign_id, "criteria": rows, "count": len(rows)}
