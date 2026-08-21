"""Reporting tools: raw GAQL access plus common pre-built reports."""

from __future__ import annotations

from ..client import from_micros
from ..context import AppContext


def register(mcp, ctx: AppContext) -> None:
    @mcp.tool()
    def run_gaql_query(customer_id: str, query: str) -> dict:
        """Run any Google Ads Query Language (GAQL) query and return the rows.

        Use this for anything not covered by the pre-built report tools.
        Example query:
            SELECT campaign.name, metrics.clicks, metrics.cost_micros
            FROM campaign
            WHERE segments.date DURING LAST_7_DAYS
        """
        rows = ctx.client.search(customer_id, query)
        return {"row_count": len(rows), "rows": rows}

    @mcp.tool()
    def get_campaign_performance(
        customer_id: str,
        date_range: str = "LAST_7_DAYS",
        campaign_id: str | None = None,
    ) -> dict:
        """Campaign-level performance: impressions, clicks, cost, conversions, CTR, CPC.

        Args:
            date_range: A GAQL date literal, e.g. LAST_7_DAYS, LAST_30_DAYS, THIS_MONTH, YESTERDAY.
            campaign_id: Optional, restrict to a single campaign.
        """
        where = f"WHERE segments.date DURING {date_range}"
        if campaign_id:
            where += f" AND campaign.id = {int(campaign_id)}"
        query = f"""
            SELECT
                campaign.id, campaign.name, campaign.status,
                metrics.impressions, metrics.clicks, metrics.cost_micros,
                metrics.conversions, metrics.conversions_value,
                metrics.ctr, metrics.average_cpc
            FROM campaign
            {where}
            ORDER BY metrics.cost_micros DESC
        """
        rows = ctx.client.search(customer_id, query)
        return {
            "date_range": date_range,
            "campaigns": [_flatten_campaign_row(r) for r in rows],
        }

    @mcp.tool()
    def get_ad_group_performance(
        customer_id: str,
        date_range: str = "LAST_7_DAYS",
        campaign_id: str | None = None,
    ) -> dict:
        """Ad-group-level performance metrics."""
        where = f"WHERE segments.date DURING {date_range}"
        if campaign_id:
            where += f" AND campaign.id = {int(campaign_id)}"
        query = f"""
            SELECT
                campaign.name, ad_group.id, ad_group.name, ad_group.status,
                metrics.impressions, metrics.clicks, metrics.cost_micros,
                metrics.conversions, metrics.ctr
            FROM ad_group
            {where}
            ORDER BY metrics.cost_micros DESC
        """
        rows = ctx.client.search(customer_id, query)
        return {"date_range": date_range, "ad_groups": rows}

    @mcp.tool()
    def get_keyword_performance(
        customer_id: str,
        date_range: str = "LAST_7_DAYS",
        ad_group_id: str | None = None,
    ) -> dict:
        """Keyword-level performance, including quality score where available."""
        where = f"WHERE segments.date DURING {date_range}"
        if ad_group_id:
            where += f" AND ad_group.id = {int(ad_group_id)}"
        query = f"""
            SELECT
                ad_group_criterion.criterion_id,
                ad_group_criterion.keyword.text,
                ad_group_criterion.keyword.match_type,
                ad_group_criterion.quality_info.quality_score,
                ad_group.name, campaign.name,
                metrics.impressions, metrics.clicks, metrics.cost_micros,
                metrics.conversions, metrics.ctr, metrics.average_cpc
            FROM keyword_view
            {where}
            ORDER BY metrics.cost_micros DESC
            LIMIT 200
        """
        rows = ctx.client.search(customer_id, query)
        return {"date_range": date_range, "keywords": rows}

    @mcp.tool()
    def get_search_terms_report(
        customer_id: str,
        date_range: str = "LAST_7_DAYS",
        campaign_id: str | None = None,
    ) -> dict:
        """Actual search terms that triggered your ads — the source list for new negatives/keywords."""
        where = f"WHERE segments.date DURING {date_range}"
        if campaign_id:
            where += f" AND campaign.id = {int(campaign_id)}"
        query = f"""
            SELECT
                search_term_view.search_term,
                campaign.name, ad_group.name,
                segments.keyword.info.text, segments.keyword.info.match_type,
                metrics.impressions, metrics.clicks, metrics.cost_micros, metrics.conversions
            FROM search_term_view
            {where}
            ORDER BY metrics.cost_micros DESC
            LIMIT 200
        """
        rows = ctx.client.search(customer_id, query)
        return {"date_range": date_range, "search_terms": rows}

    @mcp.tool()
    def get_ad_performance(
        customer_id: str,
        date_range: str = "LAST_7_DAYS",
        ad_group_id: str | None = None,
    ) -> dict:
        """Ad-level performance, including responsive search ad asset combos."""
        where = f"WHERE segments.date DURING {date_range}"
        if ad_group_id:
            where += f" AND ad_group.id = {int(ad_group_id)}"
        query = f"""
            SELECT
                ad_group_ad.ad.id, ad_group_ad.status,
                ad_group_ad.ad.responsive_search_ad.headlines,
                ad_group_ad.ad.final_urls,
                ad_group.name, campaign.name,
                metrics.impressions, metrics.clicks, metrics.cost_micros,
                metrics.conversions, metrics.ctr
            FROM ad_group_ad
            {where}
            ORDER BY metrics.cost_micros DESC
            LIMIT 200
        """
        rows = ctx.client.search(customer_id, query)
        return {"date_range": date_range, "ads": rows}

    @mcp.tool()
    def get_geographic_performance(
        customer_id: str,
        date_range: str = "LAST_7_DAYS",
        campaign_id: str | None = None,
    ) -> dict:
        """Performance broken down by the physical or presence location of
        the user (where the click came from), not by which location was
        targeted. Useful for spotting spend leaking outside your intended area."""
        where = f"WHERE segments.date DURING {date_range}"
        if campaign_id:
            where += f" AND campaign.id = {int(campaign_id)}"
        query = f"""
            SELECT
                geographic_view.location_type,
                geographic_view.country_criterion_id,
                campaign.name,
                metrics.impressions, metrics.clicks, metrics.cost_micros,
                metrics.conversions
            FROM geographic_view
            {where}
            ORDER BY metrics.cost_micros DESC
            LIMIT 200
        """
        rows = ctx.client.search(customer_id, query)
        return {"date_range": date_range, "geographic_performance": rows}

    @mcp.tool()
    def get_device_performance(
        customer_id: str,
        date_range: str = "LAST_7_DAYS",
        campaign_id: str | None = None,
    ) -> dict:
        """Performance broken down by device (MOBILE / DESKTOP / TABLET),
        segmented at the campaign level — the data behind deciding a
        set_device_bid_modifier call."""
        where = f"WHERE segments.date DURING {date_range}"
        if campaign_id:
            where += f" AND campaign.id = {int(campaign_id)}"
        query = f"""
            SELECT
                campaign.id, campaign.name, segments.device,
                metrics.impressions, metrics.clicks, metrics.cost_micros,
                metrics.conversions, metrics.ctr, metrics.average_cpc
            FROM campaign
            {where}
            ORDER BY metrics.cost_micros DESC
        """
        rows = ctx.client.search(customer_id, query)
        return {"date_range": date_range, "device_performance": rows}

    @mcp.tool()
    def get_asset_performance(
        customer_id: str,
        date_range: str = "LAST_7_DAYS",
        campaign_id: str | None = None,
    ) -> dict:
        """Performance of individual assets (sitelinks, call, message, image,
        promotion, and RSA headline/description assets) — which specific
        piece of creative is actually pulling weight."""
        where = f"WHERE segments.date DURING {date_range}"
        if campaign_id:
            where += f" AND campaign.id = {int(campaign_id)}"
        query = f"""
            SELECT
                asset.id, asset.type, asset.name,
                campaign.name,
                metrics.impressions, metrics.clicks, metrics.cost_micros,
                metrics.conversions
            FROM campaign_asset
            {where}
            ORDER BY metrics.cost_micros DESC
            LIMIT 200
        """
        rows = ctx.client.search(customer_id, query)
        return {"date_range": date_range, "asset_performance": rows}

    @mcp.tool()
    def get_audience_performance(
        customer_id: str,
        date_range: str = "LAST_7_DAYS",
        campaign_id: str | None = None,
    ) -> dict:
        """Performance of attached audiences (remarketing / customer match /
        affinity / in-market) at the ad-group level — which audience is
        actually converting vs. just attached for observation."""
        where = f"WHERE segments.date DURING {date_range}"
        if campaign_id:
            where += f" AND campaign.id = {int(campaign_id)}"
        query = f"""
            SELECT
                ad_group_criterion.criterion_id,
                ad_group_criterion.user_list.user_list,
                ad_group.name, campaign.name,
                metrics.impressions, metrics.clicks, metrics.cost_micros,
                metrics.conversions
            FROM user_list
            {where}
            ORDER BY metrics.cost_micros DESC
            LIMIT 200
        """
        rows = ctx.client.search(customer_id, query)
        return {"date_range": date_range, "audience_performance": rows}

    @mcp.tool()
    def get_change_history(
        customer_id: str,
        days: int = 7,
        resource_type: str | None = None,
        operation: str | None = None,
        user_email: str | None = None,
    ) -> dict:
        """What changed in this account recently (native change_event resource, max 30 days back).

        Optional filters: ``resource_type`` (for example CAMPAIGN, AD_GROUP,
        KEYWORD, BUDGET), ``operation`` (ADD, SET, REMOVE) and ``user_email``
        (the actor, e.g. an MCC user or "system").
        """
        days = min(days, 30)
        filters = [f"change_event.change_date_time DURING LAST_{days}_DAYS"]
        if resource_type:
            resource_type = resource_type.strip().upper()
            if not resource_type.isidentifier():
                raise ValueError("resource_type must be a change-event resource enum name.")
            filters.append(
                f"change_event.change_resource_type = {resource_type}"
            )
        if operation:
            operation = operation.strip().upper()
            if operation not in {"ADD", "SET", "REMOVE"}:
                raise ValueError("operation must be ADD, SET, or REMOVE.")
            filters.append(
                f"change_event.resource_change_operation = {operation}"
            )
        if user_email:
            email = user_email.strip()
            if not email or " " in email or "'" in email:
                raise ValueError("user_email must be a single email address.")
            filters.append(f"change_event.user_email = '{email}'")
        query = f"""
            SELECT
                change_event.change_date_time,
                change_event.change_resource_type,
                change_event.client_type,
                change_event.user_email,
                change_event.resource_change_operation,
                change_event.changed_fields
            FROM change_event
            WHERE {' AND '.join(filters)}
            ORDER BY change_event.change_date_time DESC
            LIMIT 200
        """
        rows = ctx.client.search(customer_id, query)
        return {
            "days": days,
            "filters": {
                "resource_type": resource_type,
                "operation": operation,
                "user_email": user_email,
            },
            "changes": rows,
        }

    @mcp.tool()
    def get_quality_score_report(
        customer_id: str, date_range: str = "LAST_30_DAYS"
    ) -> dict:
        """Aggregate keyword performance by Quality Score bucket.

        Useful for spotting QS 1-3 keywords dragging down account-wide CPC
        and prioritizing optimizations.
        """
        query = f"""
            SELECT
                ad_group_criterion.criterion_id,
                ad_group_criterion.keyword.text,
                ad_group_criterion.quality_info.quality_score,
                ad_group.name, campaign.name,
                metrics.impressions, metrics.clicks, metrics.cost_micros,
                metrics.conversions
            FROM keyword_view
            WHERE segments.date DURING {date_range}
              AND ad_group_criterion.quality_info.quality_score IS NOT NULL
            ORDER BY metrics.cost_micros DESC
            LIMIT 2000
        """
        rows = ctx.client.search(customer_id, query)

        buckets: dict[int, dict] = {}
        for row in rows:
            qs = (
                row.get("ad_group_criterion", {})
                .get("quality_info", {})
                .get("quality_score")
            )
            if qs is None:
                continue
            bucket = buckets.setdefault(
                qs,
                {
                    "quality_score": qs,
                    "keyword_count": 0,
                    "impressions": 0,
                    "clicks": 0,
                    "cost": 0.0,
                    "conversions": 0.0,
                },
            )
            metrics = row.get("metrics", {})
            bucket["keyword_count"] += 1
            bucket["impressions"] += int(metrics.get("impressions", 0))
            bucket["clicks"] += int(metrics.get("clicks", 0))
            bucket["cost"] += from_micros(int(metrics.get("cost_micros", 0)))
            bucket["conversions"] += float(metrics.get("conversions", 0.0) or 0.0)

        return {
            "date_range": date_range,
            "buckets": list(buckets.values()),
            "total_keywords": len(rows),
        }

    @mcp.tool()
    def get_disapproved_ads(
        customer_id: str, campaign_id: str | None = None
    ) -> dict:
        """List ads with policy issues: disapproved, limited by policy, or
        under review — with the specific policy topic and evidence where
        available. This is the fast way to find "why isn't this ad
        serving" without opening the UI, especially relevant for regulated
        categories (health, medical devices, finance) where policy holds
        are common.
        """
        where = "WHERE ad_group_ad.policy_summary.approval_status != APPROVED"
        if campaign_id:
            where += f" AND campaign.id = {int(campaign_id)}"
        query = f"""
            SELECT
                campaign.name, ad_group.name, ad_group_ad.ad.id,
                ad_group_ad.status,
                ad_group_ad.policy_summary.approval_status,
                ad_group_ad.policy_summary.review_status,
                ad_group_ad.policy_summary.policy_topic_entries
            FROM ad_group_ad
            {where}
        """
        rows = ctx.client.search(customer_id, query)
        return {"ads_with_policy_issues": rows, "count": len(rows)}

    @mcp.tool()
    def get_shopping_performance_report(
        customer_id: str,
        campaign_id: str | None = None,
        date_range: str = "LAST_30_DAYS",
    ) -> dict:
        """Shopping campaign performance broken out by individual product
        (via shopping_performance_view) — impressions, clicks, cost,
        conversions per item, so you can see which SKUs are actually
        driving results vs. burning spend with none.
        """
        where = f"WHERE segments.date DURING {date_range}"
        if campaign_id:
            where += f" AND campaign.id = {int(campaign_id)}"
        query = f"""
            SELECT
                campaign.name,
                segments.product_item_id, segments.product_title,
                segments.product_brand, segments.product_type_l1,
                metrics.impressions, metrics.clicks, metrics.cost_micros,
                metrics.conversions, metrics.conversions_value
            FROM shopping_performance_view
            {where}
            ORDER BY metrics.cost_micros DESC
            LIMIT 2000
        """
        rows = ctx.client.search(customer_id, query)
        for row in rows:
            metrics = row.get("metrics", {})
            if "cost_micros" in metrics:
                metrics["cost"] = from_micros(int(metrics["cost_micros"]))
        return {"date_range": date_range, "products": rows, "count": len(rows)}

    @mcp.tool()
    def list_shopping_products(customer_id: str, campaign_id: str | None = None) -> dict:
        """List the distinct products currently serving in Shopping/PMax
        campaigns, read from Google Ads' side (not Merchant Center) — i.e.
        what's actually eligible to show, with basic identifying info. For
        full catalog/feed management (pricing, availability, adding new
        products) use Merchant Center directly; this MCP does not wrap that
        API.
        """
        where = ""
        if campaign_id:
            where = f"WHERE campaign.id = {int(campaign_id)}"
        query = f"""
            SELECT
                campaign.name,
                segments.product_item_id, segments.product_title,
                segments.product_brand, segments.product_type_l1,
                segments.product_condition
            FROM shopping_performance_view
            {where}
        """
        rows = ctx.client.search(customer_id, query)
        seen = {}
        for row in rows:
            item_id = row.get("segments", {}).get("product_item_id")
            if item_id and item_id not in seen:
                seen[item_id] = row
        return {"products": list(seen.values()), "count": len(seen)}

    @mcp.tool()
    def get_impression_share_report(
        customer_id: str,
        date_range: str = "LAST_7_DAYS",
        campaign_id: str | None = None,
    ) -> dict:
        """Search impression share diagnostics per campaign.

        Impression-share values are 0-1 fractions (multiply by 100 for %).
        ``search_budget_lost_impression_share`` is the share lost to budget
        constraints; ``search_rank_lost_impression_share`` the share lost to
        ad rank. Also includes top/absolute-top breakdowns and
        exact-match impression share.
        """
        where = f"WHERE segments.date DURING {date_range}"
        if campaign_id:
            where += f" AND campaign.id = {int(campaign_id)}"
        query = f"""
            SELECT
                campaign.id, campaign.name, campaign.status,
                metrics.impressions, metrics.clicks, metrics.cost_micros,
                metrics.search_impression_share,
                metrics.search_absolute_top_impression_share,
                metrics.search_top_impression_share,
                metrics.search_exact_match_impression_share,
                metrics.search_budget_lost_impression_share,
                metrics.search_budget_lost_top_impression_share,
                metrics.search_budget_lost_absolute_top_impression_share,
                metrics.search_rank_lost_impression_share,
                metrics.search_rank_lost_top_impression_share,
                metrics.search_rank_lost_absolute_top_impression_share
            FROM campaign
            {where}
            ORDER BY campaign.id
        """
        rows = ctx.client.search(customer_id, query)
        for row in rows:
            metrics = row.get("metrics", {})
            if "cost_micros" in metrics:
                metrics["cost"] = from_micros(int(metrics["cost_micros"]))
        return {
            "date_range": date_range,
            "campaigns": rows,
            "count": len(rows),
        }


def _flatten_campaign_row(row: dict) -> dict:
    c, m = row["campaign"], row["metrics"]
    return {
        "id": c["id"],
        "name": c["name"],
        "status": c["status"],
        "impressions": int(m.get("impressions", 0)),
        "clicks": int(m.get("clicks", 0)),
        "cost": from_micros(int(m.get("cost_micros", 0))),
        "conversions": m.get("conversions", 0),
        "conversions_value": m.get("conversions_value", 0),
        "ctr": m.get("ctr", 0),
        "avg_cpc": from_micros(int(m.get("average_cpc", 0))),
    }
