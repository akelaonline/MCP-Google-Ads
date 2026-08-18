"""Google Ads recommendation tools: read, apply, and dismiss them."""

from __future__ import annotations

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
