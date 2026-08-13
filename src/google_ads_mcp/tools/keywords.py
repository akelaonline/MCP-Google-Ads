"""Keyword and negative-keyword tools."""

from __future__ import annotations

from google.protobuf import field_mask_pb2

from ..client import micros
from ..context import AppContext


def register(mcp, ctx: AppContext) -> None:
    @mcp.tool()
    def add_keywords(
        customer_id: str,
        ad_group_id: str,
        keywords: list[dict],
        cpc_bid: float | None = None,
    ) -> dict:
        """Propose adding one or more keywords to an ad group.

        Args:
            keywords: list of {"text": "running shoes", "match_type": "PHRASE"}.
                match_type is one of EXACT, PHRASE, BROAD.
            cpc_bid: Optional per-keyword max CPC override (currency units), applied to all.
        """
        client = ctx.client.raw
        operations = []
        for kw in keywords:
            operation = client.get_type("AdGroupCriterionOperation")
            criterion = operation.create
            criterion.ad_group = client.get_service("AdGroupService").ad_group_path(
                customer_id.replace("-", ""), ad_group_id
            )
            criterion.status = client.enums.AdGroupCriterionStatusEnum.ENABLED
            criterion.keyword.text = kw["text"]
            criterion.keyword.match_type = client.enums.KeywordMatchTypeEnum[
                kw.get("match_type", "BROAD")
            ].value
            if cpc_bid is not None:
                criterion.cpc_bid_micros = micros(cpc_bid)
            operations.append(operation)

        description = (
            f"Add {len(keywords)} keyword(s) to ad group {ad_group_id}: "
            + ", ".join(
                f"[{k.get('match_type', 'BROAD')}] {k['text']}" for k in keywords
            )
        )

        def execute():
            return ctx.client.mutate("AdGroupCriterionService", customer_id, operations)

        return ctx.safety.propose(
            tool_name="add_keywords",
            customer_id=customer_id,
            description=description,
            payload={
                "ad_group_id": ad_group_id,
                "keywords": keywords,
                "cpc_bid": cpc_bid,
            },
            execute=execute,
        )

    @mcp.tool()
    def update_keyword_status(
        customer_id: str, ad_group_id: str, criterion_id: str, status: str
    ) -> dict:
        """Propose pausing, enabling, or removing a keyword.

        Args:
            status: ENABLED, PAUSED, or REMOVED.
        """
        client = ctx.client.raw
        operation = client.get_type("AdGroupCriterionOperation")
        resource_name = client.get_service(
            "AdGroupCriterionService"
        ).ad_group_criterion_path(
            customer_id.replace("-", ""), ad_group_id, criterion_id
        )
        operation.update.resource_name = resource_name
        operation.update.status = client.enums.AdGroupCriterionStatusEnum[status].value
        operation.update_mask.CopyFrom(field_mask_pb2.FieldMask(paths=["status"]))

        description = (
            f"Set keyword {criterion_id} (ad group {ad_group_id}) status -> {status}"
        )

        def execute():
            return ctx.client.mutate(
                "AdGroupCriterionService", customer_id, [operation]
            )

        return ctx.safety.propose(
            tool_name="update_keyword_status",
            customer_id=customer_id,
            description=description,
            payload={
                "ad_group_id": ad_group_id,
                "criterion_id": criterion_id,
                "status": status,
            },
            execute=execute,
        )

    @mcp.tool()
    def update_keyword_bid(
        customer_id: str, ad_group_id: str, criterion_id: str, cpc_bid: float
    ) -> dict:
        """Propose changing an existing keyword's max CPC bid, in place —
        no need to remove and re-add it (which would lose its Quality Score
        history and any accumulated performance data).

        Args:
            cpc_bid: New max CPC, in currency units (e.g. 25.50).
        """
        client = ctx.client.raw
        operation = client.get_type("AdGroupCriterionOperation")
        resource_name = client.get_service(
            "AdGroupCriterionService"
        ).ad_group_criterion_path(
            customer_id.replace("-", ""), ad_group_id, criterion_id
        )
        operation.update.resource_name = resource_name
        operation.update.cpc_bid_micros = micros(cpc_bid)
        operation.update_mask.CopyFrom(
            field_mask_pb2.FieldMask(paths=["cpc_bid_micros"])
        )

        description = (
            f"Set keyword {criterion_id} (ad group {ad_group_id}) CPC bid -> "
            f"${cpc_bid:,.2f}"
        )

        def execute():
            return ctx.client.mutate(
                "AdGroupCriterionService", customer_id, [operation]
            )

        return ctx.safety.propose(
            tool_name="update_keyword_bid",
            customer_id=customer_id,
            description=description,
            payload={
                "ad_group_id": ad_group_id,
                "criterion_id": criterion_id,
                "cpc_bid": cpc_bid,
            },
            execute=execute,
        )

    @mcp.tool()
    def update_keyword_match_type(
        customer_id: str, ad_group_id: str, criterion_id: str, match_type: str
    ) -> dict:
        """Propose changing an existing keyword's match type (e.g. BROAD ->
        PHRASE to tighten targeting after seeing wasted spend in the search
        terms report), in place.

        Note: Google Ads does NOT actually support mutating match_type on an
        existing keyword criterion via the API (it's an immutable field on
        KeywordInfo) — this tool implements the correct workaround: it adds
        a new keyword with the same text and the new match_type, then
        removes the old one, as a single atomic batch of operations so
        there's no gap where neither variant is active.

        Args:
            match_type: EXACT, PHRASE, or BROAD.
        """
        client = ctx.client.raw
        customer_id_clean = customer_id.replace("-", "")

        # Look up the existing keyword's text and current cpc_bid so the
        # replacement preserves them.
        query = f"""
            SELECT ad_group_criterion.keyword.text, ad_group_criterion.cpc_bid_micros
            FROM ad_group_criterion
            WHERE ad_group_criterion.criterion_id = {int(criterion_id)}
              AND ad_group.id = {int(ad_group_id)}
        """
        rows = ctx.client.search(customer_id, query)
        if not rows:
            raise ValueError(
                f"No keyword found with criterion_id={criterion_id} in ad group "
                f"{ad_group_id}."
            )
        existing_text = rows[0]["ad_group_criterion"]["keyword"]["text"]
        existing_cpc_micros = rows[0]["ad_group_criterion"].get("cpc_bid_micros")

        description = (
            f"Change keyword '{existing_text}' (criterion {criterion_id}, ad group "
            f"{ad_group_id}) match type -> {match_type} (recreated, old removed)"
        )

        def execute():
            add_operation = client.get_type("AdGroupCriterionOperation")
            new_criterion = add_operation.create
            new_criterion.ad_group = client.get_service(
                "AdGroupService"
            ).ad_group_path(customer_id_clean, ad_group_id)
            new_criterion.status = client.enums.AdGroupCriterionStatusEnum.ENABLED
            new_criterion.keyword.text = existing_text
            new_criterion.keyword.match_type = client.enums.KeywordMatchTypeEnum[
                match_type
            ].value
            if existing_cpc_micros:
                new_criterion.cpc_bid_micros = int(existing_cpc_micros)

            remove_operation = client.get_type("AdGroupCriterionOperation")
            remove_operation.remove = client.get_service(
                "AdGroupCriterionService"
            ).ad_group_criterion_path(customer_id_clean, ad_group_id, criterion_id)

            return ctx.client.mutate(
                "AdGroupCriterionService",
                customer_id,
                [add_operation, remove_operation],
            )

        return ctx.safety.propose(
            tool_name="update_keyword_match_type",
            customer_id=customer_id,
            description=description,
            payload={
                "ad_group_id": ad_group_id,
                "criterion_id": criterion_id,
                "match_type": match_type,
            },
            execute=execute,
        )

    @mcp.tool()
    def remove_keyword(customer_id: str, ad_group_id: str, criterion_id: str) -> dict:
        """Propose permanently removing a keyword from an ad group."""
        client = ctx.client.raw
        operation = client.get_type("AdGroupCriterionOperation")
        operation.remove = client.get_service(
            "AdGroupCriterionService"
        ).ad_group_criterion_path(
            customer_id.replace("-", ""), ad_group_id, criterion_id
        )

        description = f"REMOVE keyword {criterion_id} from ad group {ad_group_id}"

        def execute():
            return ctx.client.mutate(
                "AdGroupCriterionService", customer_id, [operation]
            )

        return ctx.safety.propose(
            tool_name="remove_keyword",
            customer_id=customer_id,
            description=description,
            payload={"ad_group_id": ad_group_id, "criterion_id": criterion_id},
            execute=execute,
        )

    @mcp.tool()
    def add_negative_keywords(
        customer_id: str,
        keywords: list[dict],
        campaign_id: str | None = None,
        ad_group_id: str | None = None,
    ) -> dict:
        """Propose adding negative keywords, at campaign level or ad-group level.

        Provide exactly one of campaign_id or ad_group_id.

        Args:
            keywords: list of {"text": "free", "match_type": "BROAD"}.
        """
        if bool(campaign_id) == bool(ad_group_id):
            raise ValueError("Provide exactly one of campaign_id or ad_group_id.")

        client = ctx.client.raw
        operations = []

        if campaign_id:
            service_name = "CampaignCriterionService"
            for kw in keywords:
                operation = client.get_type("CampaignCriterionOperation")
                criterion = operation.create
                criterion.campaign = client.get_service(
                    "CampaignService"
                ).campaign_path(customer_id.replace("-", ""), campaign_id)
                criterion.negative = True
                criterion.keyword.text = kw["text"]
                criterion.keyword.match_type = client.enums.KeywordMatchTypeEnum[
                    kw.get("match_type", "BROAD")
                ].value
                operations.append(operation)
            scope = f"campaign {campaign_id}"
        else:
            service_name = "AdGroupCriterionService"
            for kw in keywords:
                operation = client.get_type("AdGroupCriterionOperation")
                criterion = operation.create
                criterion.ad_group = client.get_service("AdGroupService").ad_group_path(
                    customer_id.replace("-", ""), ad_group_id
                )
                criterion.negative = True
                criterion.keyword.text = kw["text"]
                criterion.keyword.match_type = client.enums.KeywordMatchTypeEnum[
                    kw.get("match_type", "BROAD")
                ].value
                operations.append(operation)
            scope = f"ad group {ad_group_id}"

        description = (
            f"Add {len(keywords)} negative keyword(s) to {scope}: "
            + ", ".join(
                f"[{k.get('match_type', 'BROAD')}] {k['text']}" for k in keywords
            )
        )

        def execute():
            return ctx.client.mutate(service_name, customer_id, operations)

        return ctx.safety.propose(
            tool_name="add_negative_keywords",
            customer_id=customer_id,
            description=description,
            payload={
                "campaign_id": campaign_id,
                "ad_group_id": ad_group_id,
                "keywords": keywords,
            },
            execute=execute,
        )
