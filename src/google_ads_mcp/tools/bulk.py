"""Bulk write operations with all-or-nothing mutation semantics."""

from __future__ import annotations

from google.protobuf import field_mask_pb2

from ..context import AppContext

_VALID_STATUSES = {"ENABLED", "PAUSED", "REMOVED"}
_VALID_MATCH_TYPES = {"BROAD", "PHRASE", "EXACT"}


def register(mcp, ctx: AppContext) -> None:
    @mcp.tool()
    def bulk_update_keyword_status(
        customer_id: str,
        updates: list[dict],
        status: str,
    ) -> dict:
        """Pause, enable, or remove many keywords atomically."""
        _validate_status_batch(updates, status, "ad_group_id", "criterion_id")
        client = ctx.client.raw
        customer_id_clean = customer_id.replace("-", "")
        criterion_service = client.get_service("AdGroupCriterionService")
        operations = []
        for item in updates:
            resource_name = criterion_service.ad_group_criterion_path(
                customer_id_clean, item["ad_group_id"], item["criterion_id"]
            )
            operation = client.get_type("AdGroupCriterionOperation")
            if status == "REMOVED":
                operation.remove = resource_name
            else:
                operation.update.resource_name = resource_name
                operation.update.status = client.enums.AdGroupCriterionStatusEnum[
                    status
                ].value
                operation.update_mask.CopyFrom(
                    field_mask_pb2.FieldMask(paths=["status"])
                )
            operations.append(operation)

        description = f"Atomically set {len(operations)} keyword(s) status -> {status}"

        def execute():
            return ctx.client.mutate(
                "AdGroupCriterionService",
                customer_id,
                operations,
                partial_failure=False,
            )

        return ctx.safety.propose(
            tool_name="bulk_update_keyword_status",
            customer_id=customer_id,
            description=description,
            payload={"updates": updates, "status": status, "atomic": True},
            execute=execute,
        )

    @mcp.tool()
    def bulk_add_negative_keywords_multi_scope(
        customer_id: str,
        campaign_negatives: dict[str, list[dict]] | None = None,
        ad_group_negatives: dict[str, list[dict]] | None = None,
    ) -> dict:
        """Add negatives across campaign/ad-group scopes in one atomic mutate."""
        campaign_negatives = campaign_negatives or {}
        ad_group_negatives = ad_group_negatives or {}
        if not campaign_negatives and not ad_group_negatives:
            raise ValueError(
                "Provide at least one of campaign_negatives or ad_group_negatives."
            )

        client = ctx.client.raw
        customer_id_clean = customer_id.replace("-", "")
        mutate_operations = []
        campaign_count = 0
        ad_group_count = 0

        for campaign_id, keywords in campaign_negatives.items():
            campaign_resource_name = client.get_service(
                "CampaignService"
            ).campaign_path(customer_id_clean, campaign_id)
            for keyword in keywords:
                text, match_type = _validate_negative(keyword)
                operation = client.get_type("CampaignCriterionOperation")
                criterion = operation.create
                criterion.campaign = campaign_resource_name
                criterion.negative = True
                criterion.keyword.text = text
                criterion.keyword.match_type = client.enums.KeywordMatchTypeEnum[
                    match_type
                ].value
                mutate_operations.append(
                    _wrap_mutate(client, "campaign_criterion_operation", operation)
                )
                campaign_count += 1

        for ad_group_id, keywords in ad_group_negatives.items():
            ad_group_resource_name = client.get_service("AdGroupService").ad_group_path(
                customer_id_clean, ad_group_id
            )
            for keyword in keywords:
                text, match_type = _validate_negative(keyword)
                operation = client.get_type("AdGroupCriterionOperation")
                criterion = operation.create
                criterion.ad_group = ad_group_resource_name
                criterion.negative = True
                criterion.keyword.text = text
                criterion.keyword.match_type = client.enums.KeywordMatchTypeEnum[
                    match_type
                ].value
                mutate_operations.append(
                    _wrap_mutate(client, "ad_group_criterion_operation", operation)
                )
                ad_group_count += 1

        if not mutate_operations:
            raise ValueError("The supplied negative keyword collections are empty.")

        description = (
            f"Atomically add {campaign_count} campaign-level and {ad_group_count} "
            "ad-group-level negative keyword(s)"
        )

        def execute():
            return ctx.client.mutate_atomic(customer_id, mutate_operations)

        return ctx.safety.propose(
            tool_name="bulk_add_negative_keywords_multi_scope",
            customer_id=customer_id,
            description=description,
            payload={
                "campaign_negatives": campaign_negatives,
                "ad_group_negatives": ad_group_negatives,
                "atomic": True,
            },
            execute=execute,
        )

    @mcp.tool()
    def bulk_update_ad_status(
        customer_id: str,
        updates: list[dict],
        status: str,
    ) -> dict:
        """Pause, enable, or remove many ads atomically."""
        _validate_status_batch(updates, status, "ad_group_id", "ad_id")
        client = ctx.client.raw
        customer_id_clean = customer_id.replace("-", "")
        ad_service = client.get_service("AdGroupAdService")
        operations = []
        for item in updates:
            resource_name = ad_service.ad_group_ad_path(
                customer_id_clean, item["ad_group_id"], item["ad_id"]
            )
            operation = client.get_type("AdGroupAdOperation")
            if status == "REMOVED":
                operation.remove = resource_name
            else:
                operation.update.resource_name = resource_name
                operation.update.status = client.enums.AdGroupAdStatusEnum[status].value
                operation.update_mask.CopyFrom(
                    field_mask_pb2.FieldMask(paths=["status"])
                )
            operations.append(operation)

        description = f"Atomically set {len(operations)} ad(s) status -> {status}"

        def execute():
            return ctx.client.mutate(
                "AdGroupAdService",
                customer_id,
                operations,
                partial_failure=False,
            )

        return ctx.safety.propose(
            tool_name="bulk_update_ad_status",
            customer_id=customer_id,
            description=description,
            payload={"updates": updates, "status": status, "atomic": True},
            execute=execute,
        )

    @mcp.tool()
    def bulk_update_campaign_status(
        customer_id: str,
        campaign_ids: list[str],
        status: str,
    ) -> dict:
        """Pause, enable, or remove many campaigns atomically."""
        if not campaign_ids:
            raise ValueError("Provide at least one campaign_id.")
        if status not in _VALID_STATUSES:
            raise ValueError("status must be ENABLED, PAUSED, or REMOVED.")
        if any(not str(campaign_id).strip() for campaign_id in campaign_ids):
            raise ValueError("campaign_ids must not contain empty values.")

        client = ctx.client.raw
        customer_id_clean = customer_id.replace("-", "")
        campaign_service = client.get_service("CampaignService")
        operations = []
        for campaign_id in campaign_ids:
            resource_name = campaign_service.campaign_path(
                customer_id_clean, str(campaign_id)
            )
            operation = client.get_type("CampaignOperation")
            if status == "REMOVED":
                operation.remove = resource_name
            else:
                operation.update.resource_name = resource_name
                operation.update.status = client.enums.CampaignStatusEnum[status].value
                operation.update_mask.CopyFrom(
                    field_mask_pb2.FieldMask(paths=["status"])
                )
            operations.append(operation)

        description = f"Atomically set {len(operations)} campaign(s) status -> {status}"

        def execute():
            return ctx.client.mutate(
                "CampaignService",
                customer_id,
                operations,
                partial_failure=False,
            )

        return ctx.safety.propose(
            tool_name="bulk_update_campaign_status",
            customer_id=customer_id,
            description=description,
            payload={"campaign_ids": campaign_ids, "status": status, "atomic": True},
            execute=execute,
        )


def _validate_status_batch(updates: list[dict], status: str, *required_keys: str) -> None:
    if not updates:
        raise ValueError("Provide at least one update entry.")
    if status not in _VALID_STATUSES:
        raise ValueError("status must be ENABLED, PAUSED, or REMOVED.")
    for index, item in enumerate(updates):
        if not isinstance(item, dict):
            raise TypeError(f"updates[{index}] must be an object.")
        for key in required_keys:
            if not str(item.get(key, "")).strip():
                raise ValueError(f"updates[{index}] is missing non-empty {key!r}.")


def _validate_negative(keyword: dict) -> tuple[str, str]:
    if not isinstance(keyword, dict):
        raise TypeError("Each negative keyword must be an object.")
    text = str(keyword.get("text", "")).strip()
    if not text:
        raise ValueError("Negative keyword text must not be empty.")
    match_type = str(keyword.get("match_type", "BROAD")).upper()
    if match_type not in _VALID_MATCH_TYPES:
        raise ValueError("Negative keyword match_type must be BROAD, PHRASE, or EXACT.")
    return text, match_type


def _wrap_mutate(client, field_name: str, operation):
    mutate_operation = client.get_type("MutateOperation")
    client.copy_from(getattr(mutate_operation, field_name), operation)
    return mutate_operation
