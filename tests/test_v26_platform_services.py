"""Contract tests for Google Ads API v26 additions in platform_services.

Uses the real v26 protobuf types via the pinned API version, a fake transport
service, and no network access.
"""

from __future__ import annotations

import inspect
from types import SimpleNamespace

import pytest
from google.ads.googleads.client import GoogleAdsClient
from google.oauth2.credentials import Credentials

from google_ads_mcp.client import GOOGLE_ADS_API_VERSION
from google_ads_mcp.tools import platform_services


def _raw_client() -> GoogleAdsClient:
    return GoogleAdsClient(
        credentials=Credentials(token="contract-token"),
        developer_token="contract-developer-token",
        version=GOOGLE_ADS_API_VERSION,
    )


class _FakeMcp:
    def __init__(self):
        self.registered = {}

    def tool(self):
        def deco(fn):
            self.registered[fn.__name__] = fn
            return fn

        return deco


def _ctx(service) -> SimpleNamespace:
    client = SimpleNamespace(
        assert_customer_allowed=lambda cid: cid.replace("-", ""),
        raw=_raw_client(),
        service=lambda name: service,
    )
    return SimpleNamespace(client=client)


def test_check_local_services_eligibility_builds_real_request():
    # client.get_type() returns dynamically-created classes in google-ads 35;
    # real RPC responses are proto-plus messages, so construct via the types
    # module the way the transport deserializer does.
    from google.ads.googleads.v26.services.types import (
        local_services_eligibility_service as lse_types,
    )

    response = lse_types.CheckLocalServicesEligibilityResponse()
    captured = {}

    class FakeService:
        def check_local_services_eligibility(self, request):
            captured["request"] = request
            return response

    mcp = _FakeMcp()
    platform_services.register(mcp, _ctx(FakeService()))
    result = mcp.registered["check_local_services_eligibility"](
        customer_id="123-456-7890", listing_id="gmb-listing-1"
    )
    assert captured["request"].customer_id == "1234567890"
    assert captured["request"].listing_id == "gmb-listing-1"
    assert result["customer_id"] == "1234567890"
    assert result["listing_id"] == "gmb-listing-1"


def test_check_local_services_eligibility_requires_listing():
    mcp = _FakeMcp()
    platform_services.register(mcp, _ctx(object()))
    with pytest.raises(ValueError):
        mcp.registered["check_local_services_eligibility"](
            customer_id="1234567890", listing_id="  "
        )


def test_v26_request_and_service_exist_on_pinned_version():
    raw = _raw_client()
    assert GOOGLE_ADS_API_VERSION == "v26"
    service = raw.get_service("LocalServicesEligibilityService")
    assert "check_local_services_eligibility" in dir(service)
    request = raw.get_type("CheckLocalServicesEligibilityRequest")
    request.customer_id = "1234567890"
    request.listing_id = "x"
    assert request.customer_id == "1234567890"


def test_v26_youtube_upload_uses_resumable_session():
    # google-ads 35 moved YouTube create uploads to ResumableUploadSession:
    # the stub no longer accepts a `stream=` kwarg.
    raw = _raw_client()
    service = raw.get_service("YouTubeVideoUploadService")
    params = inspect.signature(service.create_you_tube_video_upload).parameters
    assert "stream" not in params
    assert "request" in params
