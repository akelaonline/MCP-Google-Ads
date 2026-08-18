"""Smart Bidding incident/event controls for Google Ads API v25."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from ..context import AppContext

_SUPPORTED_CHANNELS = {"SEARCH", "DISPLAY", "SHOPPING"}
_SUPPORTED_DEVICES = {"DESKTOP", "MOBILE", "TABLET"}


def _parse_interval(start_date_time: str, end_date_time: str) -> tuple[str, str]:
    fmt = "%Y-%m-%d %H:%M:%S"
    try:
        start = datetime.strptime(start_date_time, fmt).replace(tzinfo=UTC)
        end = datetime.strptime(end_date_time, fmt).replace(tzinfo=UTC)
    except ValueError as ex:
        raise ValueError(
            "start_date_time and end_date_time must use yyyy-MM-dd HH:mm:ss."
        ) from ex
    if end <= start:
        raise ValueError("end_date_time must be later than start_date_time.")
    if (end - start).total_seconds() > 14 * 24 * 60 * 60:
        raise ValueError("Smart Bidding event intervals must be 14 days or shorter.")
    return start_date_time, end_date_time


def _scope_fields(
    raw,
    customer_id: str,
    target,
    *,
    scope: str,
    advertising_channel_types: list[str] | None,
    campaign_ids: list[str] | None,
    devices: list[str] | None,
) -> dict[str, Any]:
    scope_name = scope.strip().upper()
    if scope_name not in {"CHANNEL", "CAMPAIGN"}:
        raise ValueError("scope must be CHANNEL or CAMPAIGN.")
    target.scope = getattr(raw.enums.SeasonalityEventScopeEnum, scope_name)

    if scope_name == "CHANNEL":
        if campaign_ids:
            raise ValueError("campaign_ids cannot be set when scope=CHANNEL.")
        channels = advertising_channel_types or ["SEARCH"]
        normalized = [str(value).strip().upper() for value in channels]
        if not normalized or any(value not in _SUPPORTED_CHANNELS for value in normalized):
            raise ValueError(
                "advertising_channel_types must contain only SEARCH, DISPLAY, or SHOPPING."
            )
        for value in normalized:
            target.advertising_channel_types.append(
                getattr(raw.enums.AdvertisingChannelTypeEnum, value)
            )
        scope_summary: dict[str, Any] = {"channels": normalized}
    else:
        if advertising_channel_types:
            raise ValueError(
                "advertising_channel_types cannot be set when scope=CAMPAIGN."
            )
        ids = [str(value).strip() for value in (campaign_ids or [])]
        if not ids or len(ids) > 2000 or any(not value.isdigit() for value in ids):
            raise ValueError(
                "campaign_ids must contain between 1 and 2000 numeric campaign IDs."
            )
        for campaign_id in ids:
            target.campaigns.append(f"customers/{customer_id}/campaigns/{campaign_id}")
        scope_summary = {"campaign_ids": ids}

    normalized_devices = [str(value).strip().upper() for value in (devices or [])]
    if any(value not in _SUPPORTED_DEVICES for value in normalized_devices):
        raise ValueError("devices must contain only DESKTOP, MOBILE, or TABLET.")
    for value in normalized_devices:
        target.devices.append(getattr(raw.enums.DeviceEnum, value))
    scope_summary["devices"] = normalized_devices
    return scope_summary


def register(mcp, ctx: AppContext) -> None:
    @mcp.tool()
    def list_seasonality_adjustments(customer_id: str, limit: int = 100) -> dict:
        """List Smart Bidding seasonality adjustments for a client account."""
        if limit < 1 or limit > 500:
            raise ValueError("limit must be between 1 and 500.")
        rows = ctx.client.search(
            customer_id,
            f"""
            SELECT
                bidding_seasonality_adjustment.resource_name,
                bidding_seasonality_adjustment.seasonality_adjustment_id,
                bidding_seasonality_adjustment.name,
                bidding_seasonality_adjustment.description,
                bidding_seasonality_adjustment.scope,
                bidding_seasonality_adjustment.status,
                bidding_seasonality_adjustment.start_date_time,
                bidding_seasonality_adjustment.end_date_time,
                bidding_seasonality_adjustment.conversion_rate_modifier,
                bidding_seasonality_adjustment.advertising_channel_types,
                bidding_seasonality_adjustment.campaigns,
                bidding_seasonality_adjustment.devices
            FROM bidding_seasonality_adjustment
            ORDER BY bidding_seasonality_adjustment.seasonality_adjustment_id DESC
            LIMIT {limit}
            """,
        )
        return {"seasonality_adjustments": rows, "count": len(rows)}

    @mcp.tool()
    def create_seasonality_adjustment(
        customer_id: str,
        name: str,
        start_date_time: str,
        end_date_time: str,
        conversion_rate_modifier: float,
        scope: str = "CHANNEL",
        advertising_channel_types: list[str] | None = None,
        campaign_ids: list[str] | None = None,
        devices: list[str] | None = None,
        description: str | None = None,
    ) -> dict:
        """Propose a forward-looking Smart Bidding seasonality adjustment."""
        if not name.strip() or len(name) > 255:
            raise ValueError("name must contain 1 to 255 characters.")
        if description is not None and len(description) > 2048:
            raise ValueError("description must be 2048 characters or fewer.")
        if not 0.1 <= float(conversion_rate_modifier) <= 10.0:
            raise ValueError("conversion_rate_modifier must be between 0.1 and 10.0.")
        start, end = _parse_interval(start_date_time, end_date_time)
        customer = ctx.client.assert_customer_allowed(customer_id)
        raw = ctx.client.raw
        operation = raw.get_type("BiddingSeasonalityAdjustmentOperation")
        item = operation.create
        item.name = name.strip()
        item.start_date_time = start
        item.end_date_time = end
        item.conversion_rate_modifier = float(conversion_rate_modifier)
        if description:
            item.description = description
        scope_summary = _scope_fields(
            raw,
            customer,
            item,
            scope=scope,
            advertising_channel_types=advertising_channel_types,
            campaign_ids=campaign_ids,
            devices=devices,
        )

        def execute():
            return ctx.client.mutate(
                "BiddingSeasonalityAdjustmentService", customer, [operation]
            )

        payload = {
            "name": name.strip(),
            "start_date_time": start,
            "end_date_time": end,
            "conversion_rate_modifier": float(conversion_rate_modifier),
            "scope": scope.strip().upper(),
            **scope_summary,
        }
        return ctx.safety.propose(
            tool_name="create_seasonality_adjustment",
            customer_id=customer,
            description=(
                f"Create Smart Bidding seasonality adjustment '{name.strip()}' "
                f"with conversion-rate modifier {conversion_rate_modifier}"
            ),
            payload=payload,
            execute=execute,
        )

    @mcp.tool()
    def remove_seasonality_adjustment(customer_id: str, adjustment_id: str) -> dict:
        """Propose removing a seasonality adjustment."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        identifier = str(adjustment_id).strip()
        if not identifier.isdigit():
            raise ValueError("adjustment_id must be numeric.")
        resource_name = (
            f"customers/{customer}/biddingSeasonalityAdjustments/{identifier}"
        )
        operation = ctx.client.raw.get_type("BiddingSeasonalityAdjustmentOperation")
        operation.remove = resource_name

        def execute():
            return ctx.client.mutate(
                "BiddingSeasonalityAdjustmentService", customer, [operation]
            )

        return ctx.safety.propose(
            tool_name="remove_seasonality_adjustment",
            customer_id=customer,
            description=f"Remove Smart Bidding seasonality adjustment {identifier}",
            payload={"resource_name": resource_name},
            execute=execute,
        )

    @mcp.tool()
    def list_data_exclusions(customer_id: str, limit: int = 100) -> dict:
        """List Smart Bidding conversion data exclusions for a client account."""
        if limit < 1 or limit > 500:
            raise ValueError("limit must be between 1 and 500.")
        rows = ctx.client.search(
            customer_id,
            f"""
            SELECT
                bidding_data_exclusion.resource_name,
                bidding_data_exclusion.data_exclusion_id,
                bidding_data_exclusion.name,
                bidding_data_exclusion.description,
                bidding_data_exclusion.scope,
                bidding_data_exclusion.status,
                bidding_data_exclusion.start_date_time,
                bidding_data_exclusion.end_date_time,
                bidding_data_exclusion.advertising_channel_types,
                bidding_data_exclusion.campaigns,
                bidding_data_exclusion.devices
            FROM bidding_data_exclusion
            ORDER BY bidding_data_exclusion.data_exclusion_id DESC
            LIMIT {limit}
            """,
        )
        return {"data_exclusions": rows, "count": len(rows)}

    @mcp.tool()
    def create_data_exclusion(
        customer_id: str,
        name: str,
        start_date_time: str,
        end_date_time: str,
        scope: str = "CHANNEL",
        advertising_channel_types: list[str] | None = None,
        campaign_ids: list[str] | None = None,
        devices: list[str] | None = None,
        description: str | None = None,
    ) -> dict:
        """Propose excluding bad conversion data from Smart Bidding learning."""
        if not name.strip() or len(name) > 255:
            raise ValueError("name must contain 1 to 255 characters.")
        if description is not None and len(description) > 2048:
            raise ValueError("description must be 2048 characters or fewer.")
        start, end = _parse_interval(start_date_time, end_date_time)
        customer = ctx.client.assert_customer_allowed(customer_id)
        raw = ctx.client.raw
        operation = raw.get_type("BiddingDataExclusionOperation")
        item = operation.create
        item.name = name.strip()
        item.start_date_time = start
        item.end_date_time = end
        if description:
            item.description = description
        scope_summary = _scope_fields(
            raw,
            customer,
            item,
            scope=scope,
            advertising_channel_types=advertising_channel_types,
            campaign_ids=campaign_ids,
            devices=devices,
        )

        def execute():
            return ctx.client.mutate(
                "BiddingDataExclusionService", customer, [operation]
            )

        payload = {
            "name": name.strip(),
            "start_date_time": start,
            "end_date_time": end,
            "scope": scope.strip().upper(),
            **scope_summary,
        }
        return ctx.safety.propose(
            tool_name="create_data_exclusion",
            customer_id=customer,
            description=(
                f"Create Smart Bidding data exclusion '{name.strip()}' for {start} → {end}"
            ),
            payload=payload,
            execute=execute,
        )

    @mcp.tool()
    def remove_data_exclusion(customer_id: str, data_exclusion_id: str) -> dict:
        """Propose removing a Smart Bidding data exclusion."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        identifier = str(data_exclusion_id).strip()
        if not identifier.isdigit():
            raise ValueError("data_exclusion_id must be numeric.")
        resource_name = f"customers/{customer}/biddingDataExclusions/{identifier}"
        operation = ctx.client.raw.get_type("BiddingDataExclusionOperation")
        operation.remove = resource_name

        def execute():
            return ctx.client.mutate(
                "BiddingDataExclusionService", customer, [operation]
            )

        return ctx.safety.propose(
            tool_name="remove_data_exclusion",
            customer_id=customer,
            description=f"Remove Smart Bidding data exclusion {identifier}",
            payload={"resource_name": resource_name},
            execute=execute,
        )
