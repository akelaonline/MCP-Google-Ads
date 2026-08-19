"""Google Ads recommendation tools: read, generate, apply, dismiss, and auto-apply."""

from __future__ import annotations

import proto
from google.protobuf import field_mask_pb2

from ..context import AppContext
from ..errors import GoogleAdsMcpError, format_google_ads_exception

_AUTO_APPLY_TYPES = {
    "ENHANCED_CPC_OPT_IN",
    "KEYWORD",
    "KEYWORD_MATCH_TYPE",
    "LOWER_TARGET_ROAS",
    "MAXIMIZE_CLICKS_OPT_IN",
    "OPTIMIZE_AD_ROTATION",
    "RAISE_TARGET_CPA",
    "RESPONSIVE_SEARCH_AD",
    "RESPONSIVE_SEARCH_AD_IMPROVE_AD_STRENGTH",
    "SEARCH_PARTNERS_OPT_IN",
    "SEARCH_PLUS_OPT_IN",
    "SET_TARGET_CPA",
    "SET_TARGET_ROAS",
    "TARGET_CPA_OPT_IN",
    "TARGET_ROAS_OPT_IN",
    "USE_BROAD_MATCH_KEYWORD",
}


def _recommendation_type(value: str, *, auto_apply_only: bool = False) -> str:
    clean = str(value).strip().upper()
    if not clean or not clean.replace("_", "").isalnum():
        raise ValueError("recommendation_type must be a valid enum name.")
    if auto_apply_only and clean not in _AUTO_APPLY_TYPES:
        raise ValueError(
            "recommendation_type is not supported by RecommendationSubscriptionService. "
            "Supported types: " + ", ".join(sorted(_AUTO_APPLY_TYPES))
        )
    return clean


def register(mcp, ctx: AppContext) -> None:
    @mcp.tool()
    def get_recommendations(
        customer_id: str,
        type_filter: str | None = None,
        include_dismissed: bool = False,
    ) -> dict:
        """List Google Ads recommendations for the account."""
        where_parts = [] if include_dismissed else ["recommendation.dismissed = FALSE"]
        if type_filter:
            value = _recommendation_type(type_filter)
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
    def list_recommendation_subscriptions(customer_id: str) -> dict:
        """List recommendation types configured for automatic application."""
        rows = ctx.client.search(
            customer_id,
            """
            SELECT
                recommendation_subscription.resource_name,
                recommendation_subscription.type,
                recommendation_subscription.status,
                recommendation_subscription.create_date_time,
                recommendation_subscription.modify_date_time
            FROM recommendation_subscription
            ORDER BY recommendation_subscription.type
            """,
        )
        return {
            "recommendation_subscriptions": rows,
            "count": len(rows),
            "supported_types": sorted(_AUTO_APPLY_TYPES),
        }

    @mcp.tool()
    def set_recommendation_subscription(
        customer_id: str,
        recommendation_type: str,
        enabled: bool,
        validate_only: bool = False,
    ) -> dict:
        """Propose enabling or pausing automatic application of one recommendation type.

        The operation is idempotent: it creates the subscription when absent and
        updates its status when already present. Google does not support deleting
        recommendation subscriptions once created; PAUSED is the off state.
        """
        customer = ctx.client.assert_customer_allowed(customer_id)
        rec_type = _recommendation_type(recommendation_type, auto_apply_only=True)
        target_status = "ENABLED" if enabled else "PAUSED"
        resource_name = (
            f"customers/{customer}/recommendationSubscriptions/{rec_type}"
        )
        escaped_resource = resource_name.replace("\\", "\\\\").replace("'", "\\'")
        existing = ctx.client.search(
            customer,
            f"""
            SELECT recommendation_subscription.resource_name,
                   recommendation_subscription.status,
                   recommendation_subscription.type
            FROM recommendation_subscription
            WHERE recommendation_subscription.resource_name = '{escaped_resource}'
            LIMIT 1
            """,
        )

        raw = ctx.client.raw
        operation = raw.get_type("RecommendationSubscriptionOperation")
        status_value = getattr(raw.enums.RecommendationSubscriptionStatusEnum, target_status)
        type_value = getattr(raw.enums.RecommendationTypeEnum, rec_type)
        mode = "update" if existing else "create"
        if existing:
            subscription = operation.update
            subscription.resource_name = resource_name
            subscription.status = status_value
            operation.update_mask.CopyFrom(field_mask_pb2.FieldMask(paths=["status"]))
        else:
            subscription = operation.create
            subscription.type_ = type_value
            subscription.status = status_value

        service = ctx.client.service("RecommendationSubscriptionService")

        def execute():
            from google.ads.googleads.errors import GoogleAdsException

            request = raw.get_type("MutateRecommendationSubscriptionRequest")
            request.customer_id = customer
            request.operations.append(operation)
            request.partial_failure = False
            request.validate_only = bool(validate_only)
            request.response_content_type = raw.enums.ResponseContentTypeEnum.MUTABLE_RESOURCE
            try:
                response = service.mutate_recommendation_subscription(request=request)
            except GoogleAdsException as ex:
                raise GoogleAdsMcpError(format_google_ads_exception(ex)) from ex
            if validate_only:
                return {
                    "validated": True,
                    "executed": False,
                    "mode": mode,
                    "resource_name": resource_name,
                    "status": target_status,
                }
            result = response.results[0] if response.results else None
            return {
                "mode": mode,
                "resource_name": (
                    getattr(result, "resource_name", None) if result else resource_name
                ),
                "status": target_status,
                "recommendation_type": rec_type,
            }

        return ctx.safety.propose(
            tool_name="set_recommendation_subscription",
            customer_id=customer,
            description=(
                f"{target_status} auto-apply subscription for recommendation type "
                f"{rec_type} on customer {customer}"
            ),
            payload={
                "recommendation_type": rec_type,
                "status": target_status,
                "mode": mode,
                "validate_only": bool(validate_only),
            },
            execute=execute,
        )

    @mcp.tool()
    def get_auto_applied_recommendation_changes(
        customer_id: str,
        limit: int = 100,
    ) -> dict:
        """Show recent account changes made by recommendation subscriptions."""
        if limit < 1 or limit > 1000:
            raise ValueError("limit must be between 1 and 1000.")
        rows = ctx.client.search(
            customer_id,
            f"""
            SELECT
                change_event.change_date_time,
                change_event.change_resource_type,
                change_event.change_resource_name,
                change_event.resource_change_operation,
                change_event.changed_fields,
                change_event.client_type
            FROM change_event
            WHERE change_event.client_type = 'GOOGLE_ADS_RECOMMENDATIONS_SUBSCRIPTION'
            ORDER BY change_event.change_date_time DESC
            LIMIT {limit}
            """,
        )
        return {"changes": rows, "count": len(rows)}

    @mcp.tool()
    def generate_keyword_recommendations(
        customer_id: str,
        seed_keywords: list[str],
        url_seed: str | None = None,
    ) -> dict:
        """Generate fresh Search keyword recommendations from keyword/URL seeds."""
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
        resource = ctx.client.assert_resource_name_customer(
            customer_id,
            resource_name,
            field_name="recommendation resource_name",
        )
        customer = ctx.client.assert_customer_allowed(customer_id)
        from google.ads.googleads.errors import GoogleAdsException

        def execute():
            client = ctx.client.raw
            service = client.get_service("RecommendationService")
            operation = client.get_type("ApplyRecommendationOperation")
            operation.resource_name = resource
            try:
                return service.apply_recommendation(
                    customer_id=customer,
                    operations=[operation],
                    partial_failure=False,
                )
            except GoogleAdsException as ex:
                raise GoogleAdsMcpError(format_google_ads_exception(ex)) from ex

        return ctx.safety.propose(
            tool_name="apply_recommendation",
            customer_id=customer,
            description=f"Apply recommendation {resource}",
            payload={"resource_name": resource},
            execute=execute,
        )

    @mcp.tool()
    def dismiss_recommendation(customer_id: str, resource_name: str) -> dict:
        """Propose dismissing a Google Ads recommendation by resource_name."""
        resource = ctx.client.assert_resource_name_customer(
            customer_id,
            resource_name,
            field_name="recommendation resource_name",
        )
        customer = ctx.client.assert_customer_allowed(customer_id)
        from google.ads.googleads.errors import GoogleAdsException

        def execute():
            client = ctx.client.raw
            service = client.get_service("RecommendationService")
            operation = client.get_type(
                "DismissRecommendationRequest.DismissRecommendationOperation"
            )
            operation.resource_name = resource
            try:
                return service.dismiss_recommendation(
                    customer_id=customer,
                    operations=[operation],
                    partial_failure=False,
                )
            except GoogleAdsException as ex:
                raise GoogleAdsMcpError(format_google_ads_exception(ex)) from ex

        return ctx.safety.propose(
            tool_name="dismiss_recommendation",
            customer_id=customer,
            description=f"Dismiss recommendation {resource}",
            payload={"resource_name": resource},
            execute=execute,
        )
