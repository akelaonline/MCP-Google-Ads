"""v26 YouTube upload lifecycle: propose -> confirm over a resumable session.

Exercises the real execute() path with a fake v26 service (whose create method
returns a ResumableUploadSession-like object, matching the google-ads 35 API),
verifies the integrity re-check between proposal and confirmation, stream
closure, and the immutable-field guard on updates. No network.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from conftest import FakeAuditLog, FakeMcp, FakeRawClient

from google_ads_mcp.errors import GoogleAdsMcpError
from google_ads_mcp.safety import SafetyLayer
from google_ads_mcp.tools import youtube_uploads


class _FakeSession:
    def __init__(self):
        self.calls = []

    def upload(self, stream, size=None, **kwargs):
        self.calls.append({"stream": stream, "size": size})
        return SimpleNamespace(resource_name="customers/1/youTubeVideoUploads/9")


class _FakeYouTubeService:
    def __init__(self, session):
        self._session = session
        self.update_requests = []

    # v26 signature: no `stream` kwarg; returns a resumable session.
    def create_you_tube_video_upload(self, request=None, **kwargs):
        return self._session

    def update_you_tube_video_upload(self, request=None, **kwargs):
        self.update_requests.append(request)
        return SimpleNamespace(resource_name=request.you_tube_video_upload.resource_name)


def _ctx(service) -> SimpleNamespace:
    raw = FakeRawClient()
    raw.enums = SimpleNamespace(
        YouTubeVideoPrivacyEnum=SimpleNamespace(UNLISTED=1, PUBLIC=2)
    )
    client = SimpleNamespace(
        raw=raw,
        service=lambda name: service,
        assert_customer_allowed=lambda cid: cid.replace("-", ""),
        assert_resource_name_customer=lambda cid, rn, field_name="r": rn,
        search=lambda cid, q: [],
    )
    return SimpleNamespace(
        client=client,
        safety=SafetyLayer(auto_approve=False, ttl_minutes=30, audit_log=FakeAuditLog()),
        audit=FakeAuditLog(),
    )


def _registered(ctx):
    mcp = FakeMcp()
    youtube_uploads.register(mcp, ctx)
    return mcp.registered


def test_upload_executes_through_resumable_session_and_closes_stream(tmp_path):
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"\x00" * 2048)
    session = _FakeSession()
    ctx = _ctx(_FakeYouTubeService(session))
    tools = _registered(ctx)

    pending = tools["upload_youtube_video"](
        customer_id="1234567890",
        video_file_path=str(video),
        video_title="t",
        video_privacy="UNLISTED",
    )
    assert pending["status"] == "pending_confirmation"
    envelope = ctx.safety.confirm(pending["pending_action_id"]); result = envelope["result"]

    assert result["resource_name"] == "customers/1/youTubeVideoUploads/9"
    assert len(session.calls) == 1
    assert session.calls[0]["size"] == 2048
    assert session.calls[0]["stream"].closed


def test_upload_rejects_file_swapped_between_propose_and_confirm(tmp_path):
    video = tmp_path / "clip.mp4"
    video.write_bytes(b"\x00" * 2048)
    session = _FakeSession()
    ctx = _ctx(_FakeYouTubeService(session))
    tools = _registered(ctx)

    pending = tools["upload_youtube_video"](
        customer_id="1234567890",
        video_file_path=str(video),
        video_title="t",
        video_privacy="UNLISTED",
    )
    video.write_bytes(b"\xff" * 999)  # tamper after approval was requested

    with pytest.raises(GoogleAdsMcpError):
        ctx.safety.confirm(pending["pending_action_id"])
    assert session.calls == []


def test_update_rejects_immutable_title_and_description():
    ctx = _ctx(_FakeYouTubeService(_FakeSession()))
    tools = _registered(ctx)
    for kwargs in (
        {"video_title": "new"},
        {"video_description": "new"},
    ):
        with pytest.raises(ValueError):
            tools["update_youtube_video_upload"](
                customer_id="1234567890",
                you_tube_video_upload_resource_name="customers/1234567890/youTubeVideoUploads/9",
                **kwargs,
            )
    with pytest.raises(ValueError):
        tools["update_youtube_video_upload"](
            customer_id="1234567890",
            you_tube_video_upload_resource_name="customers/1234567890/youTubeVideoUploads/9",
        )


def test_update_privacy_only_masks_single_field():
    service = _FakeYouTubeService(_FakeSession())
    ctx = _ctx(service)
    tools = _registered(ctx)
    pending = tools["update_youtube_video_upload"](
        customer_id="1234567890",
        you_tube_video_upload_resource_name="customers/1234567890/youTubeVideoUploads/9",
        video_privacy="UNLISTED",
    )
    envelope = ctx.safety.confirm(pending["pending_action_id"]); result = envelope["result"]
    assert result["updated_fields"] == ["video_privacy"]
    assert result["video_privacy"] == "UNLISTED"
