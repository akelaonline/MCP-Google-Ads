"""Runtime contracts that sit below the v0.14 agency tools."""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from google.ads.googleads.client import GoogleAdsClient
from google.oauth2.credentials import Credentials

from google_ads_mcp.client import GoogleAdsClientWrapper
from google_ads_mcp.errors import GoogleAdsMcpError


class _SingularService:
    def __init__(self):
        self.calls = []

    def mutate_customer_user_access(self, customer_id, operation):
        self.calls.append((customer_id, operation))
        return {"ok": True}


class _FakeRaw:
    def __init__(self, service):
        self._service = service

    def get_service(self, name):
        assert name == "CustomerUserAccessService"
        return self._service


def _wrapper_with_service(service):
    settings = SimpleNamespace(
        allowed_customer_ids=frozenset(),
        require_customer_allowlist=False,
    )
    wrapper = GoogleAdsClientWrapper(settings)
    wrapper._client = _FakeRaw(service)
    return wrapper


def test_singular_mutate_passes_operation_object_not_list():
    service = _SingularService()
    wrapper = _wrapper_with_service(service)
    operation = object()

    result = wrapper.mutate(
        "CustomerUserAccessService",
        "123-456-7890",
        [operation],
        operations_field="operation",
    )

    assert result == {"ok": True}
    assert service.calls == [("1234567890", operation)]
    assert not isinstance(service.calls[0][1], list)


def test_singular_mutate_rejects_multiple_operations():
    service = _SingularService()
    wrapper = _wrapper_with_service(service)

    with pytest.raises(GoogleAdsMcpError, match="accepts exactly one operation"):
        wrapper.mutate(
            "CustomerUserAccessService",
            "1234567890",
            [object(), object()],
            operations_field="operation",
        )

    assert service.calls == []


def test_invoice_request_uses_real_v25_month_enum_contract():
    client = GoogleAdsClient(
        credentials=Credentials(token="contract-token"),
        developer_token="contract-developer-token",
        version="v25",
        use_proto_plus=True,
    )
    request = client.get_type("ListInvoicesRequest")
    request.customer_id = "1234567890"
    request.billing_setup = "customers/1234567890/billingSetups/999"
    request.issue_year = "2026"
    request.issue_month = client.enums.MonthOfYearEnum.JULY.value
    request.include_granular_level_invoice_details = True

    assert request.customer_id == "1234567890"
    assert request.issue_year == "2026"
    assert request.issue_month.name == "JULY"
    assert request.include_granular_level_invoice_details is True
