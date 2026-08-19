"""YouTube video upload lifecycle for Google Ads API v25.

The Google Ads API can upload videos directly to a Google-managed YouTube
channel or an advertiser-owned channel. Upload streaming is supported by the
Python client, so this MCP tool accepts a file path that exists on the MCP host.
"""

from __future__ import annotations

from pathlib import Path

from google.protobuf import field_mask_pb2

from ..context import AppContext
from ..errors import GoogleAdsMcpError, format_google_ads_exception

_ALLOWED_PRIVACY = {"PUBLIC", "UNLISTED"}
_ALLOWED_STATES = {
    "FAILED",
    "PENDING",
    "PROCESSED",
    "REJECTED",
    "UNAVAILABLE",
    "UPLOADED",
}


def _privacy(raw, value: str):
    clean = str(value).strip().upper()
    if clean not in _ALLOWED_PRIVACY:
        raise ValueError("video_privacy must be PUBLIC or UNLISTED.")
    return clean, getattr(raw.enums.YouTubeVideoPrivacyEnum, clean)


def _resource(ctx: AppContext, customer_id: str, resource_name: str) -> tuple[str, str]:
    customer = ctx.client.assert_customer_allowed(customer_id)
    resource = ctx.client.assert_resource_name_customer(
        customer,
        resource_name,
        field_name="you_tube_video_upload_resource_name",
    )
    return customer, resource


def _google_call(service, method_name: str, **kwargs):
    from google.ads.googleads.errors import GoogleAdsException

    try:
        return getattr(service, method_name)(**kwargs)
    except GoogleAdsException as ex:
        raise GoogleAdsMcpError(format_google_ads_exception(ex)) from ex


def register(mcp, ctx: AppContext) -> None:
    @mcp.tool()
    def list_youtube_video_uploads(
        customer_id: str,
        state: str | None = None,
        limit: int = 100,
    ) -> dict:
        """List videos uploaded through Google Ads API and their processing state."""
        if limit < 1 or limit > 1000:
            raise ValueError("limit must be between 1 and 1000.")
        where = ""
        if state:
            clean_state = str(state).strip().upper()
            if clean_state not in _ALLOWED_STATES:
                raise ValueError(
                    "state must be FAILED, PENDING, PROCESSED, REJECTED, "
                    "UNAVAILABLE, or UPLOADED."
                )
            where = f"WHERE you_tube_video_upload.state = '{clean_state}'"
        rows = ctx.client.search(
            customer_id,
            f"""
            SELECT
                you_tube_video_upload.resource_name,
                you_tube_video_upload.video_upload_id,
                you_tube_video_upload.video_id,
                you_tube_video_upload.state,
                you_tube_video_upload.channel_id,
                you_tube_video_upload.video_privacy
            FROM you_tube_video_upload
            {where}
            ORDER BY you_tube_video_upload.video_upload_id DESC
            LIMIT {limit}
            """,
        )
        return {"youtube_video_uploads": rows, "count": len(rows)}

    @mcp.tool()
    def get_youtube_video_upload(
        customer_id: str,
        you_tube_video_upload_resource_name: str,
    ) -> dict:
        """Retrieve one video upload including processing state and YouTube video ID."""
        customer, resource = _resource(
            ctx, customer_id, you_tube_video_upload_resource_name
        )
        safe = resource.replace("\\", "\\\\").replace("'", "\\'")
        rows = ctx.client.search(
            customer,
            f"""
            SELECT
                you_tube_video_upload.resource_name,
                you_tube_video_upload.video_upload_id,
                you_tube_video_upload.video_id,
                you_tube_video_upload.state,
                you_tube_video_upload.channel_id,
                you_tube_video_upload.video_privacy
            FROM you_tube_video_upload
            WHERE you_tube_video_upload.resource_name = '{safe}'
            LIMIT 1
            """,
        )
        upload = rows[0] if rows else None
        state = None
        video_id = None
        if upload:
            data = upload.get("you_tube_video_upload", {})
            state = data.get("state")
            video_id = data.get("video_id")
        return {
            "youtube_video_upload": upload,
            "found": bool(upload),
            "ready_for_ads": state == "PROCESSED" and bool(video_id),
            "video_id": video_id,
        }

    @mcp.tool()
    def upload_youtube_video(
        customer_id: str,
        video_file_path: str,
        video_title: str,
        video_description: str = "",
        channel_id: str | None = None,
        video_privacy: str = "UNLISTED",
    ) -> dict:
        """Propose uploading a local video file to YouTube through Google Ads API.

        ``video_file_path`` is a path on the machine running this MCP server.
        If ``channel_id`` is omitted, Google uses the Google-managed YouTube
        channel associated with the Ads account and privacy must be UNLISTED.
        """
        customer = ctx.client.assert_customer_allowed(customer_id)
        title = str(video_title).strip()
        if not title:
            raise ValueError("video_title must not be empty.")
        description = str(video_description)
        path = Path(video_file_path).expanduser().resolve()
        if not path.exists() or not path.is_file():
            raise ValueError("video_file_path must point to an existing regular file.")
        file_size = path.stat().st_size
        if file_size <= 0:
            raise ValueError("video_file_path is empty.")

        raw = ctx.client.raw
        privacy_name, privacy_value = _privacy(raw, video_privacy)
        clean_channel = str(channel_id).strip() if channel_id else None
        if not clean_channel and privacy_name != "UNLISTED":
            raise ValueError(
                "Google-managed YouTube channel uploads must use UNLISTED privacy."
            )

        request = raw.get_type("CreateYouTubeVideoUploadRequest")
        request.customer_id = customer
        upload = request.you_tube_video_upload
        upload.video_title = title
        upload.video_description = description
        upload.video_privacy = privacy_value
        if clean_channel:
            upload.channel_id = clean_channel
        service = ctx.client.service("YouTubeVideoUploadService")

        def execute():
            from google.ads.googleads.errors import GoogleAdsException

            try:
                with path.open("rb") as stream:
                    response = service.create_you_tube_video_upload(
                        stream=stream,
                        request=request,
                        retry=None,
                    )
            except GoogleAdsException as ex:
                raise GoogleAdsMcpError(format_google_ads_exception(ex)) from ex
            except OSError as ex:
                raise GoogleAdsMcpError(f"Could not read video file: {ex}") from ex
            return {
                "resource_name": getattr(response, "resource_name", None),
                "file_name": path.name,
                "file_size_bytes": file_size,
                "next_step": (
                    "Call get_youtube_video_upload until state is PROCESSED; then use "
                    "the returned video_id in Performance Max or Demand Gen assets."
                ),
            }

        return ctx.safety.propose(
            tool_name="upload_youtube_video",
            customer_id=customer,
            description=(
                f"Upload local video '{path.name}' to YouTube for Google Ads customer "
                f"{customer}"
            ),
            payload={
                "file_name": path.name,
                "file_size_bytes": file_size,
                "video_title": title,
                "video_description_length": len(description),
                "channel_id": clean_channel,
                "video_privacy": privacy_name,
            },
            execute=execute,
        )

    @mcp.tool()
    def update_youtube_video_upload(
        customer_id: str,
        you_tube_video_upload_resource_name: str,
        video_title: str | None = None,
        video_description: str | None = None,
        video_privacy: str | None = None,
    ) -> dict:
        """Propose updating supported metadata on a video uploaded through this API."""
        customer, resource = _resource(
            ctx, customer_id, you_tube_video_upload_resource_name
        )
        if video_title is None and video_description is None and video_privacy is None:
            raise ValueError("Provide at least one field to update.")

        raw = ctx.client.raw
        request = raw.get_type("UpdateYouTubeVideoUploadRequest")
        upload = request.you_tube_video_upload
        upload.resource_name = resource
        paths: list[str] = []
        if video_title is not None:
            title = str(video_title).strip()
            if not title:
                raise ValueError("video_title must not be empty when supplied.")
            upload.video_title = title
            paths.append("video_title")
        if video_description is not None:
            upload.video_description = str(video_description)
            paths.append("video_description")
        privacy_name = None
        if video_privacy is not None:
            privacy_name, privacy_value = _privacy(raw, video_privacy)
            upload.video_privacy = privacy_value
            paths.append("video_privacy")
        request.update_mask.CopyFrom(field_mask_pb2.FieldMask(paths=paths))
        service = ctx.client.service("YouTubeVideoUploadService")

        def execute():
            response = _google_call(
                service,
                "update_you_tube_video_upload",
                request=request,
            )
            return {
                "resource_name": getattr(response, "resource_name", resource),
                "updated_fields": paths,
                "video_privacy": privacy_name,
            }

        return ctx.safety.propose(
            tool_name="update_youtube_video_upload",
            customer_id=customer,
            description=f"Update YouTube upload {resource}: {', '.join(paths)}",
            payload={
                "you_tube_video_upload_resource_name": resource,
                "fields": paths,
                "video_privacy": privacy_name,
            },
            execute=execute,
        )

    @mcp.tool()
    def remove_youtube_video_upload(
        customer_id: str,
        you_tube_video_upload_resource_name: str,
    ) -> dict:
        """Propose removing a video from both Google Ads asset library and YouTube."""
        customer, resource = _resource(
            ctx, customer_id, you_tube_video_upload_resource_name
        )
        raw = ctx.client.raw
        request = raw.get_type("RemoveYouTubeVideoUploadRequest")
        request.customer_id = customer
        request.resource_name = resource
        service = ctx.client.service("YouTubeVideoUploadService")

        def execute():
            _google_call(service, "remove_you_tube_video_upload", request=request)
            return {"removed": resource}

        return ctx.safety.propose(
            tool_name="remove_youtube_video_upload",
            customer_id=customer,
            description=(
                f"Remove YouTube upload {resource} from Google Ads and YouTube"
            ),
            payload={"you_tube_video_upload_resource_name": resource},
            execute=execute,
        )
