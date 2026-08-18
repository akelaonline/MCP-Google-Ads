"""Google Ads recommendation tools: read, generate, apply, and dismiss them."""

from __future__ import annotations

import proto

from ..context import AppContext
from ..errors import GoogleAdsMcpError, format_google_ads_exception
from ..helpers import normalize_customer_id


def register(mcp, ctx: AppContext) -> None:
    @mcp.tool()
    def get_recommendations(
        customer_id: str,
        type_filter: str | None = None,
        include_dismissed: bool = False,
    ) -> dict:
        """List Google Ads recommendations for the account.

        API v25 exposes ``recommendation.dismissed`` rather than a status enum.
        By default dismissed recommendations are excluded.
        """
        where_parts = [] if include_dismissed else ["recommendation.dismissed = FALSE"]
        if type_filter:
            value = type_filter.strip().upper()
            if not value or not value.replace("_", "").isalnum():
                raise ValueError("type_filter must be a valid recommendation enum name.")
            where_parts.append(f"recommendation.type = '{value}'")

        where = "WHERE " + " AND ".join(where_parts) if where_parts else ""
        query = f"""
            SELECT
                recommendation.resource_name,
                recommendation.type,
                recommendation.dismissed,
                recommendation.impact.base_metrics.clicks,
                recommendation.impact.base_metrics.cost_micros,
                recommendation.impact.base_metrics.conversions,
                recommendation.impact.base_metrics.impressions,
                recommendation.campaign,
                recommendation.ad_group,
                recommendation.campaign_budget
            FROM recommendation
            {where}
            ORDER BY recommendation.impact.base_metrics.cost_micros DESC
            LIMIT 500
        """
        rows = ctx.client.search(customer_id, query)
        return {"recommendations": rows, "count": len(rows)}

    @mcp.tool()
    def generate_keyword_recommendations(
        customer_id: str,
        seed_keywords: list[str],
        url_seed: str | None = None,
    ) -> dict:
        """Generate fresh Search keyword recommendations from keyword/URL seeds.

        This uses RecommendationService.GenerateRecommendations rather than the
        account's existing recommendation feed. Google can legitimately return
        an empty list when the supplied signals are insufficient or no change is
        recommended.
        """
        seeds = [str(value).strip() for value in seed_keywords if str(value).strip()]
        if not seeds:
            raise ValueError("seed_keywords must contain at least one keyword.")
        if len(seeds) > 20:
            raise ValueError("seed_keywords supports at most 20 keywords.")
        if url_seed is not None:
            url = url_seed.strip()
            if not url.startswith(("https://", "http://")):
                raise ValueError("url_seed must be an http:// or https:// URL.")
        else:
            url = None

        customer = ctx.client.assert_customer_allowed(customer_id)
        raw = ctx.client.raw
        request = raw.get_type("GenerateRecommendationsRequest")
        request.customer_id = customer
        request.advertising_channel_type = raw.enums.AdvertisingChannelTypeEnum.SEARCH
        request.recommendation_types.append(raw.enums.RecommendationTypeEnum.KEYWORD)
        request.seed_info.keyword_seeds.extend(seeds)
        if url:
            request.seed_info.url_seed = url

        service = ctx.client.service("RecommendationService")
        from google.ads.googleads.errors import GoogleAdsException

        try:
            response = service.generate_recommendations(request=request)
        except GoogleAdsException as ex:
            raise GoogleAdsMcpError(format_google_ads_exception(ex)) from ex

        recommendations = [
            proto.Message.to_dict(item, preserving_proto_field_name=True)
            for item in response.recommendations
        ]
        return {
            "recommendation_type": "KEYWORD",
            "advertising_channel_type": "SEARCH",
            "seed_keywords": seeds,
            "url_seed": url,
            "recommendations": recommendations,
            "count": len(recommendations),
        }

    @mcp.tool()
    def apply_recommendation(customer_id: str, resource_name: str) -> dict:
        """Propose applying a Google Ads recommendation by resource_name."""
        if not resource_name.strip():
            raise ValueError("resource_name must not be empty.")
        from google.ads.googleads.errors import GoogleAdsException

        customer_id_norm = normalize_customer_id(customer_id)

        def execute():
            client = ctx.client.raw
            service = client.get_service("RecommendationService")
            operation = client.get_type("ApplyRecommendationOperation")
            operation.resource_name = resource_name
            try:
                return service.apply_recommendation(
                    customer_id=customer_id_norm,
                    operations=[operation],
                    partial_failure=False,
                )
            except GoogleAdsException as ex:
                raise GoogleAdsMcpError(format_google_ads_exception(ex)) from ex

        return ctx.safety.propose(
            tool_name="apply_recommendation",
            customer_id=customer_id,
            description=f"Apply recommendation {resource_name}",
            payload={"resource_name": resource_name},
            execute=execute,
        )

    @mcp.tool()
    def dismiss_recommendation(customer_id: str, resource_name: str) -> dict:
        """Propose dismissing a Google Ads recommendation by resource_name."""
        if not resource_name.strip():
            raise ValueError("resource_name must not be empty.")
        from google.ads.googleads.errors import GoogleAdsException

        customer_id_norm = normalize_customer_id(customer_id)

        def execute():
            client = ctx.client.raw
            service = client.get_service("RecommendationService")
            operation = client.get_type(
                "DismissRecommendationRequest.DismissRecommendationOperation"
            )
            operation.resource_name = resource_name
            try:
                return service.dismiss_recommendation(
                    customer_id=customer_id_norm,
                    operations=[operation],
                    partial_failure=False,
                )
            except GoogleAdsException as ex:
                raise GoogleAdsMcpError(format_google_ads_exception(ex)) from ex

        return ctx.safety.propose(
            tool_name="dismiss_recommendation",
            customer_id=customer_id,
            description=f"Dismiss recommendation {resource_name}",
            payload={"resource_name": resource_name},
            execute=execute,
        )
