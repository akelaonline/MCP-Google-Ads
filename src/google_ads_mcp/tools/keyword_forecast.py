"""Keyword Planner forecast metrics for Google Ads API v25."""

from __future__ import annotations

from datetime import date

import proto

from ..client import micros
from ..context import AppContext
from ..errors import GoogleAdsMcpError, format_google_ads_exception

_MATCH_TYPES = {"BROAD", "PHRASE", "EXACT"}


def _positive_id(value: str, field_name: str) -> str:
    text = str(value).strip()
    if not text.isdigit() or int(text) <= 0:
        raise ValueError(f"{field_name} must be a positive numeric ID.")
    return text


def register(mcp, ctx: AppContext) -> None:
    @mcp.tool()
    def generate_keyword_forecast_metrics(
        customer_id: str,
        keywords: list[dict],
        max_cpc_bid: float,
        geo_target_ids: list[str] | None = None,
        language_constant_ids: list[str] | None = None,
        start_date: str | None = None,
        end_date: str | None = None,
        currency_code: str | None = None,
    ) -> dict:
        """Generate future Keyword Planner forecast metrics without saving a plan.

        ``keywords`` is a list of objects with ``text`` and optional
        ``match_type`` (BROAD/PHRASE/EXACT). The API v25 forecast contract uses
        ``ForecastAdGroup.keywords`` and a campaign-level Manual CPC bid.
        """
        customer = ctx.client.assert_customer_allowed(customer_id)
        if not keywords:
            raise ValueError("keywords must contain at least one keyword.")
        if len(keywords) > 10_000:
            raise ValueError("Forecast at most 10,000 keywords per call.")
        if max_cpc_bid <= 0:
            raise ValueError("max_cpc_bid must be greater than 0.")

        geos = [_positive_id(value, "geo_target_ids") for value in (geo_target_ids or [])]
        languages = [
            _positive_id(value, "language_constant_ids")
            for value in (language_constant_ids or ["1000"])
        ]
        if len(languages) > 1:
            raise ValueError("Keyword Planner forecast supports at most one target language.")

        if (start_date is None) != (end_date is None):
            raise ValueError("Provide both start_date and end_date, or neither.")
        if start_date is not None:
            try:
                start = date.fromisoformat(start_date)
                end = date.fromisoformat(end_date or "")
            except ValueError as ex:
                raise ValueError("start_date/end_date must use YYYY-MM-DD.") from ex
            if end < start:
                raise ValueError("end_date must be on or after start_date.")
            if (end - start).days > 365:
                raise ValueError("Forecast date range must not exceed one year.")

        if currency_code is not None:
            currency = currency_code.strip().upper()
            if len(currency) != 3 or not currency.isalpha():
                raise ValueError("currency_code must be a three-letter ISO currency code.")
        else:
            currency = None

        raw = ctx.client.raw
        campaign = raw.get_type("CampaignToForecast")
        campaign.bidding_strategy.manual_cpc_bidding_strategy.max_cpc_bid_micros = micros(
            max_cpc_bid
        )
        ga_service = raw.get_service("GoogleAdsService")
        for geo_id in geos:
            campaign.geo_target_constants.append(
                ga_service.geo_target_constant_path(geo_id)
            )
        for language_id in languages:
            campaign.language_constants.append(
                ga_service.language_constant_path(language_id)
            )

        forecast_ad_group = raw.get_type("ForecastAdGroup")
        safe_keywords = []
        for item in keywords:
            text = str(item.get("text", "")).strip()
            if not text:
                raise ValueError("Every keyword requires non-empty text.")
            match_type = str(item.get("match_type", "BROAD")).strip().upper()
            if match_type not in _MATCH_TYPES:
                raise ValueError(f"match_type must be one of {sorted(_MATCH_TYPES)}.")
            keyword = raw.get_type("KeywordInfo")
            keyword.text = text
            keyword.match_type = getattr(raw.enums.KeywordMatchTypeEnum, match_type)
            forecast_ad_group.keywords.append(keyword)
            safe_keywords.append({"text": text, "match_type": match_type})
        campaign.ad_groups.append(forecast_ad_group)

        request = raw.get_type("GenerateKeywordForecastMetricsRequest")
        request.customer_id = customer
        request.campaign = campaign
        if start_date is not None:
            request.forecast_period.start_date = start_date
            request.forecast_period.end_date = end_date
        if currency:
            request.currency_code = currency

        from google.ads.googleads.errors import GoogleAdsException

        try:
            response = ctx.client.service(
                "KeywordPlanIdeaService"
            ).generate_keyword_forecast_metrics(request=request)
        except GoogleAdsException as ex:
            raise GoogleAdsMcpError(format_google_ads_exception(ex)) from ex

        result = proto.Message.to_dict(response, preserving_proto_field_name=True)
        result["request_summary"] = {
            "customer_id": customer,
            "keywords": safe_keywords,
            "max_cpc_bid": max_cpc_bid,
            "geo_target_ids": geos,
            "language_constant_ids": languages,
            "start_date": start_date,
            "end_date": end_date,
            "currency_code": currency,
        }
        return result
