"""Controlled Google Ads API v25 Batch Job tools.

The MCP intentionally does not expose arbitrary raw MutateOperation protobufs.
Instead, callers submit a small JSON DSL covering the most common agency-scale
mutations. The whole submission is confirmation-gated as a high-risk action so
an operator can review the complete manifest before the asynchronous job starts.
"""

from __future__ import annotations

import json
from collections import Counter
from typing import Any

import proto
from google.ads.googleads.errors import GoogleAdsException
from google.protobuf.field_mask_pb2 import FieldMask

from ..context import AppContext
from ..errors import GoogleAdsMcpError, format_google_ads_exception

_MAX_OPERATIONS_PER_SUBMISSION = 10_000
_MAX_MANIFEST_BYTES = 20 * 1024 * 1024
_ALLOWED_STATUS = {"ENABLED", "PAUSED", "REMOVED"}
_ALLOWED_MATCH_TYPES = {"BROAD", "PHRASE", "EXACT"}
_SUPPORTED_KINDS = {
    "campaign_status",
    "ad_group_status",
    "ad_status",
    "keyword_status",
    "campaign_budget_amount",
    "keyword_bid",
    "add_campaign_negative_keyword",
}


def _required(spec: dict[str, Any], key: str) -> Any:
    value = spec.get(key)
    if value is None or (isinstance(value, str) and not value.strip()):
        raise ValueError(f"Batch operation requires '{key}'.")
    return value


def _positive_int(value: Any, key: str) -> str:
    text = str(value).strip()
    if not text.isdigit() or int(text) <= 0:
        raise ValueError(f"{key} must be a positive integer ID.")
    return text


def _status(raw, value: Any, enum_name: str):
    name = str(value).strip().upper()
    if name not in _ALLOWED_STATUS:
        raise ValueError(f"status must be one of {sorted(_ALLOWED_STATUS)}.")
    return getattr(getattr(raw.enums, enum_name), name)


def _build_batch_mutate(raw, customer_id: str, spec: dict[str, Any]):
    if not isinstance(spec, dict):
        raise TypeError("Each batch operation must be an object/dict.")
    kind = str(spec.get("kind", "")).strip().lower()
    if kind not in _SUPPORTED_KINDS:
        raise ValueError(
            f"Unsupported batch operation kind '{kind}'. Supported kinds: "
            + ", ".join(sorted(_SUPPORTED_KINDS))
        )

    mutate = raw.get_type("MutateOperation")

    if kind == "campaign_status":
        campaign_id = _positive_int(_required(spec, "campaign_id"), "campaign_id")
        op = mutate.campaign_operation
        op.update.resource_name = f"customers/{customer_id}/campaigns/{campaign_id}"
        op.update.status = _status(raw, _required(spec, "status"), "CampaignStatusEnum")
        op.update_mask = FieldMask(paths=["status"])
        return mutate

    if kind == "ad_group_status":
        ad_group_id = _positive_int(_required(spec, "ad_group_id"), "ad_group_id")
        op = mutate.ad_group_operation
        op.update.resource_name = f"customers/{customer_id}/adGroups/{ad_group_id}"
        op.update.status = _status(raw, _required(spec, "status"), "AdGroupStatusEnum")
        op.update_mask = FieldMask(paths=["status"])
        return mutate

    if kind == "ad_status":
        ad_group_id = _positive_int(_required(spec, "ad_group_id"), "ad_group_id")
        ad_id = _positive_int(_required(spec, "ad_id"), "ad_id")
        op = mutate.ad_group_ad_operation
        op.update.resource_name = (
            f"customers/{customer_id}/adGroupAds/{ad_group_id}~{ad_id}"
        )
        op.update.status = _status(raw, _required(spec, "status"), "AdGroupAdStatusEnum")
        op.update_mask = FieldMask(paths=["status"])
        return mutate

    if kind == "keyword_status":
        ad_group_id = _positive_int(_required(spec, "ad_group_id"), "ad_group_id")
        criterion_id = _positive_int(_required(spec, "criterion_id"), "criterion_id")
        op = mutate.ad_group_criterion_operation
        op.update.resource_name = (
            f"customers/{customer_id}/adGroupCriteria/{ad_group_id}~{criterion_id}"
        )
        status_name = str(_required(spec, "status")).strip().upper()
        if status_name not in _ALLOWED_STATUS:
            raise ValueError(f"status must be one of {sorted(_ALLOWED_STATUS)}.")
        if status_name == "REMOVED":
            op.remove = op.update.resource_name
            return mutate
        op.update.status = getattr(raw.enums.AdGroupCriterionStatusEnum, status_name)
        op.update_mask = FieldMask(paths=["status"])
        return mutate

    if kind == "campaign_budget_amount":
        budget_id = _positive_int(
            _required(spec, "campaign_budget_id"), "campaign_budget_id"
        )
        amount = float(_required(spec, "amount"))
        if amount <= 0:
            raise ValueError("amount must be greater than zero.")
        op = mutate.campaign_budget_operation
        op.update.resource_name = (
            f"customers/{customer_id}/campaignBudgets/{budget_id}"
        )
        op.update.amount_micros = round(amount * 1_000_000)
        op.update_mask = FieldMask(paths=["amount_micros"])
        return mutate

    if kind == "keyword_bid":
        ad_group_id = _positive_int(_required(spec, "ad_group_id"), "ad_group_id")
        criterion_id = _positive_int(_required(spec, "criterion_id"), "criterion_id")
        cpc_bid = float(_required(spec, "cpc_bid"))
        if cpc_bid <= 0:
            raise ValueError("cpc_bid must be greater than zero.")
        op = mutate.ad_group_criterion_operation
        op.update.resource_name = (
            f"customers/{customer_id}/adGroupCriteria/{ad_group_id}~{criterion_id}"
        )
        op.update.cpc_bid_micros = round(cpc_bid * 1_000_000)
        op.update_mask = FieldMask(paths=["cpc_bid_micros"])
        return mutate

    campaign_id = _positive_int(_required(spec, "campaign_id"), "campaign_id")
    text = str(_required(spec, "text")).strip()
    if len(text) > 80:
        raise ValueError("Negative keyword text must be 80 characters or fewer.")
    match_type = str(spec.get("match_type", "BROAD")).strip().upper()
    if match_type not in _ALLOWED_MATCH_TYPES:
        raise ValueError(
            f"match_type must be one of {sorted(_ALLOWED_MATCH_TYPES)}."
        )
    op = mutate.campaign_criterion_operation
    op.create.campaign = f"customers/{customer_id}/campaigns/{campaign_id}"
    op.create.negative = True
    op.create.keyword.text = text
    op.create.keyword.match_type = getattr(raw.enums.KeywordMatchTypeEnum, match_type)
    return mutate


def _operation_name(lro: Any) -> str | None:
    operation = getattr(lro, "operation", None)
    if operation is not None:
        name = getattr(operation, "name", None)
        if name:
            return str(name)
    name = getattr(lro, "name", None)
    return str(name) if name else None


def register(mcp, ctx: AppContext) -> None:
    @mcp.tool()
    def list_batch_jobs(
        customer_id: str,
        status_filter: str | None = None,
        limit: int = 100,
    ) -> dict:
        """List recent Google Ads batch jobs and their execution metadata."""
        if limit < 1 or limit > 500:
            raise ValueError("limit must be between 1 and 500.")
        where = ""
        if status_filter:
            status = status_filter.strip().upper()
            allowed = {"PENDING", "RUNNING", "DONE", "CANCELED"}
            if status not in allowed:
                raise ValueError(f"status_filter must be one of {sorted(allowed)}.")
            where = f"WHERE batch_job.status = '{status}'"
        rows = ctx.client.search(
            customer_id,
            f"""
            SELECT
                batch_job.id,
                batch_job.resource_name,
                batch_job.status,
                batch_job.long_running_operation,
                batch_job.metadata.creation_date_time,
                batch_job.metadata.start_date_time,
                batch_job.metadata.completion_date_time,
                batch_job.metadata.estimated_completion_ratio,
                batch_job.metadata.operation_count,
                batch_job.metadata.executed_operation_count
            FROM batch_job
            {where}
            ORDER BY batch_job.id DESC
            LIMIT {limit}
            """,
        )
        return {"batch_jobs": rows, "count": len(rows)}

    @mcp.tool()
    def submit_batch_job(customer_id: str, operations: list[dict]) -> dict:
        """Propose and submit a controlled mixed-resource batch job.

        Supported operation kinds:
        campaign_status, ad_group_status, ad_status, keyword_status,
        campaign_budget_amount, keyword_bid, add_campaign_negative_keyword.

        The complete manifest is confirmation-gated. Google Batch Jobs use
        partial-success semantics internally, so successful rows are not rolled
        back when another row fails; inspect results with get_batch_job_results.
        """
        if not operations:
            raise ValueError("operations must contain at least one operation.")
        if len(operations) > _MAX_OPERATIONS_PER_SUBMISSION:
            raise ValueError(
                f"A single MCP batch submission supports at most "
                f"{_MAX_OPERATIONS_PER_SUBMISSION} operations."
            )
        encoded = json.dumps(operations, sort_keys=True, separators=(",", ":")).encode()
        if len(encoded) > _MAX_MANIFEST_BYTES:
            raise ValueError("Batch manifest is too large; split it into smaller jobs.")

        customer = ctx.client.assert_customer_allowed(customer_id)
        mutate_operations = [
            _build_batch_mutate(ctx.client.raw, customer, spec) for spec in operations
        ]
        summary = dict(Counter(str(spec["kind"]).strip().lower() for spec in operations))

        def execute():
            service = ctx.client.service("BatchJobService")
            create_operation = ctx.client.raw.get_type("BatchJobOperation")
            batch_job = ctx.client.raw.get_type("BatchJob")
            ctx.client.raw.copy_from(create_operation.create, batch_job)
            try:
                created = service.mutate_batch_job(
                    customer_id=customer,
                    operation=create_operation,
                )
                resource_name = created.result.resource_name
                added = service.add_batch_job_operations(
                    resource_name=resource_name,
                    mutate_operations=mutate_operations,
                )
                lro = service.run_batch_job(resource_name=resource_name)
            except GoogleAdsException as ex:
                raise GoogleAdsMcpError(format_google_ads_exception(ex)) from ex
            return {
                "resource_name": resource_name,
                "operation_count": len(mutate_operations),
                "next_sequence_token": getattr(added, "next_sequence_token", None),
                "long_running_operation": _operation_name(lro),
                "status": "submitted",
            }

        return ctx.safety.propose(
            tool_name="submit_batch_job",
            customer_id=customer,
            description=(
                f"Create and run one Google Ads batch job with {len(operations)} "
                f"mixed-resource operations"
            ),
            payload={
                "operation_count": len(operations),
                "operation_summary": summary,
                "operations": operations,
            },
            execute=execute,
        )

    @mcp.tool()
    def get_batch_job_results(
        customer_id: str,
        batch_job_resource_name: str,
        page_size: int = 1000,
        page_token: str | None = None,
        return_mutable_resource: bool = False,
    ) -> dict:
        """Read one page of results for a completed batch job."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        prefix = f"customers/{customer}/batchJobs/"
        if not batch_job_resource_name.startswith(prefix):
            raise ValueError(
                "batch_job_resource_name must belong to the supplied customer_id."
            )
        if page_size < 1 or page_size > 1000:
            raise ValueError("page_size must be between 1 and 1000.")
        response_type = (
            ctx.client.raw.enums.ResponseContentTypeEnum.MUTABLE_RESOURCE
            if return_mutable_resource
            else ctx.client.raw.enums.ResponseContentTypeEnum.RESOURCE_NAME_ONLY
        )
        service = ctx.client.service("BatchJobService")
        kwargs: dict[str, Any] = {
            "resource_name": batch_job_resource_name,
            "page_size": page_size,
            "response_content_type": response_type,
        }
        if page_token:
            kwargs["page_token"] = page_token
        try:
            pager = service.list_batch_job_results(**kwargs)
        except GoogleAdsException as ex:
            raise GoogleAdsMcpError(format_google_ads_exception(ex)) from ex

        page = None
        pages = getattr(pager, "pages", None)
        if pages is not None:
            page = next(iter(pages), None)
        if page is None:
            page = getattr(pager, "_response", pager)
        raw_results = getattr(page, "results", None)
        if raw_results is None:
            raw_results = list(pager)
        results = [
            proto.Message.to_dict(item, preserving_proto_field_name=True)
            for item in raw_results
        ]
        return {
            "batch_job_resource_name": batch_job_resource_name,
            "results": results,
            "count": len(results),
            "next_page_token": getattr(page, "next_page_token", None) or None,
        }
