"""Shared negative keyword list tools for Google Ads API v25."""

from __future__ import annotations

from ..context import AppContext

_VALID_MATCH_TYPES = {"BROAD", "PHRASE", "EXACT"}


def register(mcp, ctx: AppContext) -> None:
    @mcp.tool()
    def list_shared_negative_keyword_lists(customer_id: str) -> dict:
        """List shared negative keyword sets and their campaign usage counts."""
        query = """
            SELECT
                shared_set.id,
                shared_set.name,
                shared_set.type,
                shared_set.status,
                shared_set.member_count,
                shared_set.reference_count,
                shared_set.resource_name
            FROM shared_set
            WHERE shared_set.type = NEGATIVE_KEYWORDS
            ORDER BY shared_set.name
        """
        rows = ctx.client.search(customer_id, query)
        return {"shared_negative_keyword_lists": rows, "count": len(rows)}

    @mcp.tool()
    def list_shared_negative_keywords(customer_id: str, shared_set_id: str) -> dict:
        """List keyword criteria inside a shared negative keyword list."""
        query = f"""
            SELECT
                shared_criterion.criterion_id,
                shared_criterion.keyword.text,
                shared_criterion.keyword.match_type,
                shared_criterion.negative,
                shared_criterion.resource_name,
                shared_criterion.shared_set
            FROM shared_criterion
            WHERE shared_criterion.shared_set =
                'customers/{customer_id.replace('-', '')}/sharedSets/{int(shared_set_id)}'
            ORDER BY shared_criterion.keyword.text
        """
        rows = ctx.client.search(customer_id, query)
        return {"keywords": rows, "count": len(rows), "shared_set_id": shared_set_id}

    @mcp.tool()
    def create_shared_negative_keyword_list(customer_id: str, name: str) -> dict:
        """Propose creating an empty shared negative keyword list."""
        if not name.strip():
            raise ValueError("name is required.")
        client = ctx.client.raw
        operation = client.get_type("SharedSetOperation")
        operation.create.name = name.strip()
        operation.create.type_ = client.enums.SharedSetTypeEnum.NEGATIVE_KEYWORDS

        def execute():
            return ctx.client.mutate("SharedSetService", customer_id, [operation])

        return ctx.safety.propose(
            tool_name="create_shared_negative_keyword_list",
            customer_id=customer_id,
            description=f"Create shared negative keyword list '{name.strip()}'",
            payload={"name": name.strip(), "type": "NEGATIVE_KEYWORDS"},
            execute=execute,
        )

    @mcp.tool()
    def add_shared_negative_keywords(
        customer_id: str,
        shared_set_id: str,
        keywords: list[dict],
    ) -> dict:
        """Propose atomically adding keywords to a shared negative keyword list."""
        if not keywords:
            raise ValueError("Provide at least one keyword.")
        if len(keywords) > 10_000:
            raise ValueError("A single call supports at most 10,000 keywords.")

        client = ctx.client.raw
        customer = customer_id.replace("-", "")
        shared_set_resource = client.get_service("SharedSetService").shared_set_path(
            customer, shared_set_id
        )
        operations = []
        normalized_keywords = []
        for item in keywords:
            text = str(item.get("text", "")).strip()
            match_type = str(item.get("match_type", "BROAD")).upper()
            if not text:
                raise ValueError("Every keyword requires non-empty text.")
            if match_type not in _VALID_MATCH_TYPES:
                raise ValueError("match_type must be BROAD, PHRASE, or EXACT.")
            operation = client.get_type("SharedCriterionOperation")
            criterion = operation.create
            criterion.shared_set = shared_set_resource
            criterion.negative = True
            criterion.keyword.text = text
            criterion.keyword.match_type = client.enums.KeywordMatchTypeEnum[match_type].value
            operations.append(operation)
            normalized_keywords.append({"text": text, "match_type": match_type})

        def execute():
            return ctx.client.mutate("SharedCriterionService", customer_id, operations)

        return ctx.safety.propose(
            tool_name="add_shared_negative_keywords",
            customer_id=customer_id,
            description=(
                f"Add {len(operations)} negative keyword(s) to shared set {shared_set_id}"
            ),
            payload={"shared_set_id": shared_set_id, "keywords": normalized_keywords},
            execute=execute,
        )

    @mcp.tool()
    def remove_shared_negative_keyword(
        customer_id: str,
        shared_set_id: str,
        criterion_id: str,
    ) -> dict:
        """Propose permanently removing one keyword from a shared list."""
        client = ctx.client.raw
        operation = client.get_type("SharedCriterionOperation")
        operation.remove = client.get_service("SharedCriterionService").shared_criterion_path(
            customer_id.replace("-", ""), shared_set_id, criterion_id
        )

        def execute():
            return ctx.client.mutate("SharedCriterionService", customer_id, [operation])

        return ctx.safety.propose(
            tool_name="remove_shared_negative_keyword",
            customer_id=customer_id,
            description=(
                f"Remove criterion {criterion_id} from shared negative list {shared_set_id}"
            ),
            payload={"shared_set_id": shared_set_id, "criterion_id": criterion_id},
            execute=execute,
        )

    @mcp.tool()
    def attach_shared_negative_keyword_list_to_campaign(
        customer_id: str,
        campaign_id: str,
        shared_set_id: str,
    ) -> dict:
        """Propose attaching a shared negative keyword list to a campaign."""
        client = ctx.client.raw
        customer = customer_id.replace("-", "")
        operation = client.get_type("CampaignSharedSetOperation")
        relation = operation.create
        relation.campaign = client.get_service("CampaignService").campaign_path(
            customer, campaign_id
        )
        relation.shared_set = client.get_service("SharedSetService").shared_set_path(
            customer, shared_set_id
        )

        def execute():
            return ctx.client.mutate("CampaignSharedSetService", customer_id, [operation])

        return ctx.safety.propose(
            tool_name="attach_shared_negative_keyword_list_to_campaign",
            customer_id=customer_id,
            description=(
                f"Attach shared negative keyword list {shared_set_id} to campaign {campaign_id}"
            ),
            payload={"campaign_id": campaign_id, "shared_set_id": shared_set_id},
            execute=execute,
        )

    @mcp.tool()
    def remove_shared_negative_keyword_list_from_campaign(
        customer_id: str,
        campaign_id: str,
        shared_set_id: str,
    ) -> dict:
        """Propose detaching a shared negative keyword list from a campaign."""
        customer = customer_id.replace("-", "")
        operation = ctx.client.raw.get_type("CampaignSharedSetOperation")
        operation.remove = (
            f"customers/{customer}/campaignSharedSets/{campaign_id}~{shared_set_id}"
        )

        def execute():
            return ctx.client.mutate("CampaignSharedSetService", customer_id, [operation])

        return ctx.safety.propose(
            tool_name="remove_shared_negative_keyword_list_from_campaign",
            customer_id=customer_id,
            description=(
                f"Detach shared negative keyword list {shared_set_id} from campaign {campaign_id}"
            ),
            payload={"campaign_id": campaign_id, "shared_set_id": shared_set_id},
            execute=execute,
        )

    @mcp.tool()
    def remove_shared_negative_keyword_list(customer_id: str, shared_set_id: str) -> dict:
        """Propose permanently removing an entire shared negative keyword list."""
        client = ctx.client.raw
        operation = client.get_type("SharedSetOperation")
        operation.remove = client.get_service("SharedSetService").shared_set_path(
            customer_id.replace("-", ""), shared_set_id
        )

        def execute():
            return ctx.client.mutate("SharedSetService", customer_id, [operation])

        return ctx.safety.propose(
            tool_name="remove_shared_negative_keyword_list",
            customer_id=customer_id,
            description=f"Permanently remove shared negative keyword list {shared_set_id}",
            payload={"shared_set_id": shared_set_id},
            execute=execute,
        )
