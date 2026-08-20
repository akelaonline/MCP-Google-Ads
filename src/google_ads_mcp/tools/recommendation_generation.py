"""Complete Google Ads v25 GenerateRecommendations campaign-construction surface."""

from __future__ import annotations

import proto
from google.ads.googleads.errors import GoogleAdsException

from ..client import micros
from ..context import AppContext
from ..errors import GoogleAdsMcpError, format_google_ads_exception

_GENERATABLE_TYPES = {
    "CAMPAIGN_BUDGET",
    "KEYWORD",
    "MAXIMIZE_CLICKS_OPT_IN",
    "MAXIMIZE_CONVERSIONS_OPT_IN",
    "MAXIMIZE_CONVERSION_VALUE_OPT_IN",
    "SET_TARGET_CPA",
    "SET_TARGET_ROAS",
    "SITELINK_ASSET",
    "TARGET_CPA_OPT_IN",
    "TARGET_ROAS_OPT_IN",
}
_BIDDING_SIGNAL_TYPES = {
    "CAMPAIGN_BUDGET",
    "MAXIMIZE_CLICKS_OPT_IN",
    "MAXIMIZE_CONVERSIONS_OPT_IN",
    "MAXIMIZE_CONVERSION_VALUE_OPT_IN",
    "SET_TARGET_CPA",
    "SET_TARGET_ROAS",
    "TARGET_CPA_OPT_IN",
    "TARGET_ROAS_OPT_IN",
}
_CONVERSION_SIGNAL_TYPES = _BIDDING_SIGNAL_TYPES - {"CAMPAIGN_BUDGET"}


def register(mcp, ctx: AppContext) -> None:
    @mcp.tool()
    def generate_campaign_construction_recommendations(
        customer_id: str,
        recommendation_types: list[str],
        advertising_channel_type: str,
        seed_keywords: list[str] | None = None,
        url_seed: str | None = None,
        campaign_sitelink_count: int | None = None,
        conversion_tracking_status: str | None = None,
        bidding_strategy_type: str | None = None,
        target_cpa: float | None = None,
        target_roas: float | None = None,
        target_impression_location: str | None = None,
        target_impression_percent: float | None = None,
        max_cpc_bid_ceiling: float | None = None,
        ad_group_type: str | None = None,
        ad_group_keywords: list[dict | str] | None = None,
        current_budget: float | None = None,
        asset_groups: list[dict] | None = None,
        campaign_image_asset_count: int | None = None,
        campaign_call_asset_count: int | None = None,
        country_codes: list[str] | None = None,
        language_codes: list[str] | None = None,
        positive_location_ids: list[str] | None = None,
        negative_location_ids: list[str] | None = None,
        target_partner_search_network: bool | None = None,
        target_content_network: bool | None = None,
        merchant_center_account_id: str | None = None,
        is_new_customer: bool | None = None,
    ) -> dict:
        """Generate any v25 recommendation type supported during campaign construction.

        Google documents ten supported recommendation types for this RPC. The MCP
        validates type-specific signals so an under-specified request is less
        likely to be mistaken for a legitimate empty recommendation response.
        """
        requested: list[str] = []
        for value in recommendation_types:
            name = str(value).strip().upper()
            if name not in _GENERATABLE_TYPES:
                raise ValueError(
                    f"GenerateRecommendations supports only {sorted(_GENERATABLE_TYPES)}; "
                    f"got {name!r}."
                )
            if name not in requested:
                requested.append(name)
        if not requested:
            raise ValueError("recommendation_types must contain at least one supported type.")

        channel = advertising_channel_type.strip().upper()
        if channel not in {"SEARCH", "PERFORMANCE_MAX"}:
            raise ValueError("advertising_channel_type must be SEARCH or PERFORMANCE_MAX.")

        seeds = [str(v).strip() for v in (seed_keywords or []) if str(v).strip()]
        if len(seeds) > 20:
            raise ValueError("seed_keywords supports at most 20 values.")
        url = url_seed.strip() if url_seed else None
        if url is not None and not url.startswith(("https://", "http://")):
            raise ValueError("url_seed must be an http:// or https:// URL.")

        requested_set = set(requested)
        if "KEYWORD" in requested_set and not (seeds or url):
            raise ValueError("KEYWORD generation requires seed_keywords and/or url_seed.")
        if "SITELINK_ASSET" in requested_set and campaign_sitelink_count is None:
            raise ValueError("SITELINK_ASSET generation requires campaign_sitelink_count.")
        if requested_set & _CONVERSION_SIGNAL_TYPES:
            if conversion_tracking_status is None or bidding_strategy_type is None:
                raise ValueError(
                    "Bidding opt-in/target generation requires conversion_tracking_status "
                    "and bidding_strategy_type."
                )
        if "CAMPAIGN_BUDGET" in requested_set:
            if bidding_strategy_type is None:
                raise ValueError("CAMPAIGN_BUDGET generation requires bidding_strategy_type.")
            if not asset_groups:
                raise ValueError(
                    "CAMPAIGN_BUDGET generation requires asset_groups with final_url."
                )
            if channel == "SEARCH":
                if not country_codes or not language_codes:
                    raise ValueError(
                        "Search CAMPAIGN_BUDGET generation requires country_codes and "
                        "language_codes."
                    )
                if not positive_location_ids and not negative_location_ids:
                    raise ValueError(
                        "Search CAMPAIGN_BUDGET generation requires positive_location_ids "
                        "or negative_location_ids."
                    )
                if not ad_group_keywords:
                    raise ValueError(
                        "Search CAMPAIGN_BUDGET generation requires ad_group_keywords."
                    )

        customer = ctx.client.assert_customer_allowed(customer_id)
        raw = ctx.client.raw
        request = raw.get_type("GenerateRecommendationsRequest")
        request.customer_id = customer
        request.advertising_channel_type = getattr(
            raw.enums.AdvertisingChannelTypeEnum, channel
        )
        for name in requested:
            request.recommendation_types.append(
                getattr(raw.enums.RecommendationTypeEnum, name)
            )

        if campaign_sitelink_count is not None:
            if campaign_sitelink_count < 0:
                raise ValueError("campaign_sitelink_count cannot be negative.")
            request.campaign_sitelink_count = campaign_sitelink_count

        if conversion_tracking_status is not None:
            status = conversion_tracking_status.strip().upper()
            try:
                request.conversion_tracking_status = getattr(
                    raw.enums.ConversionTrackingStatusEnum, status
                )
            except AttributeError as ex:
                raise ValueError(f"Unknown ConversionTrackingStatus {status!r}.") from ex

        if bidding_strategy_type is not None:
            strategy = bidding_strategy_type.strip().upper()
            try:
                request.bidding_info.bidding_strategy_type = getattr(
                    raw.enums.BiddingStrategyTypeEnum, strategy
                )
            except AttributeError as ex:
                raise ValueError(f"Unknown BiddingStrategyType {strategy!r}.") from ex
            if target_cpa is not None:
                if target_cpa <= 0:
                    raise ValueError("target_cpa must be greater than 0.")
                request.bidding_info.target_cpa_micros = micros(target_cpa)
            if target_roas is not None:
                if target_roas <= 0:
                    raise ValueError("target_roas must be greater than 0.")
                request.bidding_info.target_roas = target_roas
            if strategy == "TARGET_IMPRESSION_SHARE":
                if target_impression_location is None or target_impression_percent is None:
                    raise ValueError(
                        "TARGET_IMPRESSION_SHARE requires target_impression_location and "
                        "target_impression_percent."
                    )
                location = target_impression_location.strip().upper()
                try:
                    request.bidding_info.target_impression_share_info.location = getattr(
                        raw.enums.TargetImpressionShareLocationEnum, location
                    )
                except AttributeError as ex:
                    raise ValueError(
                        f"Unknown target impression location {location!r}."
                    ) from ex
                percent = float(target_impression_percent)
                if not 0.0001 <= percent <= 100:
                    raise ValueError("target_impression_percent must be in (0, 100].")
                request.bidding_info.target_impression_share_info.target_impression_share_micros = round(
                    percent * 10_000
                )
                if max_cpc_bid_ceiling is not None:
                    if max_cpc_bid_ceiling <= 0:
                        raise ValueError("max_cpc_bid_ceiling must be greater than 0.")
                    request.bidding_info.target_impression_share_info.max_cpc_bid_ceiling = micros(
                        max_cpc_bid_ceiling
                    )

        if seeds or url:
            request.seed_info.keyword_seeds.extend(seeds)
            if url:
                request.seed_info.url_seed = url

        if ad_group_keywords or ad_group_type:
            info = raw.get_type("GenerateRecommendationsRequest.AdGroupInfo")
            if ad_group_type:
                group_type = ad_group_type.strip().upper()
                try:
                    info.ad_group_type = getattr(raw.enums.AdGroupTypeEnum, group_type)
                except AttributeError as ex:
                    raise ValueError(f"Unknown AdGroupType {group_type!r}.") from ex
            for item in ad_group_keywords or []:
                keyword = raw.get_type("KeywordInfo")
                if isinstance(item, str):
                    text = item.strip()
                    match_type = "BROAD"
                else:
                    text = str(item.get("text", "")).strip()
                    match_type = str(item.get("match_type", "BROAD")).strip().upper()
                if not text:
                    raise ValueError("ad_group_keywords cannot contain an empty keyword.")
                if match_type not in {"BROAD", "PHRASE", "EXACT"}:
                    raise ValueError("Keyword match_type must be BROAD, PHRASE, or EXACT.")
                keyword.text = text
                keyword.match_type = getattr(raw.enums.KeywordMatchTypeEnum, match_type)
                info.keywords.append(keyword)
            request.ad_group_info.append(info)

        if current_budget is not None:
            if current_budget <= 0:
                raise ValueError("current_budget must be greater than 0.")
            request.budget_info.current_budget = micros(current_budget)

        for item in asset_groups or []:
            final_url = str(item.get("final_url", "")).strip()
            if not final_url.startswith(("http://", "https://")):
                raise ValueError("Every asset_groups item requires an http(s) final_url.")
            info = raw.get_type("GenerateRecommendationsRequest.AssetGroupInfo")
            info.final_url = final_url
            info.headline.extend(
                [str(v).strip() for v in item.get("headlines", []) if str(v).strip()]
            )
            info.description.extend(
                [
                    str(v).strip()
                    for v in item.get("descriptions", [])
                    if str(v).strip()
                ]
            )
            request.asset_group_info.append(info)

        for field, value in (
            ("campaign_image_asset_count", campaign_image_asset_count),
            ("campaign_call_asset_count", campaign_call_asset_count),
        ):
            if value is not None:
                if value < 0:
                    raise ValueError(f"{field} cannot be negative.")
                setattr(request, field, value)

        request.country_codes.extend(_codes(country_codes or [], upper=True, name="country_codes"))
        request.language_codes.extend(_codes(language_codes or [], upper=False, name="language_codes"))
        request.positive_locations_ids.extend(_ids(positive_location_ids or [], "positive_location_ids"))
        request.negative_locations_ids.extend(_ids(negative_location_ids or [], "negative_location_ids"))

        if target_partner_search_network is not None:
            request.target_partner_search_network = target_partner_search_network
        if target_content_network is not None:
            request.target_content_network = target_content_network
        if merchant_center_account_id is not None:
            if channel != "PERFORMANCE_MAX":
                raise ValueError(
                    "merchant_center_account_id is only valid for PERFORMANCE_MAX."
                )
            request.merchant_center_account_id = _ids(
                [merchant_center_account_id], "merchant_center_account_id"
            )[0]
        if is_new_customer is not None:
            request.is_new_customer = is_new_customer

        try:
            response = ctx.client.service(
                "RecommendationService"
            ).generate_recommendations(request=request)
        except GoogleAdsException as ex:
            raise GoogleAdsMcpError(format_google_ads_exception(ex)) from ex

        recommendations = [
            proto.Message.to_dict(item, preserving_proto_field_name=True)
            for item in response.recommendations
        ]
        return {
            "recommendation_types": requested,
            "advertising_channel_type": channel,
            "recommendations": recommendations,
            "count": len(recommendations),
            "empty_result_note": (
                "Google can return zero recommendations when the campaign is already "
                "in the recommended state or supplied signals remain insufficient."
            ),
        }


def _codes(values: list[str], *, upper: bool, name: str) -> list[str]:
    result = []
    for value in values:
        code = str(value).strip()
        code = code.upper() if upper else code.lower()
        if len(code) != 2 or not code.isalpha():
            raise ValueError(f"{name} values must be two-letter codes.")
        result.append(code)
    return result


def _ids(values: list[str], name: str) -> list[int]:
    result = []
    for value in values:
        try:
            number = int(str(value).strip())
        except ValueError as ex:
            raise ValueError(f"{name} must contain numeric IDs.") from ex
        if number <= 0:
            raise ValueError(f"{name} must contain positive IDs.")
        result.append(number)
    return result
