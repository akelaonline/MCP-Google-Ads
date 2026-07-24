"""Bulk operations: batch several mutations of the same kind into a single
Google Ads API call instead of one round-trip per item.

`add_keywords` / `add_negative_keywords` (keywords.py) already batch when
you pass a list — this module targets the gap that's left: bulk *status
changes* (pause/enable/remove) across many existing keywords or ads at once,
including across different ad groups in the same request.
"""

from __future__ import annotations

from google.protobuf import field_mask_pb2

from ..context import AppContext


def register(mcp, ctx: AppContext) -> None:
    @mcp.tool()
    def bulk_update_keyword_status(
        customer_id: str,
        updates: list[dict],
        status: str,
    ) -> dict:
        """Propose pausing, enabling, or removing many keywords in one call.

        Args:
            updates: list of {"ad_group_id": "...", "criterion_id": "..."}.
                Can span multiple ad groups in the same campaign or account.
            status: ENABLED, PAUSED, or REMOVED — applied to every keyword in
                `updates`. To apply different statuses to different keywords,
                call this tool once per status group.
        """
        if not updates:
            raise ValueError("Provide at least one {ad_group_id, criterion_id} entry.")

        client = ctx.client.raw
        customer_id_clean = customer_id.replace("-", "")
        criterion_service = client.get_service("AdGroupCriterionService")

        operations = []
        for item in updates:
            operation = client.get_type("AdGroupCriterionOperation")
            resource_name = criterion_service.ad_group_criterion_path(
                customer_id_clean, item["ad_group_id"], item["criterion_id"]
            )
            operation.update.resource_name = resource_name
            operation.update.status = client.enums.AdGroupCriterionStatusEnum[status].value
            operation.update_mask.CopyFrom(field_mask_pb2.FieldMask(paths=["status"]))
            operations.append(operation)

        description = f"Set {len(operations)} keyword(s) status -> {status}"

        def execute():
            return ctx.client.mutate(
                "AdGroupCriterionService", customer_id, operations, partial_failure=True
            )

        return ctx.safety.propose(
            tool_name="bulk_update_keyword_status",
            customer_id=customer_id,
            description=description,
            payload={"updates": updates, "status": status},
            execute=execute,
        )

    @mcp.tool()
    def bulk_add_negative_keywords_multi_scope(
        customer_id: str,
        campaign_negatives: dict[str, list[dict]] | None = None,
        ad_group_negatives: dict[str, list[dict]] | None = None,
    ) -> dict:
        """Propose adding negative keywords across multiple campaigns and/or
        ad groups in a single call — e.g. rolling the same "cursos gratuitos"
        negative list out to every active campaign in one shot instead of
        calling add_negative_keywords once per campaign.

        Args:
            campaign_negatives: {"<campaign_id>": [{"text": "...", "match_type": "PHRASE"}, ...]}
            ad_group_negatives: {"<ad_group_id>": [{"text": "...", "match_type": "PHRASE"}, ...]}
        """
        campaign_negatives = campaign_negatives or {}
        ad_group_negatives = ad_group_negatives or {}
        if not campaign_negatives and not ad_group_negatives:
            raise ValueError("Provide at least one of campaign_negatives or ad_group_negatives.")

        client = ctx.client.raw
        customer_id_clean = customer_id.replace("-", "")

        campaign_ops = []
        for campaign_id, keywords in campaign_negatives.items():
            campaign_resource_name = client.get_service("CampaignService").campaign_path(
                customer_id_clean, campaign_id
            )
            for kw in keywords:
                operation = client.get_type("CampaignCriterionOperation")
                criterion = operation.create
                criterion.campaign = campaign_resource_name
                criterion.negative = True
                criterion.keyword.text = kw["text"]
                criterion.keyword.match_type = client.enums.KeywordMatchTypeEnum[
                    kw.get("match_type", "BROAD")
                ].value
                campaign_ops.append(operation)

        ad_group_ops = []
        for ad_group_id, keywords in ad_group_negatives.items():
            ad_group_resource_name = client.get_service("AdGroupService").ad_group_path(
                customer_id_clean, ad_group_id
            )
            for kw in keywords:
                operation = client.get_type("AdGroupCriterionOperation")
                criterion = operation.create
                criterion.ad_group = ad_group_resource_name
                criterion.negative = True
                criterion.keyword.text = kw["text"]
                criterion.keyword.match_type = client.enums.KeywordMatchTypeEnum[
                    kw.get("match_type", "BROAD")
                ].value
                ad_group_ops.append(operation)

        total = len(campaign_ops) + len(ad_group_ops)
        description = (
            f"Add {len(campaign_ops)} campaign-level and {len(ad_group_ops)} ad-group-level "
            f"negative keyword(s) across {len(campaign_negatives)} campaign(s) and "
            f"{len(ad_group_negatives)} ad group(s) ({total} total)"
        )

        def execute():
            results = {}
            if campaign_ops:
                results["campaign_criteria"] = ctx.client.mutate(
                    "CampaignCriterionService", customer_id, campaign_ops, partial_failure=True
                )
            if ad_group_ops:
                results["ad_group_criteria"] = ctx.client.mutate(
                    "AdGroupCriterionService", customer_id, ad_group_ops, partial_failure=True
                )
            return {
                "campaign_resource_names": [
                    r.resource_name for r in results["campaign_criteria"].results
                ]
                if "campaign_criteria" in results
                else [],
                "ad_group_resource_names": [
                    r.resource_name for r in results["ad_group_criteria"].results
                ]
                if "ad_group_criteria" in results
                else [],
            }

        return ctx.safety.propose(
            tool_name="bulk_add_negative_keywords_multi_scope",
            customer_id=customer_id,
            description=description,
            payload={
                "campaign_negatives": campaign_negatives,
                "ad_group_negatives": ad_group_negatives,
            },
            execute=execute,
        )

    @mcp.tool()
    def bulk_update_ad_status(customer_id: str, updates: list[dict], status: str) -> dict:
        """Propose pausing, enabling, or removing many ads in one call.

        Args:
            updates: list of {"ad_group_id": "...", "ad_id": "..."}.
            status: ENABLED, PAUSED, or REMOVED.
        """
        if not updates:
            raise ValueError("Provide at least one {ad_group_id, ad_id} entry.")

        client = ctx.client.raw
        customer_id_clean = customer_id.replace("-", "")
        ad_service = client.get_service("AdGroupAdService")

        operations = []
        for item in updates:
            operation = client.get_type("AdGroupAdOperation")
            resource_name = ad_service.ad_group_ad_path(
                customer_id_clean, item["ad_group_id"], item["ad_id"]
            )
            operation.update.resource_name = resource_name
            operation.update.status = client.enums.AdGroupAdStatusEnum[status].value
            operation.update_mask.CopyFrom(field_mask_pb2.FieldMask(paths=["status"]))
            operations.append(operation)

        description = f"Set {len(operations)} ad(s) status -> {status}"

        def execute():
            return ctx.client.mutate(
                "AdGroupAdService", customer_id, operations, partial_failure=True
            )

        return ctx.safety.propose(
            tool_name="bulk_update_ad_status",
            customer_id=customer_id,
            description=description,
            payload={"updates": updates, "status": status},
            execute=execute,
        )
