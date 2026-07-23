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

        description = f"Add {len(keywords)} keyword(s) to ad group {ad_group_id}: " + ", ".join(
            f"[{k.get('match_type', 'BROAD')}] {k['text']}" for k in keywords
        )

        def execute():
            return ctx.client.mutate("AdGroupCriterionService", customer_id, operations)

        return ctx.safety.propose(
            tool_name="add_keywords",
            customer_id=customer_id,
            description=description,
            payload={"ad_group_id": ad_group_id, "keywords": keywords, "cpc_bid": cpc_bid},
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
        resource_name = client.get_service("AdGroupCriterionService").ad_group_criterion_path(
            customer_id.replace("-", ""), ad_group_id, criterion_id
        )
        operation.update.resource_name = resource_name
        operation.update.status = client.enums.AdGroupCriterionStatusEnum[status].value
        operation.update_mask.CopyFrom(field_mask_pb2.FieldMask(paths=["status"]))

        description = f"Set keyword {criterion_id} (ad group {ad_group_id}) status -> {status}"

        def execute():
            return ctx.client.mutate("AdGroupCriterionService", customer_id, [operation])

        return ctx.safety.propose(
            tool_name="update_keyword_status",
            customer_id=customer_id,
            description=description,
            payload={"ad_group_id": ad_group_id, "criterion_id": criterion_id, "status": status},
            execute=execute,
        )

    @mcp.tool()
    def remove_keyword(customer_id: str, ad_group_id: str, criterion_id: str) -> dict:
        """Propose permanently removing a keyword from an ad group."""
        client = ctx.client.raw
        operation = client.get_type("AdGroupCriterionOperation")
        operation.remove = client.get_service("AdGroupCriterionService").ad_group_criterion_path(
            customer_id.replace("-", ""), ad_group_id, criterion_id
        )

        description = f"REMOVE keyword {criterion_id} from ad group {ad_group_id}"

        def execute():
            return ctx.client.mutate("AdGroupCriterionService", customer_id, [operation])

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
                criterion.campaign = client.get_service("CampaignService").campaign_path(
                    customer_id.replace("-", ""), campaign_id
                )
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

        description = f"Add {len(keywords)} negative keyword(s) to {scope}: " + ", ".join(
            f"[{k.get('match_type', 'BROAD')}] {k['text']}" for k in keywords
        )

        def execute():
            return ctx.client.mutate(service_name, customer_id, operations)

        return ctx.safety.propose(
            tool_name="add_negative_keywords",
            customer_id=customer_id,
            description=description,
            payload={"campaign_id": campaign_id, "ad_group_id": ad_group_id, "keywords": keywords},
            execute=execute,
        )
