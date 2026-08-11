"""Keyword Planner tools: keyword idea generation via KeywordPlanIdeaService.

Read-only — this is the actual "Keyword Planner" functionality (search
volume, competition, CPC bid ranges) that the GAQL-based reporting tools
and the keywords.py management tools do NOT cover. Google Ads' keyword_plan
GAQL resource only reads back plans you've already created manually; it does
NOT expose idea generation. generateKeywordIdeas is a separate RPC
(KeywordPlanIdeaService) and is free to call against any account that has
Google Ads API access — no active spend or existing campaigns required,
just a valid customer_id under the authorized login_customer_id (MCC).
"""

from __future__ import annotations

import logging

from google.ads.googleads.errors import GoogleAdsException

from ..context import AppContext
from ..errors import GoogleAdsMcpError, format_google_ads_exception
from ..helpers import is_valid_customer_id, normalize_customer_id

logger = logging.getLogger(__name__)


def register(mcp, ctx: AppContext) -> None:
    @mcp.tool()
    def generate_keyword_ideas(
        customer_id: str,
        keywords: list[str] | None = None,
        page_url: str | None = None,
        language: str = "en",
        geo_target_ids: list[str] | None = None,
        limit: int = 200,
        include_adult_keywords: bool = False,
    ) -> dict:
        """Generate keyword ideas with real Google Ads search-volume data.

        This is Google Keyword Planner's actual idea-generation endpoint
        (KeywordPlanIdeaService.GenerateKeywordIdeas) — free to call, no ad
        spend required. Use it to find search volume, competition level,
        and CPC bid ranges for topics, or to discover keyword gaps (seed
        with existing site keywords, then diff the ideas against what the
        site already covers).

        Args:
            customer_id: The Ads account to run this under (e.g. an active
                client account under your MCC). Billing/spend on this account
                doesn't matter — it's just the API-quota context for the call.
            keywords: Seed keyword phrases, e.g. ["eb5 visa", "pest control cost"].
                Provide at least one of keywords or page_url.
            page_url: Optional seed URL — Google will extract keyword ideas
                from the page content instead of/in addition to `keywords`.
            language: Language code, e.g. "en" or "es". Mapped to Google Ads'
                internal language criterion IDs (only a common subset is
                supported here — extend LANGUAGE_IDS below if you need more).
            geo_target_ids: Optional list of Google Ads geo target constant IDs
                (e.g. ["2840"] for United States, ["2032"] for Argentina).
                Leave empty for worldwide.
            limit: Max number of ideas to return, sorted by avg monthly searches
                descending. Must be between 1 and 2000.
            include_adult_keywords: Passed through to the API, default False.

        Returns:
            {"idea_count": N, "seed_keywords": [...], "seed_url": "...",
             "ideas": [{keyword, avg_monthly_searches, competition,
             competition_index, low_bid_micros, high_bid_micros, low_bid,
             high_bid}, ...]}
        """
        keywords = keywords or []
        page_url = page_url or ""
        geo_target_ids = geo_target_ids or []

        _validate_inputs(customer_id, keywords, page_url, limit)

        client = ctx.client.raw
        customer_id_norm = normalize_customer_id(customer_id)

        keyword_plan_idea_service = client.get_service("KeywordPlanIdeaService")
        keyword_plan_network = (
            client.enums.KeywordPlanNetworkEnum.GOOGLE_SEARCH_AND_PARTNERS
        )

        request = client.get_type("GenerateKeywordIdeasRequest")
        request.customer_id = customer_id_norm
        request.language = _language_resource_name(language)
        request.geo_target_constants.extend(
            [_geo_target_resource_name(gid) for gid in geo_target_ids]
        )
        request.keyword_plan_network = keyword_plan_network
        request.include_adult_keywords = include_adult_keywords

        if keywords and page_url:
            request.keyword_and_url_seed.url = page_url
            request.keyword_and_url_seed.keywords.extend(keywords)
        elif page_url:
            request.url_seed.url = page_url
        else:
            request.keyword_seed.keywords.extend(keywords)

        logger.info(
            "generate_keyword_ideas customer=%s language=%s geo=%s seed_type=%s",
            customer_id_norm,
            language,
            geo_target_ids,
            "keyword_and_url"
            if (keywords and page_url)
            else ("url" if page_url else "keyword"),
        )

        try:
            response = keyword_plan_idea_service.generate_keyword_ideas(request=request)
        except GoogleAdsException as ex:
            logger.warning("generate_keyword_ideas failed: %s", ex.request_id)
            raise GoogleAdsMcpError(format_google_ads_exception(ex)) from ex

        ideas = []
        for result in response:
            metrics = result.keyword_idea_metrics
            ideas.append(
                {
                    "keyword": result.text,
                    "avg_monthly_searches": metrics.avg_monthly_searches,
                    "competition": (
                        metrics.competition.name
                        if metrics.competition is not None
                        else None
                    ),
                    "competition_index": metrics.competition_index,
                    "low_bid_micros": metrics.low_top_of_page_bid_micros,
                    "high_bid_micros": metrics.high_top_of_page_bid_micros,
                    "low_bid": _micros_to_currency(metrics.low_top_of_page_bid_micros),
                    "high_bid": _micros_to_currency(
                        metrics.high_top_of_page_bid_micros
                    ),
                }
            )

        ideas.sort(key=lambda x: x["avg_monthly_searches"] or 0, reverse=True)
        ideas = ideas[:limit]

        return {
            "idea_count": len(ideas),
            "seed_keywords": keywords,
            "seed_url": page_url,
            "ideas": ideas,
        }

    @mcp.tool()
    def get_keyword_historical_metrics(
        customer_id: str,
        keywords: list[str],
        language: str = "en",
        geo_target_ids: list[str] | None = None,
    ) -> dict:
        """Look up historical search-volume metrics for a specific, known list
        of keywords (no idea expansion — use generate_keyword_ideas for that).

        Useful to re-check volume for a fixed shortlist (e.g. keywords already
        chosen from a gap analysis) without pulling in new suggestions.
        """
        geo_target_ids = geo_target_ids or []

        if not keywords:
            raise ValueError("Provide at least one keyword.")
        _validate_inputs(customer_id, keywords, page_url=None, limit=None)

        client = ctx.client.raw
        customer_id_norm = normalize_customer_id(customer_id)

        keyword_plan_idea_service = client.get_service("KeywordPlanIdeaService")

        request = client.get_type("GenerateKeywordHistoricalMetricsRequest")
        request.customer_id = customer_id_norm
        request.keywords.extend(keywords)
        request.language = _language_resource_name(language)
        request.geo_target_constants.extend(
            [_geo_target_resource_name(gid) for gid in geo_target_ids]
        )

        logger.info(
            "get_keyword_historical_metrics customer=%s language=%s keywords=%d",
            customer_id_norm,
            language,
            len(keywords),
        )

        try:
            response = keyword_plan_idea_service.generate_keyword_historical_metrics(
                request=request
            )
        except GoogleAdsException as ex:
            logger.warning("get_keyword_historical_metrics failed: %s", ex.request_id)
            raise GoogleAdsMcpError(format_google_ads_exception(ex)) from ex

        results = []
        for result in response.results:
            metrics = result.keyword_metrics
            results.append(
                {
                    "keyword": result.text,
                    "avg_monthly_searches": metrics.avg_monthly_searches,
                    "competition": (
                        metrics.competition.name
                        if metrics.competition is not None
                        else None
                    ),
                    "low_bid": _micros_to_currency(metrics.low_top_of_page_bid_micros),
                    "high_bid": _micros_to_currency(
                        metrics.high_top_of_page_bid_micros
                    ),
                }
            )
        return {"result_count": len(results), "results": results}


# Common Google Ads language criterion IDs. Extend as needed —
# full list: https://developers.google.com/google-ads/api/reference/data/codes-formats#languages
LANGUAGE_IDS: dict[str, str] = {
    "ar": "1019",
    "zh": "1017",
    "da": "1009",
    "de": "1001",
    "en": "1000",
    "es": "1003",
    "fi": "1012",
    "fr": "1002",
    "it": "1004",
    "ja": "1015",
    "ko": "1018",
    "nl": "1010",
    "no": "1013",
    "pl": "1020",
    "pt": "1014",
    "ru": "1016",
    "sv": "1021",
    "tr": "1022",
}


def _language_resource_name(language: str) -> str:
    """languageConstants/{id} — static resource name, no service call needed."""
    lang_id = LANGUAGE_IDS.get(language.lower())
    if lang_id is None:
        raise ValueError(
            f"Unsupported language code '{language}'. Known: {sorted(LANGUAGE_IDS)}. "
            "Add it to LANGUAGE_IDS in keyword_planner.py if you need another one."
        )
    return f"languageConstants/{lang_id}"


def _geo_target_resource_name(geo_target_id: str) -> str:
    """geoTargetConstants/{id} — static resource name, no service call needed."""
    return f"geoTargetConstants/{geo_target_id}"


def _validate_inputs(
    customer_id: str,
    keywords: list[str],
    page_url: str | None,
    limit: int | None,
) -> None:
    """Raise ValueError for invalid arguments before calling the API."""
    if not is_valid_customer_id(customer_id):
        raise ValueError(
            f"Invalid customer_id '{customer_id}'. Expected digits and optional dashes."
        )

    if page_url is not None and not keywords and not page_url:
        raise ValueError("Provide at least one of: keywords, page_url.")

    if limit is not None and not (1 <= limit <= 2000):
        raise ValueError("limit must be between 1 and 2000.")

    if keywords and not all(isinstance(k, str) and k.strip() for k in keywords):
        raise ValueError("keywords must be a list of non-empty strings.")

    if (
        page_url is not None
        and page_url
        and not page_url.startswith(("http://", "https://"))
    ):
        raise ValueError("page_url must start with http:// or https://.")


def _micros_to_currency(amount_micros: int | None) -> float | None:
    """Convert micros to a human-readable currency value."""
    if amount_micros is None:
        return None
    return round(amount_micros / 1_000_000, 2)
