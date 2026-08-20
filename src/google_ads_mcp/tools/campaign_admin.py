"""Campaign administration gaps for Google Ads API v25.

Covers CampaignGroup, CampaignDraft lifecycle, and explicit removal of Google
automatically-created assets at campaign or ad level.
"""

from __future__ import annotations

import proto
from google.protobuf import field_mask_pb2

from ..context import AppContext
from ..errors import GoogleAdsMcpError, format_google_ads_exception


def _id(value: str, field_name: str) -> str:
    text = str(value).strip()
    if not text.isdigit() or int(text) <= 0:
        raise ValueError(f"{field_name} must be a positive numeric ID.")
    return text


def _owned(ctx: AppContext, customer: str, resource: str, field_name: str) -> str:
    return ctx.client.assert_resource_name_customer(customer, resource, field_name=field_name)


def _call(service, method_name: str, **kwargs):
    from google.ads.googleads.errors import GoogleAdsException

    try:
        return getattr(service, method_name)(**kwargs)
    except GoogleAdsException as ex:
        raise GoogleAdsMcpError(format_google_ads_exception(ex)) from ex


def register(mcp, ctx: AppContext) -> None:
    @mcp.tool()
    def list_campaign_groups(customer_id: str) -> dict:
        """List campaign groups."""
        rows = ctx.client.search(
            customer_id,
            """
            SELECT campaign_group.resource_name,
                   campaign_group.id,
                   campaign_group.name,
                   campaign_group.status
            FROM campaign_group
            ORDER BY campaign_group.name
            """,
        )
        return {"campaign_groups": rows, "count": len(rows)}

    @mcp.tool()
    def create_campaign_group(
        customer_id: str,
        name: str,
        status: str = "ENABLED",
        validate_only: bool = False,
    ) -> dict:
        """Propose creating a campaign group."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        clean_name = str(name).strip()
        if not clean_name or any(ch in clean_name for ch in ("\x00", "\n", "\r")):
            raise ValueError("name must be non-empty and cannot contain NUL/newline characters.")
        clean_status = status.strip().upper()
        if clean_status not in {"ENABLED", "PAUSED"}:
            raise ValueError("status must be ENABLED or PAUSED.")
        raw = ctx.client.raw
        operation = raw.get_type("CampaignGroupOperation")
        operation.create.name = clean_name
        operation.create.status = getattr(raw.enums.CampaignGroupStatusEnum, clean_status)

        def execute():
            return ctx.client.mutate(
                "CampaignGroupService", customer, [operation], validate_only=validate_only
            )

        return ctx.safety.propose(
            tool_name="create_campaign_group",
            customer_id=customer,
            description=f"Create campaign group '{clean_name}' ({clean_status})",
            payload={"name": clean_name, "status": clean_status, "validate_only": validate_only},
            execute=execute,
        )

    @mcp.tool()
    def update_campaign_group(
        customer_id: str,
        campaign_group_resource_name: str,
        name: str | None = None,
        status: str | None = None,
        validate_only: bool = False,
    ) -> dict:
        """Propose renaming or enabling/pausing a campaign group."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        resource = _owned(ctx, customer, campaign_group_resource_name, "campaign_group_resource_name")
        raw = ctx.client.raw
        operation = raw.get_type("CampaignGroupOperation")
        group = operation.update
        group.resource_name = resource
        paths: list[str] = []
        clean_status = None
        if name is not None:
            clean_name = str(name).strip()
            if not clean_name or any(ch in clean_name for ch in ("\x00", "\n", "\r")):
                raise ValueError("name must be non-empty and cannot contain NUL/newline characters.")
            group.name = clean_name
            paths.append("name")
        if status is not None:
            clean_status = status.strip().upper()
            if clean_status not in {"ENABLED", "PAUSED"}:
                raise ValueError("status must be ENABLED or PAUSED.")
            group.status = getattr(raw.enums.CampaignGroupStatusEnum, clean_status)
            paths.append("status")
        if not paths:
            raise ValueError("Provide name and/or status to update.")
        operation.update_mask.CopyFrom(field_mask_pb2.FieldMask(paths=paths))

        def execute():
            return ctx.client.mutate(
                "CampaignGroupService", customer, [operation], validate_only=validate_only
            )

        return ctx.safety.propose(
            tool_name="update_campaign_group",
            customer_id=customer,
            description=f"Update campaign group {resource}: {', '.join(paths)}",
            payload={"campaign_group_resource_name": resource, "fields": paths, "status": clean_status, "validate_only": validate_only},
            execute=execute,
        )

    @mcp.tool()
    def remove_campaign_group(
        customer_id: str,
        campaign_group_resource_name: str,
        validate_only: bool = False,
    ) -> dict:
        """Propose permanently removing a campaign group."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        resource = _owned(ctx, customer, campaign_group_resource_name, "campaign_group_resource_name")
        operation = ctx.client.raw.get_type("CampaignGroupOperation")
        operation.remove = resource

        def execute():
            return ctx.client.mutate(
                "CampaignGroupService", customer, [operation], validate_only=validate_only
            )

        return ctx.safety.propose(
            tool_name="remove_campaign_group",
            customer_id=customer,
            description=f"Remove campaign group {resource}",
            payload={"campaign_group_resource_name": resource, "validate_only": validate_only},
            execute=execute,
        )

    @mcp.tool()
    def list_campaign_drafts(customer_id: str, base_campaign_id: str | None = None) -> dict:
        """List campaign drafts and their generated draft campaigns."""
        where = ""
        if base_campaign_id is not None:
            campaign_id = _id(base_campaign_id, "base_campaign_id")
            where = f"WHERE campaign.id = {campaign_id}"
        rows = ctx.client.search(
            customer_id,
            f"""
            SELECT campaign_draft.resource_name,
                   campaign_draft.draft_id,
                   campaign_draft.name,
                   campaign_draft.status,
                   campaign_draft.base_campaign,
                   campaign_draft.draft_campaign,
                   campaign_draft.has_experiment_running,
                   campaign_draft.long_running_operation
            FROM campaign_draft
            {where}
            ORDER BY campaign_draft.draft_id DESC
            """,
        )
        return {"campaign_drafts": rows, "count": len(rows)}

    @mcp.tool()
    def create_campaign_draft(
        customer_id: str,
        base_campaign_id: str,
        name: str,
        validate_only: bool = False,
    ) -> dict:
        """Propose creating a draft staging campaign from a base campaign."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        campaign_id = _id(base_campaign_id, "base_campaign_id")
        clean_name = str(name).strip()
        if not clean_name or any(ch in clean_name for ch in ("\x00", "\n", "\r")):
            raise ValueError("name must be non-empty and cannot contain NUL/newline characters.")
        raw = ctx.client.raw
        operation = raw.get_type("CampaignDraftOperation")
        operation.create.base_campaign = f"customers/{customer}/campaigns/{campaign_id}"
        operation.create.name = clean_name

        def execute():
            return ctx.client.mutate(
                "CampaignDraftService", customer, [operation], validate_only=validate_only
            )

        return ctx.safety.propose(
            tool_name="create_campaign_draft",
            customer_id=customer,
            description=f"Create campaign draft '{clean_name}' from campaign {campaign_id}",
            payload={"base_campaign_id": campaign_id, "name": clean_name, "validate_only": validate_only},
            execute=execute,
        )

    @mcp.tool()
    def rename_campaign_draft(
        customer_id: str,
        campaign_draft_resource_name: str,
        name: str,
        validate_only: bool = False,
    ) -> dict:
        """Propose renaming a campaign draft."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        resource = _owned(ctx, customer, campaign_draft_resource_name, "campaign_draft_resource_name")
        clean_name = str(name).strip()
        if not clean_name or any(ch in clean_name for ch in ("\x00", "\n", "\r")):
            raise ValueError("name must be non-empty and cannot contain NUL/newline characters.")
        raw = ctx.client.raw
        operation = raw.get_type("CampaignDraftOperation")
        operation.update.resource_name = resource
        operation.update.name = clean_name
        operation.update_mask.CopyFrom(field_mask_pb2.FieldMask(paths=["name"]))

        def execute():
            return ctx.client.mutate(
                "CampaignDraftService", customer, [operation], validate_only=validate_only
            )

        return ctx.safety.propose(
            tool_name="rename_campaign_draft",
            customer_id=customer,
            description=f"Rename campaign draft {resource} -> '{clean_name}'",
            payload={"campaign_draft_resource_name": resource, "name": clean_name, "validate_only": validate_only},
            execute=execute,
        )

    @mcp.tool()
    def remove_campaign_draft(
        customer_id: str,
        campaign_draft_resource_name: str,
        validate_only: bool = False,
    ) -> dict:
        """Propose discarding a campaign draft and its staged changes."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        resource = _owned(ctx, customer, campaign_draft_resource_name, "campaign_draft_resource_name")
        operation = ctx.client.raw.get_type("CampaignDraftOperation")
        operation.remove = resource

        def execute():
            return ctx.client.mutate(
                "CampaignDraftService", customer, [operation], validate_only=validate_only
            )

        return ctx.safety.propose(
            tool_name="remove_campaign_draft",
            customer_id=customer,
            description=f"Discard campaign draft {resource}",
            payload={"campaign_draft_resource_name": resource, "validate_only": validate_only},
            execute=execute,
        )

    @mcp.tool()
    def promote_campaign_draft(
        customer_id: str,
        campaign_draft_resource_name: str,
    ) -> dict:
        """Propose applying a campaign draft to its base campaign asynchronously."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        resource = _owned(ctx, customer, campaign_draft_resource_name, "campaign_draft_resource_name")
        raw = ctx.client.raw
        request = raw.get_type("PromoteCampaignDraftRequest")
        request.resource_name = resource

        def execute():
            response = _call(
                ctx.client.service("CampaignDraftService"),
                "promote_campaign_draft",
                request=request,
            )
            operation_name = getattr(getattr(response, "operation", None), "name", None)
            if operation_name is None:
                operation_name = getattr(response, "name", None)
            return {
                "campaign_draft_resource_name": resource,
                "long_running_operation": operation_name,
                "next_step": "Read campaign_draft.status; if PROMOTE_FAILED, call list_campaign_draft_async_errors.",
            }

        return ctx.safety.propose(
            tool_name="promote_campaign_draft",
            customer_id=customer,
            description=f"Promote campaign draft {resource} into its base campaign",
            payload={"campaign_draft_resource_name": resource},
            execute=execute,
        )

    @mcp.tool()
    def list_campaign_draft_async_errors(
        customer_id: str,
        campaign_draft_resource_name: str,
        page_size: int = 100,
        page_token: str | None = None,
    ) -> dict:
        """Read detailed errors from a failed asynchronous campaign-draft promotion."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        resource = _owned(ctx, customer, campaign_draft_resource_name, "campaign_draft_resource_name")
        if not 1 <= page_size <= 1000:
            raise ValueError("page_size must be between 1 and 1000.")
        raw = ctx.client.raw
        request = raw.get_type("ListCampaignDraftAsyncErrorsRequest")
        request.resource_name = resource
        request.page_size = page_size
        if page_token:
            request.page_token = page_token
        response = _call(
            ctx.client.service("CampaignDraftService"),
            "list_campaign_draft_async_errors",
            request=request,
        )
        return {
            "errors": [proto.Message.to_dict(item, preserving_proto_field_name=True) for item in response.errors],
            "next_page_token": response.next_page_token or None,
        }

    @mcp.tool()
    def remove_campaign_automatically_created_assets(
        customer_id: str,
        campaign_id: str,
        assets: list[dict],
    ) -> dict:
        """Propose removing specific Google-created campaign assets.

        Each item requires ``asset_resource_name`` and ``field_type``.
        """
        customer = ctx.client.assert_customer_allowed(customer_id)
        campaign = _id(campaign_id, "campaign_id")
        if not assets:
            raise ValueError("assets must not be empty.")
        raw = ctx.client.raw
        request = raw.get_type("RemoveCampaignAutomaticallyCreatedAssetRequest")
        request.customer_id = customer
        request.partial_failure = False
        safe_assets = []
        for item in assets:
            asset = _owned(ctx, customer, item.get("asset_resource_name", ""), "asset_resource_name")
            field_type = str(item.get("field_type", "")).strip().upper()
            try:
                field_enum = getattr(raw.enums.AssetFieldTypeEnum, field_type)
            except AttributeError as ex:
                raise ValueError(f"Unknown AssetFieldType: {field_type}") from ex
            operation = raw.get_type("RemoveCampaignAutomaticallyCreatedAssetOperation")
            operation.campaign = f"customers/{customer}/campaigns/{campaign}"
            operation.asset = asset
            operation.field_type = field_enum
            request.operations.append(operation)
            safe_assets.append({"asset_resource_name": asset, "field_type": field_type})

        def execute():
            response = _call(
                ctx.client.service("AutomaticallyCreatedAssetRemovalService"),
                "remove_campaign_automatically_created_asset",
                request=request,
            )
            return proto.Message.to_dict(response, preserving_proto_field_name=True)

        return ctx.safety.propose(
            tool_name="remove_campaign_automatically_created_assets",
            customer_id=customer,
            description=f"Remove {len(safe_assets)} automatically-created asset(s) from campaign {campaign}",
            payload={"campaign_id": campaign, "assets": safe_assets},
            execute=execute,
        )

    @mcp.tool()
    def remove_ad_automatically_created_assets(
        customer_id: str,
        ad_group_id: str,
        ad_id: str,
        assets: list[dict],
    ) -> dict:
        """Propose removing specific Google-created assets from an ad."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        ad_group = _id(ad_group_id, "ad_group_id")
        ad = _id(ad_id, "ad_id")
        if not assets:
            raise ValueError("assets must not be empty.")
        raw = ctx.client.raw
        request = raw.get_type("RemoveAutomaticallyCreatedAssetsRequest")
        request.ad_group_ad = f"customers/{customer}/adGroupAds/{ad_group}~{ad}"
        safe_assets = []
        for item in assets:
            asset = _owned(ctx, customer, item.get("asset_resource_name", ""), "asset_resource_name")
            field_type = str(item.get("field_type", "")).strip().upper()
            try:
                field_enum = getattr(raw.enums.AssetFieldTypeEnum, field_type)
            except AttributeError as ex:
                raise ValueError(f"Unknown AssetFieldType: {field_type}") from ex
            pair = raw.get_type("AssetsWithFieldType")
            pair.asset = asset
            pair.field_type = field_enum
            request.assets_with_field_type.append(pair)
            safe_assets.append({"asset_resource_name": asset, "field_type": field_type})

        def execute():
            _call(
                ctx.client.service("AdGroupAdService"),
                "remove_automatically_created_assets",
                request=request,
            )
            return {"ad_group_ad": request.ad_group_ad, "removed_assets": safe_assets}

        return ctx.safety.propose(
            tool_name="remove_ad_automatically_created_assets",
            customer_id=customer,
            description=f"Remove {len(safe_assets)} automatically-created asset(s) from ad {ad_group}~{ad}",
            payload={"ad_group_id": ad_group, "ad_id": ad, "assets": safe_assets},
            execute=execute,
        )
