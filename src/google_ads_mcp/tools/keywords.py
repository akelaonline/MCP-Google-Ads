"""Keyword and negative-keyword tools."""

from __future__ import annotations

from google.protobuf import field_mask_pb2

from ..client import micros
from ..context import AppContext

_VALID_MATCH_TYPES = {"EXACT", "PHRASE", "BROAD"}


def register(mcp, ctx: AppContext) -> None:
    @mcp.tool()
    def add_keywords(
        customer_id: str,
        ad_group_id: str,
        keywords: list[dict],
        cpc_bid: float | None = None,
    ) -> dict:
        """Propose adding one or more keywords to an ad group."""
        normalized = _normalize_keywords(keywords)
        if cpc_bid is not None and cpc_bid <= 0:
            raise ValueError("cpc_bid must be greater than 0.")

        client = ctx.client.raw
        operations = []
        for keyword in normalized:
            operation = client.get_type("AdGroupCriterionOperation")
            criterion = operation.create
            criterion.ad_group = client.get_service("AdGroupService").ad_group_path(
                customer_id.replace("-", ""), ad_group_id
            )
            criterion.status = client.enums.AdGroupCriterionStatusEnum.ENABLED.value
            criterion.keyword.text = keyword["text"]
            criterion.keyword.match_type = client.enums.KeywordMatchTypeEnum[
                keyword["match_type"]
            ].value
            if cpc_bid is not None:
                criterion.cpc_bid_micros = micros(cpc_bid)
            operations.append(operation)

        description = (
            f"Add {len(normalized)} keyword(s) to ad group {ad_group_id}: "
            + ", ".join(
                f"[{keyword['match_type']}] {keyword['text']}" for keyword in normalized
            )
        )

        def execute():
            return ctx.client.mutate(
                "AdGroupCriterionService", customer_id, operations, partial_failure=False
            )

        return ctx.safety.propose(
            tool_name="add_keywords",
            customer_id=customer_id,
            description=description,
            payload={
                "ad_group_id": ad_group_id,
                "keywords": normalized,
                "cpc_bid": cpc_bid,
            },
            execute=execute,
        )

    @mcp.tool()
    def update_keyword_status(
        customer_id: str,
        ad_group_id: str,
        criterion_id: str,
        status: str,
    ) -> dict:
        """Propose pausing, enabling, or removing a keyword."""
        if status not in {"ENABLED", "PAUSED", "REMOVED"}:
            raise ValueError("status must be ENABLED, PAUSED, or REMOVED.")

        client = ctx.client.raw
        operation = client.get_type("AdGroupCriterionOperation")
        resource_name = client.get_service(
            "AdGroupCriterionService"
        ).ad_group_criterion_path(
            customer_id.replace("-", ""), ad_group_id, criterion_id
        )
        if status == "REMOVED":
            operation.remove = resource_name
        else:
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
        customer_id: str,
        ad_group_id: str,
        criterion_id: str,
        cpc_bid: float,
    ) -> dict:
        """Propose changing an existing keyword's max CPC bid."""
        if cpc_bid <= 0:
            raise ValueError("cpc_bid must be greater than 0.")
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
        customer_id: str,
        ad_group_id: str,
        criterion_id: str,
        match_type: str,
    ) -> dict:
        """Recreate a keyword with a new immutable match type atomically."""
        match_type = match_type.upper()
        if match_type not in _VALID_MATCH_TYPES:
            raise ValueError("match_type must be EXACT, PHRASE, or BROAD.")

        client = ctx.client.raw
        customer_id_clean = customer_id.replace("-", "")
        query = f"""
            SELECT ad_group_criterion.keyword.text,
                   ad_group_criterion.keyword.match_type,
                   ad_group_criterion.cpc_bid_micros
            FROM ad_group_criterion
            WHERE ad_group_criterion.criterion_id = {int(criterion_id)}
              AND ad_group.id = {int(ad_group_id)}
            LIMIT 1
        """
        rows = ctx.client.search(customer_id, query)
        if not rows:
            raise ValueError(
                f"No keyword found with criterion_id={criterion_id} in ad group "
                f"{ad_group_id}."
            )
        existing = rows[0]["ad_group_criterion"]
        existing_text = existing["keyword"]["text"]
        existing_match_type = existing["keyword"].get("match_type")
        existing_cpc_micros = existing.get("cpc_bid_micros")
        if existing_match_type == match_type:
            raise ValueError(
                f"Keyword {criterion_id} already uses match type {match_type}."
            )

        add_operation = client.get_type("AdGroupCriterionOperation")
        new_criterion = add_operation.create
        new_criterion.ad_group = client.get_service("AdGroupService").ad_group_path(
            customer_id_clean, ad_group_id
        )
        new_criterion.status = client.enums.AdGroupCriterionStatusEnum.ENABLED.value
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

        description = (
            f"Change keyword '{existing_text}' (criterion {criterion_id}, ad group "
            f"{ad_group_id}) match type -> {match_type} (atomic recreate)"
        )

        def execute():
            return ctx.client.mutate(
                "AdGroupCriterionService",
                customer_id,
                [add_operation, remove_operation],
                partial_failure=False,
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
        """Propose adding negative keywords at campaign or ad-group level."""
        if bool(campaign_id) == bool(ad_group_id):
            raise ValueError("Provide exactly one of campaign_id or ad_group_id.")
        normalized = _normalize_keywords(keywords)

        client = ctx.client.raw
        operations = []
        if campaign_id:
            service_name = "CampaignCriterionService"
            campaign_resource = client.get_service("CampaignService").campaign_path(
                customer_id.replace("-", ""), campaign_id
            )
            for keyword in normalized:
                operation = client.get_type("CampaignCriterionOperation")
                criterion = operation.create
                criterion.campaign = campaign_resource
                criterion.negative = True
                criterion.keyword.text = keyword["text"]
                criterion.keyword.match_type = client.enums.KeywordMatchTypeEnum[
                    keyword["match_type"]
                ].value
                operations.append(operation)
            scope = f"campaign {campaign_id}"
        else:
            service_name = "AdGroupCriterionService"
            ad_group_resource = client.get_service("AdGroupService").ad_group_path(
                customer_id.replace("-", ""), ad_group_id
            )
            for keyword in normalized:
                operation = client.get_type("AdGroupCriterionOperation")
                criterion = operation.create
                criterion.ad_group = ad_group_resource
                criterion.negative = True
                criterion.keyword.text = keyword["text"]
                criterion.keyword.match_type = client.enums.KeywordMatchTypeEnum[
                    keyword["match_type"]
                ].value
                operations.append(operation)
            scope = f"ad group {ad_group_id}"

        description = (
            f"Add {len(normalized)} negative keyword(s) to {scope}: "
            + ", ".join(
                f"[{keyword['match_type']}] {keyword['text']}"
                for keyword in normalized
            )
        )

        def execute():
            return ctx.client.mutate(
                service_name,
                customer_id,
                operations,
                partial_failure=False,
            )

        return ctx.safety.propose(
            tool_name="add_negative_keywords",
            customer_id=customer_id,
            description=description,
            payload={
                "campaign_id": campaign_id,
                "ad_group_id": ad_group_id,
                "keywords": normalized,
            },
            execute=execute,
        )


def _normalize_keywords(keywords: list[dict]) -> list[dict[str, str]]:
    if not keywords:
        raise ValueError("Provide at least one keyword.")
    normalized = []
    for index, keyword in enumerate(keywords):
        if not isinstance(keyword, dict):
            raise ValueError(f"keywords[{index}] must be an object.")
        text = str(keyword.get("text", "")).strip()
        if not text:
            raise ValueError(f"keywords[{index}].text must not be empty.")
        match_type = str(keyword.get("match_type", "BROAD")).upper()
        if match_type not in _VALID_MATCH_TYPES:
            raise ValueError(
                f"keywords[{index}].match_type must be EXACT, PHRASE, or BROAD."
            )
        normalized.append({"text": text, "match_type": match_type})
    return normalized
