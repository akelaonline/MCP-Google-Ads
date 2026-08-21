"""Campaign CRUD tools."""

from __future__ import annotations

from google.protobuf import field_mask_pb2

from ..campaign_compat import (
    DEFAULT_EU_POLITICAL_ADVERTISING,
    apply_campaign_dates,
    apply_required_campaign_fields,
)
from ..context import AppContext


def register(mcp, ctx: AppContext) -> None:
    @mcp.tool()
    def list_campaigns(customer_id: str, status_filter: str | None = None) -> dict:
        """List campaigns, optionally filtered by ENABLED/PAUSED/REMOVED."""
        if status_filter and status_filter not in {"ENABLED", "PAUSED", "REMOVED"}:
            raise ValueError("status_filter must be ENABLED, PAUSED, or REMOVED.")
        where = f"WHERE campaign.status = '{status_filter}'" if status_filter else ""
        rows = ctx.client.search(
            customer_id,
            f"""
            SELECT campaign.id, campaign.name, campaign.status,
                   campaign.advertising_channel_type, campaign.campaign_budget,
                   campaign.contains_eu_political_advertising
            FROM campaign
            {where}
            ORDER BY campaign.name
            """,
        )
        campaigns = [
            {
                "id": row["campaign"]["id"],
                "name": row["campaign"]["name"],
                "status": row["campaign"]["status"],
                "channel_type": row["campaign"].get("advertising_channel_type"),
                "contains_eu_political_advertising": row["campaign"].get(
                    "contains_eu_political_advertising"
                ),
            }
            for row in rows
        ]
        return {"campaigns": campaigns, "count": len(campaigns)}

    @mcp.tool()
    def create_campaign(
        customer_id: str,
        name: str,
        campaign_budget_resource_name: str,
        channel_type: str = "SEARCH",
        bidding_strategy: str = "MAXIMIZE_CONVERSIONS",
        target_cpa: float | None = None,
        target_roas: float | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        contains_eu_political_advertising: str = DEFAULT_EU_POLITICAL_ADVERTISING,
    ) -> dict:
        """Propose creating a new PAUSED campaign."""
        if not name.strip():
            raise ValueError("name must not be empty.")
        if target_cpa is not None and target_cpa <= 0:
            raise ValueError("target_cpa must be greater than 0.")
        if target_roas is not None and target_roas <= 0:
            raise ValueError("target_roas must be greater than 0.")

        client = ctx.client.raw
        operation = client.get_type("CampaignOperation")
        campaign = operation.create
        campaign.name = name
        campaign.campaign_budget = campaign_budget_resource_name
        campaign.advertising_channel_type = client.enums.AdvertisingChannelTypeEnum[
            channel_type
        ].value
        campaign.status = client.enums.CampaignStatusEnum.PAUSED.value
        apply_required_campaign_fields(
            client,
            campaign,
            contains_eu_political_advertising=contains_eu_political_advertising,
        )

        if bidding_strategy == "MANUAL_CPC":
            campaign.manual_cpc.enhanced_cpc_enabled = True
        elif bidding_strategy == "MAXIMIZE_CONVERSIONS":
            client.copy_from(
                campaign.maximize_conversions,
                client.get_type("MaximizeConversions"),
            )
        elif bidding_strategy == "TARGET_CPA":
            if target_cpa is None:
                raise ValueError("target_cpa is required for TARGET_CPA.")
            from ..client import micros

            campaign.target_cpa.target_cpa_micros = micros(target_cpa)
        elif bidding_strategy == "TARGET_ROAS":
            if target_roas is None:
                raise ValueError("target_roas is required for TARGET_ROAS.")
            campaign.target_roas.target_roas = target_roas
        else:
            raise ValueError(f"Unsupported bidding_strategy: {bidding_strategy}")

        apply_campaign_dates(campaign, start_date=start_date, end_date=end_date)
        description = (
            f"Create {channel_type} campaign '{name}' "
            f"(bidding: {bidding_strategy}), created PAUSED"
        )

        def execute():
            return ctx.client.mutate("CampaignService", customer_id, [operation])

        return ctx.safety.propose(
            tool_name="create_campaign",
            customer_id=customer_id,
            description=description,
            payload={
                "name": name,
                "channel_type": channel_type,
                "bidding_strategy": bidding_strategy,
                "target_cpa": target_cpa,
                "target_roas": target_roas,
                "start_date": start_date,
                "end_date": end_date,
                "contains_eu_political_advertising": contains_eu_political_advertising,
            },
            execute=execute,
        )

    @mcp.tool()
    def update_campaign_status(customer_id: str, campaign_id: str, status: str) -> dict:
        """Pause, enable, or remove a campaign using the correct operation shape."""
        if status not in {"ENABLED", "PAUSED", "REMOVED"}:
            raise ValueError("status must be ENABLED, PAUSED, or REMOVED.")
        client = ctx.client.raw
        operation = client.get_type("CampaignOperation")
        resource_name = client.get_service("CampaignService").campaign_path(
            customer_id.replace("-", ""), campaign_id
        )
        if status == "REMOVED":
            operation.remove = resource_name
        else:
            operation.update.resource_name = resource_name
            operation.update.status = client.enums.CampaignStatusEnum[status].value
            operation.update_mask.CopyFrom(field_mask_pb2.FieldMask(paths=["status"]))

        description = f"Set campaign {campaign_id} status -> {status}"

        def execute():
            return ctx.client.mutate("CampaignService", customer_id, [operation])

        return ctx.safety.propose(
            tool_name="update_campaign_status",
            customer_id=customer_id,
            description=description,
            payload={"campaign_id": campaign_id, "status": status},
            execute=execute,
        )

    @mcp.tool()
    def update_campaign_name(customer_id: str, campaign_id: str, new_name: str) -> dict:
        """Propose renaming a campaign."""
        if not new_name.strip():
            raise ValueError("new_name must not be empty.")
        client = ctx.client.raw
        operation = client.get_type("CampaignOperation")
        operation.update.resource_name = client.get_service("CampaignService").campaign_path(
            customer_id.replace("-", ""), campaign_id
        )
        operation.update.name = new_name
        operation.update_mask.CopyFrom(field_mask_pb2.FieldMask(paths=["name"]))
        description = f"Rename campaign {campaign_id} -> '{new_name}'"

        def execute():
            return ctx.client.mutate("CampaignService", customer_id, [operation])

        return ctx.safety.propose(
            tool_name="update_campaign_name",
            customer_id=customer_id,
            description=description,
            payload={"campaign_id": campaign_id, "new_name": new_name},
            execute=execute,
        )

    @mcp.tool()
    def set_campaign_frequency_caps(
        customer_id: str,
        campaign_id: str,
        caps: list[dict],
    ) -> dict:
        """Propose setting frequency caps on a campaign (video/Demand Gen).

        ``caps`` is a list of dicts, each with ``level`` (AD_GROUP_AD,
        AD_GROUP, CAMPAIGN), ``event_type`` (IMPRESSION, VIDEO_VIEW),
        ``time_unit`` (DAY, WEEK, MONTH), ``time_length`` (>= 1) and ``cap``
        (>= 0). For example::

            [
                {"level": "CAMPAIGN", "event_type": "IMPRESSION",
                 "time_unit": "DAY", "time_length": 1, "cap": 4},
                {"level": "AD_GROUP_AD", "event_type": "VIDEO_VIEW",
                 "time_unit": "WEEK", "time_length": 1, "cap": 10},
            ]

        Pass ``caps=[]`` to clear all caps.
        """
        if caps is None:
            raise ValueError("caps must be a list (possibly empty).")
        valid_levels = {"AD_GROUP_AD", "AD_GROUP", "CAMPAIGN"}
        valid_events = {"IMPRESSION", "VIDEO_VIEW"}
        valid_units = {"DAY", "WEEK", "MONTH"}
        for item in caps:
            level = str(item.get("level", "")).strip()
            event = str(item.get("event_type", "")).strip()
            unit = str(item.get("time_unit", "")).strip()
            time_length = item.get("time_length")
            cap = item.get("cap")
            if level not in valid_levels:
                raise ValueError(
                    f"cap.level must be one of {sorted(valid_levels)}, got {level!r}."
                )
            if event not in valid_events:
                raise ValueError(
                    f"cap.event_type must be one of {sorted(valid_events)}, got {event!r}."
                )
            if unit not in valid_units:
                raise ValueError(
                    f"cap.time_unit must be one of {sorted(valid_units)}, got {unit!r}."
                )
            if not isinstance(time_length, int) or time_length < 1:
                raise ValueError("cap.time_length must be an integer >= 1.")
            if not isinstance(cap, int) or cap < 0:
                raise ValueError("cap.cap must be an integer >= 0.")

        client = ctx.client.raw
        operation = client.get_type("CampaignOperation")
        operation.update.resource_name = client.get_service("CampaignService").campaign_path(
            customer_id.replace("-", ""), campaign_id
        )
        for item in caps:
            operation.update.frequency_caps.append(
                {
                    "key": {
                        "level": client.enums.FrequencyCapLevelEnum[
                            str(item["level"]).strip()
                        ].value,
                        "event_type": client.enums.FrequencyCapEventTypeEnum[
                            str(item["event_type"]).strip()
                        ].value,
                        "time_unit": client.enums.FrequencyCapTimeUnitEnum[
                            str(item["time_unit"]).strip()
                        ].value,
                        "time_length": item["time_length"],
                    },
                    "cap": item["cap"],
                }
            )
        operation.update_mask.CopyFrom(
            field_mask_pb2.FieldMask(paths=["frequency_caps"])
        )
        description = (
            f"Set {len(caps)} frequency cap(s) on campaign {campaign_id}"
            if caps
            else f"Clear all frequency caps on campaign {campaign_id}"
        )

        def execute():
            return ctx.client.mutate("CampaignService", customer_id, [operation])

        return ctx.safety.propose(
            tool_name="set_campaign_frequency_caps",
            customer_id=customer_id,
            description=description,
            payload={"campaign_id": campaign_id, "caps": caps},
            execute=execute,
        )

    @mcp.tool()
    def set_campaign_ad_rotation(
        customer_id: str, campaign_id: str, rotation: str
    ) -> dict:
        """Propose changing how ads are rotated within a campaign.

        ``rotation`` values: ``OPTIMIZE`` (favor ads expected to perform
        better), ``CONVERSION_OPTIMIZE`` (optimize for conversions),
        ``ROTATE`` (evenly for 90 days, then optimize) or
        ``ROTATE_INDEFINITELY`` (rotate evenly forever).
        """
        valid = {"OPTIMIZE", "CONVERSION_OPTIMIZE", "ROTATE", "ROTATE_INDEFINITELY"}
        if rotation not in valid:
            raise ValueError(
                f"rotation must be one of {sorted(valid)}, got {rotation!r}."
            )
        client = ctx.client.raw
        operation = client.get_type("CampaignOperation")
        operation.update.resource_name = client.get_service("CampaignService").campaign_path(
            customer_id.replace("-", ""), campaign_id
        )
        operation.update.ad_serving_optimization_status = (
            client.enums.AdServingOptimizationStatusEnum[rotation].value
        )
        operation.update_mask.CopyFrom(
            field_mask_pb2.FieldMask(paths=["ad_serving_optimization_status"])
        )
        description = f"Set ad rotation on campaign {campaign_id} -> {rotation}"

        def execute():
            return ctx.client.mutate("CampaignService", customer_id, [operation])

        return ctx.safety.propose(
            tool_name="set_campaign_ad_rotation",
            customer_id=customer_id,
            description=description,
            payload={"campaign_id": campaign_id, "rotation": rotation},
            execute=execute,
        )

    @mcp.tool()
    def remove_campaign(customer_id: str, campaign_id: str) -> dict:
        """Propose permanently removing a campaign."""
        client = ctx.client.raw
        operation = client.get_type("CampaignOperation")
        operation.remove = client.get_service("CampaignService").campaign_path(
            customer_id.replace("-", ""), campaign_id
        )
        description = f"REMOVE campaign {campaign_id} (irreversible)"

        def execute():
            return ctx.client.mutate("CampaignService", customer_id, [operation])

        return ctx.safety.propose(
            tool_name="remove_campaign",
            customer_id=customer_id,
            description=description,
            payload={"campaign_id": campaign_id},
            execute=execute,
        )
