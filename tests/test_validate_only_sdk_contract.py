"""validate_only / partial_failure must reach the real GAPIC request message.

The Google Ads SDK stubs flatten only ``customer_id`` and the operations into
keyword arguments; ``validate_only`` and ``partial_failure`` exist only on the
request message. A wrapper that probes for them as direct arguments silently
drops ``validate_only=True`` and turns a dry run into a real mutation.
"""

from __future__ import annotations

import inspect
from typing import Any, ClassVar
from unittest.mock import MagicMock

import pytest
from google.ads.googleads.v26.services.services.campaign_group_service import (
    CampaignGroupServiceClient,
)
from google.ads.googleads.v26.services.services.google_ads_service import (
    GoogleAdsServiceClient,
)
from google.ads.googleads.v26.services.types.campaign_group_service import (
    CampaignGroupOperation,
    MutateCampaignGroupsRequest,
)
from google.ads.googleads.v26.services.types.google_ads_service import (
    MutateGoogleAdsRequest,
    MutateOperation,
)

from google_ads_mcp.client import GoogleAdsClientWrapper
from google_ads_mcp.errors import GoogleAdsMcpError


class _Settings:
    google_ads_yaml_dict: ClassVar[dict[str, Any]] = {}


def _wrapper(service):
    wrapper = GoogleAdsClientWrapper(_Settings())
    wrapper.service = lambda name: service
    wrapper._client = MagicMock()  # no real GoogleAdsClient in unit tests
    return wrapper


class _CampaignGroupStub:
    """Same signature as the real stub: flags only inside ``request``."""

    def __init__(self):
        self.calls = []

    def mutate_campaign_groups(
        self,
        request: MutateCampaignGroupsRequest | dict | None = None,
        *,
        customer_id: str | None = None,
        operations: list[CampaignGroupOperation] | None = None,
    ):
        self.calls.append(
            {"request": request, "customer_id": customer_id, "operations": operations}
        )
        return "ok"


class _GoogleAdsStub:
    def __init__(self):
        self.calls = []

    def mutate(
        self,
        request: MutateGoogleAdsRequest | dict | None = None,
        *,
        customer_id: str | None = None,
        mutate_operations: list[MutateOperation] | None = None,
    ):
        self.calls.append({"request": request, "customer_id": customer_id})
        return "ok"


def test_real_sdk_signature_has_no_direct_validate_only():
    """Guard the assumption this fix relies on."""
    for method in (
        CampaignGroupServiceClient.mutate_campaign_groups,
        GoogleAdsServiceClient.mutate,
    ):
        params = inspect.signature(method).parameters
        assert "request" in params
        assert "validate_only" not in params
    assert "validate_only" in MutateCampaignGroupsRequest.meta.fields
    assert "validate_only" in MutateGoogleAdsRequest.meta.fields


@pytest.mark.parametrize("flag", [True, False])
def test_mutate_sends_validate_only_in_request(flag):
    stub = _CampaignGroupStub()
    operation = CampaignGroupOperation()
    operation.create.name = "grupo"

    _wrapper(stub).mutate(
        "CampaignGroupService", "123-456-7890", [operation], validate_only=flag
    )

    call = stub.calls[0]
    assert call["customer_id"] is None and call["operations"] is None
    request = call["request"]
    assert isinstance(request, MutateCampaignGroupsRequest)
    assert request.customer_id == "1234567890"
    assert request.validate_only is flag
    assert request.operations[0].create.name == "grupo"


def test_mutate_sends_partial_failure_in_request():
    stub = _CampaignGroupStub()
    _wrapper(stub).mutate(
        "CampaignGroupService",
        "1234567890",
        [CampaignGroupOperation()],
        partial_failure=True,
    )
    assert stub.calls[0]["request"].partial_failure is True


def test_mutate_atomic_sends_validate_only_in_request():
    stub = _GoogleAdsStub()
    _wrapper(stub).mutate_atomic("1234567890", [MutateOperation()], validate_only=True)
    request = stub.calls[0]["request"]
    assert isinstance(request, MutateGoogleAdsRequest)
    assert request.validate_only is True


def test_validate_only_is_never_silently_dropped():
    class _NoFlags:
        def mutate_campaign_budgets(self, *, customer_id, operations):
            raise AssertionError("must not be called")

    with pytest.raises(GoogleAdsMcpError, match="validate_only"):
        _wrapper(_NoFlags()).mutate(
            "CampaignBudgetService", "1234567890", ["op"], validate_only=True
        )
