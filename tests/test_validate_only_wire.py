"""validate_only on the wire: real GAPIC clients over an intercepting gRPC channel.

No mocks of ``**kwargs``: each service is the real SDK client, bound to a fake
channel that serializes the request exactly as grpc would. The assertions read
the bytes that would leave the process, so a dropped flag cannot hide.
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil
import typing
from typing import Any, ClassVar
from unittest.mock import MagicMock

import grpc
import pytest
from google.auth.credentials import AnonymousCredentials

from google_ads_mcp.client import GoogleAdsClientWrapper, _mutate_method_name
from google_ads_mcp.errors import GoogleAdsMcpError

_SERVICES_PKG = "google.ads.googleads.v26.services.services"


class _Settings:
    google_ads_yaml_dict: ClassVar[dict[str, Any]] = {}


class _Recorder:
    """grpc.Channel stand-in: records serialized requests, never touches a network."""

    def __init__(self) -> None:
        self.wire: list[tuple[str, bytes]] = []

    def unary_unary(
        self, method, request_serializer=None, response_deserializer=None, *_a, **_
    ):
        def call(request, timeout=None, metadata=None, credentials=None, **kw):
            self.wire.append((method, request_serializer(request)))
            return response_deserializer(b"")

        call.with_call = lambda request, **kw: (call(request, **kw), None)
        return call

    def __getattr__(self, name):  # subscribe/unsubscribe/close/etc.
        return lambda *a, **k: None


class _FakeChannel(_Recorder, grpc.Channel):
    def subscribe(self, callback, try_to_connect=False):
        return None

    def unsubscribe(self, callback):
        return None

    def unary_stream(self, method, *a, **k):
        def call(*_a, **_k):
            raise AssertionError(f"streaming call {method} is not used by mutate")

        return call

    def stream_unary(self, *a, **k):
        raise AssertionError("streaming is not used by mutate")

    def stream_stream(self, *a, **k):
        raise AssertionError("streaming is not used by mutate")

    def close(self):
        return None


def _real_service(service_name: str, recorder: _Recorder):
    snake = "".join(
        "_" + c.lower() if c.isupper() and i else c.lower()
        for i, c in enumerate(service_name)
    )
    module = importlib.import_module(f"{_SERVICES_PKG}.{snake}")
    client_cls = getattr(module, f"{service_name}Client")
    transport_cls = client_cls.get_transport_class("grpc")
    transport = transport_cls(credentials=AnonymousCredentials(), channel=recorder)
    return client_cls(transport=transport)


def _wrapper(service):
    wrapper = GoogleAdsClientWrapper(_Settings())
    wrapper.service = lambda name: service
    wrapper._client = MagicMock()
    return wrapper


def _wire_request(recorder, request_type):
    assert len(recorder.wire) == 1, "exactly one RPC expected"
    return request_type.deserialize(recorder.wire[0][1])


def _request_type(service_client, method_name):
    method = getattr(
        service_client if isinstance(service_client, type) else type(service_client),
        method_name,
    )
    hints = typing.get_type_hints(method)
    return next(a for a in typing.get_args(hints["request"]) if hasattr(a, "meta"))


@pytest.mark.parametrize("flag", [True, False])
def test_plural_service_wire_carries_validate_only(flag):
    from google.ads.googleads.v26.services.types.campaign_group_service import (
        CampaignGroupOperation,
        MutateCampaignGroupsRequest,
    )

    rec = _FakeChannel()
    service = _real_service("CampaignGroupService", rec)
    operation = CampaignGroupOperation()
    operation.create.name = "grupo"

    _wrapper(service).mutate(
        "CampaignGroupService", "123-456-7890", [operation], validate_only=flag
    )

    request = _wire_request(rec, MutateCampaignGroupsRequest)
    assert request.validate_only is flag
    assert request.customer_id == "1234567890"
    assert [op.create.name for op in request.operations] == ["grupo"]
    assert request.partial_failure is False


def test_partial_failure_policy_is_preserved_on_wire():
    from google.ads.googleads.v26.services.types.campaign_group_service import (
        CampaignGroupOperation,
        MutateCampaignGroupsRequest,
    )

    rec = _FakeChannel()
    _wrapper(_real_service("CampaignGroupService", rec)).mutate(
        "CampaignGroupService",
        "1234567890",
        [CampaignGroupOperation()],
        partial_failure=True,
        validate_only=True,
    )
    request = _wire_request(rec, MutateCampaignGroupsRequest)
    assert request.partial_failure is True and request.validate_only is True


@pytest.mark.parametrize("flag", [True, False])
def test_atomic_wire_carries_validate_only(flag):
    from google.ads.googleads.v26.services.types.google_ads_service import (
        MutateGoogleAdsRequest,
        MutateOperation,
    )

    rec = _FakeChannel()
    service = _real_service("GoogleAdsService", rec)
    _wrapper(service).mutate_atomic(
        "1234567890", [MutateOperation()], validate_only=flag
    )
    request = _wire_request(rec, MutateGoogleAdsRequest)
    assert request.validate_only is flag
    assert request.partial_failure is False
    assert len(request.mutate_operations) == 1


@pytest.mark.parametrize("flag", [True, False])
def test_singular_operation_service_wire(flag):
    from google.ads.googleads.v26.services.types.customer_client_link_service import (
        CustomerClientLinkOperation,
        MutateCustomerClientLinkRequest,
    )

    rec = _FakeChannel()
    service = _real_service("CustomerClientLinkService", rec)
    op = CustomerClientLinkOperation()
    op.create.client_customer = "customers/2222222222"
    _wrapper(service).mutate(
        "CustomerClientLinkService",
        "1234567890",
        [op],
        operations_field="operation",
        allow_cross_customer_references=True,
        validate_only=flag,
    )
    request = _wire_request(rec, MutateCustomerClientLinkRequest)
    assert request.validate_only is flag
    assert request.operation.create.client_customer == "customers/2222222222"


@pytest.mark.parametrize(
    "service_name, field",
    [
        ("BillingSetupService", "operation"),
        ("CustomerUserAccessService", "operation"),
        ("CustomerUserAccessInvitationService", "operation"),
    ],
)
def test_service_without_validate_only_refuses_before_rpc(service_name, field):
    rec = _FakeChannel()
    service = _real_service(service_name, rec)
    with pytest.raises(GoogleAdsMcpError, match="validate_only"):
        _wrapper(service).mutate(
            service_name,
            "1234567890",
            [MagicMock()],
            operations_field=field,
            validate_only=True,
        )
    assert rec.wire == [], "an unsupported dry run must not send anything"


def _all_plural_services():
    pkg = importlib.import_module(_SERVICES_PKG)
    for mod in pkgutil.iter_modules(pkg.__path__):
        if mod.name.endswith("_service"):
            yield mod.name


def test_every_real_service_either_carries_flag_or_refuses():
    """Sweep the whole v26 catalogue: no service may drop the flag silently."""
    checked = 0
    for module_name in _all_plural_services():
        module = importlib.import_module(f"{_SERVICES_PKG}.{module_name}")
        for cname, cls in inspect.getmembers(module, inspect.isclass):
            if (
                not cname.endswith("ServiceClient")
                or cls.__module__.split(".")[-1] != "client"
            ):
                continue
            service_name = cname.removesuffix("Client")
            method_name = _mutate_method_name(service_name)
            method = getattr(cls, method_name, None)
            if method is None:
                continue
            fields = set(_request_type(cls, method_name).meta.fields)
            checked += 1
            if "validate_only" in fields:
                continue
            # Services without the field must be refused by the wrapper.
            rec = _FakeChannel()
            service = _real_service(service_name, rec)
            op_field = "operation" if "operation" in fields else "operations"
            with pytest.raises(GoogleAdsMcpError):
                _wrapper(service).mutate(
                    service_name,
                    "1234567890",
                    [MagicMock()],
                    operations_field=op_field,
                    validate_only=True,
                )
            assert rec.wire == []
    assert checked > 60
