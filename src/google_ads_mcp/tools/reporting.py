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
        customer_id: str, date_range: str = "LAST_7_DAYS", campaign_id: str | None = None
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
        return {"date_range": date_range, "campaigns": [_flatten_campaign_row(r) for r in rows]}

    @mcp.tool()
    def get_ad_group_performance(
        customer_id: str, date_range: str = "LAST_7_DAYS", campaign_id: str | None = None
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
        customer_id: str, date_range: str = "LAST_7_DAYS", ad_group_id: str | None = None
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
        customer_id: str, date_range: str = "LAST_7_DAYS", campaign_id: str | None = None
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
        customer_id: str, date_range: str = "LAST_7_DAYS", ad_group_id: str | None = None
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
        customer_id: str, date_range: str = "LAST_7_DAYS", campaign_id: str | None = None
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
        customer_id: str, date_range: str = "LAST_7_DAYS", campaign_id: str | None = None
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
        customer_id: str, date_range: str = "LAST_7_DAYS", campaign_id: str | None = None
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
        customer_id: str, date_range: str = "LAST_7_DAYS", campaign_id: str | None = None
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
    def get_change_history(customer_id: str, days: int = 7) -> dict:
        """What changed in this account recently (native change_event resource, max 30 days back)."""
        days = min(days, 30)
        query = f"""
            SELECT
                change_event.change_date_time,
                change_event.change_resource_type,
                change_event.client_type,
                change_event.user_email,
                change_event.resource_change_operation,
                change_event.changed_fields
            FROM change_event
            WHERE change_event.change_date_time DURING LAST_{days}_DAYS
            ORDER BY change_event.change_date_time DESC
            LIMIT 200
        """
        rows = ctx.client.search(customer_id, query)
        return {"days": days, "changes": rows}


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
