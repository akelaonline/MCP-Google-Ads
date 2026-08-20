"""Saved Keyword Planner lifecycle for Google Ads API v25.

The existing keyword_planner module covers idea/historical generation. This
module covers the persisted resources exposed by KeywordPlanService,
KeywordPlanCampaignService, KeywordPlanAdGroupService,
KeywordPlanAdGroupKeywordService and KeywordPlanCampaignKeywordService.
"""

from __future__ import annotations

from google.protobuf import field_mask_pb2

from ..client import micros
from ..context import AppContext

_MATCH_TYPES = {"BROAD", "PHRASE", "EXACT"}
_NETWORKS = {"GOOGLE_SEARCH", "GOOGLE_SEARCH_AND_PARTNERS"}
_FORECAST_INTERVALS = {"NEXT_WEEK", "NEXT_MONTH", "NEXT_QUARTER"}


def _positive_id(value: str, field_name: str) -> str:
    text = str(value).strip()
    if not text.isdigit() or int(text) <= 0:
        raise ValueError(f"{field_name} must be a positive numeric ID.")
    return text


def _owned(ctx: AppContext, customer: str, resource: str, field_name: str) -> str:
    return ctx.client.assert_resource_name_customer(
        customer, resource, field_name=field_name
    )


def register(mcp, ctx: AppContext) -> None:
    @mcp.tool()
    def list_keyword_plans(customer_id: str) -> dict:
        """List persisted Keyword Planner plans."""
        rows = ctx.client.search(
            customer_id,
            """
            SELECT
                keyword_plan.resource_name,
                keyword_plan.id,
                keyword_plan.name,
                keyword_plan.forecast_period
            FROM keyword_plan
            ORDER BY keyword_plan.name
            """,
        )
        return {"keyword_plans": rows, "count": len(rows)}

    @mcp.tool()
    def create_keyword_plan(
        customer_id: str,
        name: str,
        forecast_interval: str = "NEXT_MONTH",
        validate_only: bool = False,
    ) -> dict:
        """Propose creating a saved Keyword Planner plan."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        clean_name = str(name).strip()
        if not clean_name:
            raise ValueError("name must not be empty.")
        interval = forecast_interval.strip().upper()
        if interval not in _FORECAST_INTERVALS:
            raise ValueError(f"forecast_interval must be one of {sorted(_FORECAST_INTERVALS)}.")
        raw = ctx.client.raw
        operation = raw.get_type("KeywordPlanOperation")
        operation.create.name = clean_name
        operation.create.forecast_period.date_interval = getattr(
            raw.enums.KeywordPlanForecastIntervalEnum, interval
        )

        def execute():
            return ctx.client.mutate(
                "KeywordPlanService", customer, [operation], validate_only=validate_only
            )

        return ctx.safety.propose(
            tool_name="create_keyword_plan",
            customer_id=customer,
            description=f"Create Keyword Planner plan '{clean_name}' ({interval})",
            payload={"name": clean_name, "forecast_interval": interval, "validate_only": validate_only},
            execute=execute,
        )

    @mcp.tool()
    def update_keyword_plan(
        customer_id: str,
        keyword_plan_resource_name: str,
        name: str | None = None,
        forecast_interval: str | None = None,
        validate_only: bool = False,
    ) -> dict:
        """Propose updating a saved Keyword Planner plan."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        resource = _owned(ctx, customer, keyword_plan_resource_name, "keyword_plan_resource_name")
        raw = ctx.client.raw
        operation = raw.get_type("KeywordPlanOperation")
        plan = operation.update
        plan.resource_name = resource
        paths: list[str] = []
        if name is not None:
            clean_name = str(name).strip()
            if not clean_name:
                raise ValueError("name must not be empty when supplied.")
            plan.name = clean_name
            paths.append("name")
        if forecast_interval is not None:
            interval = forecast_interval.strip().upper()
            if interval not in _FORECAST_INTERVALS:
                raise ValueError(f"forecast_interval must be one of {sorted(_FORECAST_INTERVALS)}.")
            plan.forecast_period.date_interval = getattr(
                raw.enums.KeywordPlanForecastIntervalEnum, interval
            )
            paths.append("forecast_period")
        if not paths:
            raise ValueError("Provide name and/or forecast_interval to update.")
        operation.update_mask.CopyFrom(field_mask_pb2.FieldMask(paths=paths))

        def execute():
            return ctx.client.mutate(
                "KeywordPlanService", customer, [operation], validate_only=validate_only
            )

        return ctx.safety.propose(
            tool_name="update_keyword_plan",
            customer_id=customer,
            description=f"Update Keyword Planner plan {resource}: {', '.join(paths)}",
            payload={"keyword_plan_resource_name": resource, "fields": paths, "validate_only": validate_only},
            execute=execute,
        )

    @mcp.tool()
    def remove_keyword_plan(
        customer_id: str,
        keyword_plan_resource_name: str,
        validate_only: bool = False,
    ) -> dict:
        """Propose permanently removing a saved Keyword Planner plan."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        resource = _owned(ctx, customer, keyword_plan_resource_name, "keyword_plan_resource_name")
        operation = ctx.client.raw.get_type("KeywordPlanOperation")
        operation.remove = resource

        def execute():
            return ctx.client.mutate(
                "KeywordPlanService", customer, [operation], validate_only=validate_only
            )

        return ctx.safety.propose(
            tool_name="remove_keyword_plan",
            customer_id=customer,
            description=f"Remove Keyword Planner plan {resource}",
            payload={"keyword_plan_resource_name": resource, "validate_only": validate_only},
            execute=execute,
        )

    @mcp.tool()
    def list_keyword_plan_campaigns(
        customer_id: str,
        keyword_plan_id: str | None = None,
    ) -> dict:
        """List the campaign resources stored inside Keyword Planner plans."""
        where = ""
        if keyword_plan_id is not None:
            plan_id = _positive_id(keyword_plan_id, "keyword_plan_id")
            where = f"WHERE keyword_plan.id = {plan_id}"
        rows = ctx.client.search(
            customer_id,
            f"""
            SELECT
                keyword_plan_campaign.resource_name,
                keyword_plan_campaign.id,
                keyword_plan_campaign.name,
                keyword_plan_campaign.keyword_plan,
                keyword_plan_campaign.keyword_plan_network,
                keyword_plan_campaign.cpc_bid_micros,
                keyword_plan_campaign.language_constants,
                keyword_plan_campaign.geo_targets
            FROM keyword_plan_campaign
            {where}
            ORDER BY keyword_plan_campaign.name
            """,
        )
        return {"keyword_plan_campaigns": rows, "count": len(rows)}

    @mcp.tool()
    def create_keyword_plan_campaign(
        customer_id: str,
        keyword_plan_resource_name: str,
        name: str,
        cpc_bid: float,
        network: str = "GOOGLE_SEARCH",
        language_constant_id: str = "1000",
        geo_target_ids: list[str] | None = None,
        validate_only: bool = False,
    ) -> dict:
        """Propose creating the single campaign allowed within a Keyword Planner plan."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        plan_resource = _owned(ctx, customer, keyword_plan_resource_name, "keyword_plan_resource_name")
        clean_name = str(name).strip()
        if not clean_name:
            raise ValueError("name must not be empty.")
        if cpc_bid <= 0:
            raise ValueError("cpc_bid must be greater than 0.")
        clean_network = network.strip().upper()
        if clean_network not in _NETWORKS:
            raise ValueError(f"network must be one of {sorted(_NETWORKS)}.")
        lang_id = _positive_id(language_constant_id, "language_constant_id")
        geos = [_positive_id(value, "geo_target_ids") for value in (geo_target_ids or [])]
        if len(geos) > 20:
            raise ValueError("Google Ads allows at most 20 geo targets in a Keyword Plan campaign.")

        raw = ctx.client.raw
        operation = raw.get_type("KeywordPlanCampaignOperation")
        campaign = operation.create
        campaign.name = clean_name
        campaign.keyword_plan = plan_resource
        campaign.keyword_plan_network = getattr(raw.enums.KeywordPlanNetworkEnum, clean_network)
        campaign.cpc_bid_micros = micros(cpc_bid)
        campaign.language_constants.append(f"languageConstants/{lang_id}")
        for geo_id in geos:
            geo = raw.get_type("KeywordPlanGeoTarget")
            geo.geo_target_constant = f"geoTargetConstants/{geo_id}"
            campaign.geo_targets.append(geo)

        def execute():
            return ctx.client.mutate(
                "KeywordPlanCampaignService", customer, [operation], validate_only=validate_only
            )

        return ctx.safety.propose(
            tool_name="create_keyword_plan_campaign",
            customer_id=customer,
            description=f"Create Keyword Plan campaign '{clean_name}' in {plan_resource}",
            payload={
                "keyword_plan_resource_name": plan_resource,
                "name": clean_name,
                "cpc_bid": cpc_bid,
                "network": clean_network,
                "language_constant_id": lang_id,
                "geo_target_ids": geos,
                "validate_only": validate_only,
            },
            execute=execute,
        )

    @mcp.tool()
    def update_keyword_plan_campaign(
        customer_id: str,
        keyword_plan_campaign_resource_name: str,
        name: str | None = None,
        cpc_bid: float | None = None,
        network: str | None = None,
        language_constant_id: str | None = None,
        geo_target_ids: list[str] | None = None,
        validate_only: bool = False,
    ) -> dict:
        """Propose updating a Keyword Planner plan campaign."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        resource = _owned(ctx, customer, keyword_plan_campaign_resource_name, "keyword_plan_campaign_resource_name")
        raw = ctx.client.raw
        operation = raw.get_type("KeywordPlanCampaignOperation")
        campaign = operation.update
        campaign.resource_name = resource
        paths: list[str] = []
        if name is not None:
            clean_name = str(name).strip()
            if not clean_name:
                raise ValueError("name must not be empty when supplied.")
            campaign.name = clean_name
            paths.append("name")
        if cpc_bid is not None:
            if cpc_bid <= 0:
                raise ValueError("cpc_bid must be greater than 0.")
            campaign.cpc_bid_micros = micros(cpc_bid)
            paths.append("cpc_bid_micros")
        if network is not None:
            clean_network = network.strip().upper()
            if clean_network not in _NETWORKS:
                raise ValueError(f"network must be one of {sorted(_NETWORKS)}.")
            campaign.keyword_plan_network = getattr(raw.enums.KeywordPlanNetworkEnum, clean_network)
            paths.append("keyword_plan_network")
        if language_constant_id is not None:
            lang_id = _positive_id(language_constant_id, "language_constant_id")
            campaign.language_constants.append(f"languageConstants/{lang_id}")
            paths.append("language_constants")
        if geo_target_ids is not None:
            geos = [_positive_id(value, "geo_target_ids") for value in geo_target_ids]
            if len(geos) > 20:
                raise ValueError("Google Ads allows at most 20 geo targets in a Keyword Plan campaign.")
            for geo_id in geos:
                geo = raw.get_type("KeywordPlanGeoTarget")
                geo.geo_target_constant = f"geoTargetConstants/{geo_id}"
                campaign.geo_targets.append(geo)
            paths.append("geo_targets")
        if not paths:
            raise ValueError("Provide at least one field to update.")
        operation.update_mask.CopyFrom(field_mask_pb2.FieldMask(paths=paths))

        def execute():
            return ctx.client.mutate(
                "KeywordPlanCampaignService", customer, [operation], validate_only=validate_only
            )

        return ctx.safety.propose(
            tool_name="update_keyword_plan_campaign",
            customer_id=customer,
            description=f"Update Keyword Plan campaign {resource}: {', '.join(paths)}",
            payload={"keyword_plan_campaign_resource_name": resource, "fields": paths, "validate_only": validate_only},
            execute=execute,
        )

    @mcp.tool()
    def remove_keyword_plan_campaign(
        customer_id: str,
        keyword_plan_campaign_resource_name: str,
        validate_only: bool = False,
    ) -> dict:
        """Propose removing a Keyword Planner plan campaign."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        resource = _owned(ctx, customer, keyword_plan_campaign_resource_name, "keyword_plan_campaign_resource_name")
        operation = ctx.client.raw.get_type("KeywordPlanCampaignOperation")
        operation.remove = resource

        def execute():
            return ctx.client.mutate(
                "KeywordPlanCampaignService", customer, [operation], validate_only=validate_only
            )

        return ctx.safety.propose(
            tool_name="remove_keyword_plan_campaign",
            customer_id=customer,
            description=f"Remove Keyword Plan campaign {resource}",
            payload={"keyword_plan_campaign_resource_name": resource, "validate_only": validate_only},
            execute=execute,
        )

    @mcp.tool()
    def list_keyword_plan_ad_groups(customer_id: str, keyword_plan_campaign_id: str | None = None) -> dict:
        """List Keyword Planner ad groups, optionally within one plan campaign."""
        where = ""
        if keyword_plan_campaign_id is not None:
            campaign_id = _positive_id(keyword_plan_campaign_id, "keyword_plan_campaign_id")
            where = f"WHERE keyword_plan_campaign.id = {campaign_id}"
        rows = ctx.client.search(
            customer_id,
            f"""
            SELECT
                keyword_plan_ad_group.resource_name,
                keyword_plan_ad_group.id,
                keyword_plan_ad_group.name,
                keyword_plan_ad_group.keyword_plan_campaign,
                keyword_plan_ad_group.cpc_bid_micros
            FROM keyword_plan_ad_group
            {where}
            ORDER BY keyword_plan_ad_group.name
            """,
        )
        return {"keyword_plan_ad_groups": rows, "count": len(rows)}

    @mcp.tool()
    def create_keyword_plan_ad_group(
        customer_id: str,
        keyword_plan_campaign_resource_name: str,
        name: str,
        cpc_bid: float | None = None,
        validate_only: bool = False,
    ) -> dict:
        """Propose creating an ad group in a Keyword Planner plan campaign."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        campaign_resource = _owned(ctx, customer, keyword_plan_campaign_resource_name, "keyword_plan_campaign_resource_name")
        clean_name = str(name).strip()
        if not clean_name:
            raise ValueError("name must not be empty.")
        if cpc_bid is not None and cpc_bid <= 0:
            raise ValueError("cpc_bid must be greater than 0.")
        operation = ctx.client.raw.get_type("KeywordPlanAdGroupOperation")
        ad_group = operation.create
        ad_group.name = clean_name
        ad_group.keyword_plan_campaign = campaign_resource
        if cpc_bid is not None:
            ad_group.cpc_bid_micros = micros(cpc_bid)

        def execute():
            return ctx.client.mutate(
                "KeywordPlanAdGroupService", customer, [operation], validate_only=validate_only
            )

        return ctx.safety.propose(
            tool_name="create_keyword_plan_ad_group",
            customer_id=customer,
            description=f"Create Keyword Plan ad group '{clean_name}' in {campaign_resource}",
            payload={"keyword_plan_campaign_resource_name": campaign_resource, "name": clean_name, "cpc_bid": cpc_bid, "validate_only": validate_only},
            execute=execute,
        )

    @mcp.tool()
    def update_keyword_plan_ad_group(
        customer_id: str,
        keyword_plan_ad_group_resource_name: str,
        name: str | None = None,
        cpc_bid: float | None = None,
        validate_only: bool = False,
    ) -> dict:
        """Propose updating a Keyword Planner ad group."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        resource = _owned(ctx, customer, keyword_plan_ad_group_resource_name, "keyword_plan_ad_group_resource_name")
        operation = ctx.client.raw.get_type("KeywordPlanAdGroupOperation")
        ad_group = operation.update
        ad_group.resource_name = resource
        paths: list[str] = []
        if name is not None:
            clean_name = str(name).strip()
            if not clean_name:
                raise ValueError("name must not be empty when supplied.")
            ad_group.name = clean_name
            paths.append("name")
        if cpc_bid is not None:
            if cpc_bid <= 0:
                raise ValueError("cpc_bid must be greater than 0.")
            ad_group.cpc_bid_micros = micros(cpc_bid)
            paths.append("cpc_bid_micros")
        if not paths:
            raise ValueError("Provide name and/or cpc_bid to update.")
        operation.update_mask.CopyFrom(field_mask_pb2.FieldMask(paths=paths))

        def execute():
            return ctx.client.mutate(
                "KeywordPlanAdGroupService", customer, [operation], validate_only=validate_only
            )

        return ctx.safety.propose(
            tool_name="update_keyword_plan_ad_group",
            customer_id=customer,
            description=f"Update Keyword Plan ad group {resource}: {', '.join(paths)}",
            payload={"keyword_plan_ad_group_resource_name": resource, "fields": paths, "validate_only": validate_only},
            execute=execute,
        )

    @mcp.tool()
    def remove_keyword_plan_ad_group(
        customer_id: str,
        keyword_plan_ad_group_resource_name: str,
        validate_only: bool = False,
    ) -> dict:
        """Propose removing a Keyword Planner ad group."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        resource = _owned(ctx, customer, keyword_plan_ad_group_resource_name, "keyword_plan_ad_group_resource_name")
        operation = ctx.client.raw.get_type("KeywordPlanAdGroupOperation")
        operation.remove = resource

        def execute():
            return ctx.client.mutate(
                "KeywordPlanAdGroupService", customer, [operation], validate_only=validate_only
            )

        return ctx.safety.propose(
            tool_name="remove_keyword_plan_ad_group",
            customer_id=customer,
            description=f"Remove Keyword Plan ad group {resource}",
            payload={"keyword_plan_ad_group_resource_name": resource, "validate_only": validate_only},
            execute=execute,
        )

    @mcp.tool()
    def list_keyword_plan_ad_group_keywords(customer_id: str, keyword_plan_ad_group_id: str | None = None) -> dict:
        """List positive and negative keywords inside Keyword Planner ad groups."""
        where = ""
        if keyword_plan_ad_group_id is not None:
            ad_group_id = _positive_id(keyword_plan_ad_group_id, "keyword_plan_ad_group_id")
            where = f"WHERE keyword_plan_ad_group.id = {ad_group_id}"
        rows = ctx.client.search(
            customer_id,
            f"""
            SELECT
                keyword_plan_ad_group_keyword.resource_name,
                keyword_plan_ad_group_keyword.id,
                keyword_plan_ad_group_keyword.keyword_plan_ad_group,
                keyword_plan_ad_group_keyword.text,
                keyword_plan_ad_group_keyword.match_type,
                keyword_plan_ad_group_keyword.negative,
                keyword_plan_ad_group_keyword.cpc_bid_micros
            FROM keyword_plan_ad_group_keyword
            {where}
            ORDER BY keyword_plan_ad_group_keyword.text
            """,
        )
        return {"keyword_plan_ad_group_keywords": rows, "count": len(rows)}

    @mcp.tool()
    def add_keyword_plan_ad_group_keywords(
        customer_id: str,
        keyword_plan_ad_group_resource_name: str,
        keywords: list[dict],
        validate_only: bool = False,
    ) -> dict:
        """Propose adding positive/negative keywords to a Keyword Planner ad group.

        Each keyword object accepts text, match_type, negative, and optional
        cpc_bid. CPC is ignored/rejected for negative keywords.
        """
        customer = ctx.client.assert_customer_allowed(customer_id)
        ad_group_resource = _owned(ctx, customer, keyword_plan_ad_group_resource_name, "keyword_plan_ad_group_resource_name")
        if not keywords:
            raise ValueError("keywords must not be empty.")
        if len(keywords) > 10_000:
            raise ValueError("A Keyword Plan supports at most 10,000 positive keywords.")
        raw = ctx.client.raw
        operations = []
        safe_keywords = []
        for item in keywords:
            text = str(item.get("text", "")).strip()
            if not text:
                raise ValueError("Each keyword requires non-empty text.")
            match_type = str(item.get("match_type", "BROAD")).upper()
            if match_type not in _MATCH_TYPES:
                raise ValueError(f"match_type must be one of {sorted(_MATCH_TYPES)}.")
            negative = bool(item.get("negative", False))
            cpc_bid = item.get("cpc_bid")
            if negative and cpc_bid is not None:
                raise ValueError("Negative Keyword Plan keywords cannot have cpc_bid.")
            if cpc_bid is not None and float(cpc_bid) <= 0:
                raise ValueError("cpc_bid must be greater than 0 when supplied.")
            operation = raw.get_type("KeywordPlanAdGroupKeywordOperation")
            keyword = operation.create
            keyword.keyword_plan_ad_group = ad_group_resource
            keyword.text = text
            keyword.match_type = getattr(raw.enums.KeywordMatchTypeEnum, match_type)
            keyword.negative = negative
            if cpc_bid is not None:
                keyword.cpc_bid_micros = micros(float(cpc_bid))
            operations.append(operation)
            safe_keywords.append({"text": text, "match_type": match_type, "negative": negative, "cpc_bid": cpc_bid})

        def execute():
            return ctx.client.mutate(
                "KeywordPlanAdGroupKeywordService", customer, operations, validate_only=validate_only
            )

        return ctx.safety.propose(
            tool_name="add_keyword_plan_ad_group_keywords",
            customer_id=customer,
            description=f"Add {len(operations)} keyword(s) to Keyword Plan ad group {ad_group_resource}",
            payload={"keyword_plan_ad_group_resource_name": ad_group_resource, "keywords": safe_keywords, "validate_only": validate_only},
            execute=execute,
        )

    @mcp.tool()
    def update_keyword_plan_ad_group_keyword(
        customer_id: str,
        keyword_resource_name: str,
        text: str | None = None,
        match_type: str | None = None,
        cpc_bid: float | None = None,
        validate_only: bool = False,
    ) -> dict:
        """Propose updating mutable fields on a Keyword Planner ad-group keyword."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        resource = _owned(ctx, customer, keyword_resource_name, "keyword_resource_name")
        raw = ctx.client.raw
        operation = raw.get_type("KeywordPlanAdGroupKeywordOperation")
        keyword = operation.update
        keyword.resource_name = resource
        paths: list[str] = []
        if text is not None:
            clean_text = str(text).strip()
            if not clean_text:
                raise ValueError("text must not be empty when supplied.")
            keyword.text = clean_text
            paths.append("text")
        if match_type is not None:
            clean_match = match_type.strip().upper()
            if clean_match not in _MATCH_TYPES:
                raise ValueError(f"match_type must be one of {sorted(_MATCH_TYPES)}.")
            keyword.match_type = getattr(raw.enums.KeywordMatchTypeEnum, clean_match)
            paths.append("match_type")
        if cpc_bid is not None:
            if cpc_bid <= 0:
                raise ValueError("cpc_bid must be greater than 0.")
            keyword.cpc_bid_micros = micros(cpc_bid)
            paths.append("cpc_bid_micros")
        if not paths:
            raise ValueError("Provide at least one field to update.")
        operation.update_mask.CopyFrom(field_mask_pb2.FieldMask(paths=paths))

        def execute():
            return ctx.client.mutate(
                "KeywordPlanAdGroupKeywordService", customer, [operation], validate_only=validate_only
            )

        return ctx.safety.propose(
            tool_name="update_keyword_plan_ad_group_keyword",
            customer_id=customer,
            description=f"Update Keyword Plan keyword {resource}: {', '.join(paths)}",
            payload={"keyword_resource_name": resource, "fields": paths, "validate_only": validate_only},
            execute=execute,
        )

    @mcp.tool()
    def remove_keyword_plan_ad_group_keyword(
        customer_id: str,
        keyword_resource_name: str,
        validate_only: bool = False,
    ) -> dict:
        """Propose removing a Keyword Planner ad-group keyword."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        resource = _owned(ctx, customer, keyword_resource_name, "keyword_resource_name")
        operation = ctx.client.raw.get_type("KeywordPlanAdGroupKeywordOperation")
        operation.remove = resource

        def execute():
            return ctx.client.mutate(
                "KeywordPlanAdGroupKeywordService", customer, [operation], validate_only=validate_only
            )

        return ctx.safety.propose(
            tool_name="remove_keyword_plan_ad_group_keyword",
            customer_id=customer,
            description=f"Remove Keyword Plan ad-group keyword {resource}",
            payload={"keyword_resource_name": resource, "validate_only": validate_only},
            execute=execute,
        )

    @mcp.tool()
    def list_keyword_plan_campaign_negative_keywords(
        customer_id: str,
        keyword_plan_campaign_id: str | None = None,
    ) -> dict:
        """List campaign-level negative keywords saved in Keyword Planner."""
        where = ""
        if keyword_plan_campaign_id is not None:
            campaign_id = _positive_id(keyword_plan_campaign_id, "keyword_plan_campaign_id")
            where = f"WHERE keyword_plan_campaign.id = {campaign_id}"
        rows = ctx.client.search(
            customer_id,
            f"""
            SELECT
                keyword_plan_campaign_keyword.resource_name,
                keyword_plan_campaign_keyword.id,
                keyword_plan_campaign_keyword.keyword_plan_campaign,
                keyword_plan_campaign_keyword.text,
                keyword_plan_campaign_keyword.match_type,
                keyword_plan_campaign_keyword.negative
            FROM keyword_plan_campaign_keyword
            {where}
            ORDER BY keyword_plan_campaign_keyword.text
            """,
        )
        return {"campaign_negative_keywords": rows, "count": len(rows)}

    @mcp.tool()
    def add_keyword_plan_campaign_negative_keywords(
        customer_id: str,
        keyword_plan_campaign_resource_name: str,
        keywords: list[dict],
        validate_only: bool = False,
    ) -> dict:
        """Propose adding campaign-level negatives to a Keyword Planner plan."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        campaign_resource = _owned(ctx, customer, keyword_plan_campaign_resource_name, "keyword_plan_campaign_resource_name")
        if not keywords:
            raise ValueError("keywords must not be empty.")
        if len(keywords) > 1000:
            raise ValueError("A Keyword Plan supports at most 1,000 negative keywords total.")
        raw = ctx.client.raw
        operations = []
        safe_keywords = []
        for item in keywords:
            text = str(item.get("text", "")).strip()
            if not text:
                raise ValueError("Each keyword requires non-empty text.")
            match_type = str(item.get("match_type", "BROAD")).upper()
            if match_type not in _MATCH_TYPES:
                raise ValueError(f"match_type must be one of {sorted(_MATCH_TYPES)}.")
            operation = raw.get_type("KeywordPlanCampaignKeywordOperation")
            keyword = operation.create
            keyword.keyword_plan_campaign = campaign_resource
            keyword.text = text
            keyword.match_type = getattr(raw.enums.KeywordMatchTypeEnum, match_type)
            keyword.negative = True
            operations.append(operation)
            safe_keywords.append({"text": text, "match_type": match_type})

        def execute():
            return ctx.client.mutate(
                "KeywordPlanCampaignKeywordService", customer, operations, validate_only=validate_only
            )

        return ctx.safety.propose(
            tool_name="add_keyword_plan_campaign_negative_keywords",
            customer_id=customer,
            description=f"Add {len(operations)} campaign negative(s) to {campaign_resource}",
            payload={"keyword_plan_campaign_resource_name": campaign_resource, "keywords": safe_keywords, "validate_only": validate_only},
            execute=execute,
        )

    @mcp.tool()
    def remove_keyword_plan_campaign_negative_keyword(
        customer_id: str,
        keyword_resource_name: str,
        validate_only: bool = False,
    ) -> dict:
        """Propose removing a campaign-level Keyword Planner negative keyword."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        resource = _owned(ctx, customer, keyword_resource_name, "keyword_resource_name")
        operation = ctx.client.raw.get_type("KeywordPlanCampaignKeywordOperation")
        operation.remove = resource

        def execute():
            return ctx.client.mutate(
                "KeywordPlanCampaignKeywordService", customer, [operation], validate_only=validate_only
            )

        return ctx.safety.propose(
            tool_name="remove_keyword_plan_campaign_negative_keyword",
            customer_id=customer,
            description=f"Remove Keyword Plan campaign negative {resource}",
            payload={"keyword_resource_name": resource, "validate_only": validate_only},
            execute=execute,
        )
