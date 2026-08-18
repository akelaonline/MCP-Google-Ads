"""Compatibility helpers for campaign creation against Google Ads API v25."""

from __future__ import annotations

from datetime import date

DEFAULT_EU_POLITICAL_ADVERTISING = "DOES_NOT_CONTAIN_EU_POLITICAL_ADVERTISING"
_ALLOWED_EU_POLITICAL_VALUES = {
    "CONTAINS_EU_POLITICAL_ADVERTISING",
    "DOES_NOT_CONTAIN_EU_POLITICAL_ADVERTISING",
}


def apply_required_campaign_fields(
    client,
    campaign,
    *,
    contains_eu_political_advertising: str = DEFAULT_EU_POLITICAL_ADVERTISING,
) -> None:
    """Set fields that Google requires on every newly-created campaign.

    Google Ads API rejects campaign creates whose EU political-advertising
    self-declaration is left UNSPECIFIED. We default to the normal commercial
    case, while allowing callers to explicitly opt into the restricted
    political-advertising value when that is actually intended.
    """
    if contains_eu_political_advertising not in _ALLOWED_EU_POLITICAL_VALUES:
        raise ValueError(
            "contains_eu_political_advertising must be one of "
            f"{sorted(_ALLOWED_EU_POLITICAL_VALUES)}"
        )
    campaign.contains_eu_political_advertising = (
        client.enums.EuPoliticalAdvertisingStatusEnum[
            contains_eu_political_advertising
        ].value
    )


def apply_campaign_dates(
    campaign,
    *,
    start_date: str | None = None,
    end_date: str | None = None,
) -> None:
    """Map the MCP's date-only inputs to API v25's date-time fields.

    The public MCP API keeps accepting YYYY-MM-DD for backwards compatibility,
    while Google Ads API v23+ requires ``start_date_time`` / ``end_date_time``.
    """
    if start_date:
        campaign.start_date_time = _date_to_api_datetime(start_date, end_of_day=False)
    if end_date:
        campaign.end_date_time = _date_to_api_datetime(end_date, end_of_day=True)


def _date_to_api_datetime(value: str, *, end_of_day: bool) -> str:
    try:
        parsed = date.fromisoformat(value)
    except ValueError as ex:
        raise ValueError(f"Invalid date '{value}'. Expected YYYY-MM-DD.") from ex
    suffix = "23:59:59" if end_of_day else "00:00:00"
    return f"{parsed.strftime('%Y%m%d')} {suffix}"
