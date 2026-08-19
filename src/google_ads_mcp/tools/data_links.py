"""YouTube creator/video DataLink lifecycle for Google Ads API v25."""

from __future__ import annotations

import re

from ..context import AppContext
from ..errors import GoogleAdsMcpError, format_google_ads_exception

_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")
_CHANNEL_ID_RE = re.compile(r"^UC[A-Za-z0-9_-]{20,}$")


def _video_id(value: str) -> str:
    text = str(value).strip()
    if not _VIDEO_ID_RE.fullmatch(text):
        raise ValueError(
            "video_id must be the 11-character YouTube video ID, not a full URL."
        )
    return text


def _channel_id(value: str | None, field_name: str) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not _CHANNEL_ID_RE.fullmatch(text):
        raise ValueError(
            f"{field_name} must be a YouTube channel ID beginning with 'UC'."
        )
    return text


def _call(service, method_name: str, **kwargs):
    from google.ads.googleads.errors import GoogleAdsException

    try:
        return getattr(service, method_name)(**kwargs)
    except GoogleAdsException as ex:
        raise GoogleAdsMcpError(format_google_ads_exception(ex)) from ex


def register(mcp, ctx: AppContext) -> None:
    @mcp.tool()
    def list_youtube_video_links(
        customer_id: str,
        status: str | None = None,
    ) -> dict:
        """List YouTube creator/video data links and pending requests."""
        filters = ["data_link.type = 'VIDEO'"]
        if status:
            clean = status.strip().upper()
            allowed = {
                "DISABLED",
                "ENABLED",
                "PENDING_APPROVAL",
                "REJECTED",
                "REQUESTED",
                "REVOKED",
            }
            if clean not in allowed:
                raise ValueError(
                    "status must be DISABLED, ENABLED, PENDING_APPROVAL, REJECTED, "
                    "REQUESTED, or REVOKED."
                )
            filters.append(f"data_link.status = '{clean}'")
        where = " AND ".join(filters)
        rows = ctx.client.search(
            customer_id,
            f"""
            SELECT
                data_link.resource_name,
                data_link.product_link_id,
                data_link.data_link_id,
                data_link.type,
                data_link.status,
                data_link.youtube_video.video_id,
                data_link.youtube_video.channel_id,
                data_link.youtube_link_metadata.brand_channel_id
            FROM data_link
            WHERE {where}
            ORDER BY data_link.data_link_id DESC
            """,
        )
        return {"youtube_video_links": rows, "count": len(rows)}

    @mcp.tool()
    def request_youtube_video_link(
        customer_id: str,
        video_id: str,
        channel_id: str | None = None,
        brand_channel_id: str | None = None,
    ) -> dict:
        """Propose asking a YouTube creator to link one video to the Ads account.

        Google sets the resulting DataLink status to REQUESTED. ``channel_id`` is
        optional but can disambiguate the hosting channel. ``brand_channel_id``
        identifies the advertiser's linked YouTube brand channel for creator context.
        """
        customer = ctx.client.assert_customer_allowed(customer_id)
        video = _video_id(video_id)
        channel = _channel_id(channel_id, "channel_id")
        brand_channel = _channel_id(brand_channel_id, "brand_channel_id")
        raw = ctx.client.raw
        data_link = raw.get_type("DataLink")
        data_link.youtube_video.video_id = video
        if channel:
            data_link.youtube_video.channel_id = channel
        if brand_channel:
            data_link.youtube_link_metadata.brand_channel_id = brand_channel
        service = ctx.client.service("DataLinkService")

        def execute():
            response = _call(
                service,
                "create_data_link",
                customer_id=customer,
                data_link=data_link,
            )
            return {
                "resource_name": getattr(response, "resource_name", None),
                "expected_status": "REQUESTED",
                "next_step": (
                    "Call list_youtube_video_links to inspect whether the creator "
                    "accepted the request."
                ),
            }

        return ctx.safety.propose(
            tool_name="request_youtube_video_link",
            customer_id=customer,
            description=(
                f"Request YouTube video {video} be linked to Google Ads customer {customer}"
            ),
            payload={
                "video_id": video,
                "channel_id": channel,
                "brand_channel_id": brand_channel,
            },
            execute=execute,
        )

    @mcp.tool()
    def accept_youtube_video_link(
        customer_id: str,
        data_link_resource_name: str,
    ) -> dict:
        """Propose accepting a creator-initiated PENDING_APPROVAL video link."""
        return _update_link_status(
            ctx,
            customer_id,
            data_link_resource_name,
            "ENABLED",
            "accept_youtube_video_link",
        )

    @mcp.tool()
    def reject_youtube_video_link(
        customer_id: str,
        data_link_resource_name: str,
    ) -> dict:
        """Propose rejecting a creator-initiated PENDING_APPROVAL video link."""
        return _update_link_status(
            ctx,
            customer_id,
            data_link_resource_name,
            "REJECTED",
            "reject_youtube_video_link",
        )

    @mcp.tool()
    def revoke_youtube_video_link_request(
        customer_id: str,
        data_link_resource_name: str,
    ) -> dict:
        """Propose revoking an advertiser-initiated REQUESTED video link."""
        return _update_link_status(
            ctx,
            customer_id,
            data_link_resource_name,
            "REVOKED",
            "revoke_youtube_video_link_request",
        )

    @mcp.tool()
    def remove_youtube_video_link(
        customer_id: str,
        data_link_resource_name: str,
    ) -> dict:
        """Propose removing an established YouTube video link."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        resource = ctx.client.assert_resource_name_customer(
            customer,
            data_link_resource_name,
            field_name="data_link_resource_name",
        )
        service = ctx.client.service("DataLinkService")

        def execute():
            response = _call(
                service,
                "remove_data_link",
                customer_id=customer,
                resource_name=resource,
            )
            return {"resource_name": getattr(response, "resource_name", resource)}

        return ctx.safety.propose(
            tool_name="remove_youtube_video_link",
            customer_id=customer,
            description=f"Remove established YouTube video link {resource}",
            payload={"data_link_resource_name": resource},
            execute=execute,
        )


def _update_link_status(
    ctx: AppContext,
    customer_id: str,
    data_link_resource_name: str,
    status_name: str,
    tool_name: str,
) -> dict:
    customer = ctx.client.assert_customer_allowed(customer_id)
    resource = ctx.client.assert_resource_name_customer(
        customer,
        data_link_resource_name,
        field_name="data_link_resource_name",
    )
    raw = ctx.client.raw
    status = getattr(raw.enums.DataLinkStatusEnum, status_name)
    service = ctx.client.service("DataLinkService")

    def execute():
        response = _call(
            service,
            "update_data_link",
            customer_id=customer,
            resource_name=resource,
            data_link_status=status,
        )
        return {
            "resource_name": getattr(response, "resource_name", resource),
            "status": status_name,
        }

    return ctx.safety.propose(
        tool_name=tool_name,
        customer_id=customer,
        description=f"Set YouTube video data link {resource} to {status_name}",
        payload={
            "data_link_resource_name": resource,
            "status": status_name,
        },
        execute=execute,
    )
