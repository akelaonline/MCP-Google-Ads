"""Unit tests for the Merchant Center tool module.

Uses a fake MerchantCenterClient (records every request()/HTTP call) instead of
hitting the real Merchant API, mirroring the style of other tool-module tests
in this suite (see conftest.build_ctx / register_module).
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from conftest import FakeAuditLog, FakeMcp

from google_ads_mcp.context import AppContext
from google_ads_mcp.errors import GoogleAdsMcpError
from google_ads_mcp.safety import SafetyLayer
from google_ads_mcp.tools import merchant_center


class FakeMerchantClient:
    def __init__(self, response=None, default_account_id=None):
        self.calls: list[dict] = []
        self._response = response if response is not None else {}
        self.configured = True
        self.default_account_id = default_account_id

    def request(self, method, api, version, path, *, body=None, query=None, timeout=60):
        self.calls.append(
            {
                "method": method,
                "api": api,
                "version": version,
                "path": path,
                "body": body,
                "query": query,
            }
        )
        return self._response


def _fake_settings():
    return SimpleNamespace(merchant_center_refresh_token=None)


def _ctx(merchant, *, auto_approve: bool = True, auto_approve_destructive: bool | None = None) -> AppContext:
    safety = SafetyLayer(
        auto_approve=auto_approve,
        auto_approve_destructive=auto_approve_destructive,
        ttl_minutes=30,
        audit_log=FakeAuditLog(),
    )
    return AppContext(
        settings=_fake_settings(),
        client=None,
        safety=safety,
        audit=FakeAuditLog(),
        merchant=merchant,
    )


def _register(merchant, **ctx_kwargs):
    ctx = _ctx(merchant, **ctx_kwargs)
    mcp = FakeMcp()
    merchant_center.register(mcp, ctx)
    return mcp.registered, ctx


def test_get_configuration_reports_status():
    merchant = FakeMerchantClient(default_account_id="123")
    tools, _ctx_obj = _register(merchant)
    result = tools["get_merchant_center_configuration"]()
    assert result == {
        "configured": True,
        "default_merchant_id": "123",
        "uses_dedicated_refresh_token": False,
    }


def test_list_products_uses_v1beta_products_api():
    merchant = FakeMerchantClient(response={"products": [{"name": "p1"}]})
    tools, _ = _register(merchant)
    result = tools["list_merchant_center_products"](merchant_id="123456789")
    assert result["count"] == 1
    call = merchant.calls[0]
    assert call["method"] == "GET"
    assert call["api"] == "products"
    assert call["version"] == "v1beta"
    assert call["path"] == "accounts/123456789/products"


def test_merchant_id_falls_back_to_default():
    merchant = FakeMerchantClient(response={"accounts": []}, default_account_id="999")
    tools, _ = _register(merchant)
    tools["get_merchant_center_account"]()
    assert merchant.calls[0]["path"] == "accounts/999"


def test_merchant_id_required_without_default():
    merchant = FakeMerchantClient(response={})
    tools, _ = _register(merchant)
    with pytest.raises(ValueError, match="merchant_id is required"):
        tools["get_merchant_center_account"]()


def test_list_merchant_center_product_issues_builds_mcql_query():
    merchant = FakeMerchantClient(response={"results": [{"offerId": "sku1"}]})
    tools, _ = _register(merchant)
    result = tools["list_merchant_center_product_issues"](merchant_id="123")
    assert result["count"] == 1
    call = merchant.calls[0]
    assert call["method"] == "POST"
    assert call["path"] == "accounts/123/reports:search"
    assert "NOT_ELIGIBLE_OR_DISAPPROVED" in call["body"]["query"]
    assert "product_view" in call["body"]["query"]


def test_list_merchant_center_product_issues_rejects_bad_status():
    merchant = FakeMerchantClient()
    tools, _ = _register(merchant)
    with pytest.raises(ValueError, match="status_filter must be one of"):
        tools["list_merchant_center_product_issues"](
            merchant_id="123", status_filter="not_a_real_status"
        )


def test_product_performance_validates_dates():
    merchant = FakeMerchantClient()
    tools, _ = _register(merchant)
    with pytest.raises(ValueError, match="date_from and date_to are required"):
        tools["get_merchant_center_product_performance"](merchant_id="123")
    with pytest.raises(ValueError, match="must be 'YYYY-MM-DD'"):
        tools["get_merchant_center_product_performance"](
            merchant_id="123", date_from="08-2026-01", date_to="2026-08-31"
        )


def test_product_performance_rejects_unsafe_dimension():
    merchant = FakeMerchantClient()
    tools, _ = _register(merchant)
    with pytest.raises(ValueError, match="Invalid dimension name"):
        tools["get_merchant_center_product_performance"](
            merchant_id="123",
            date_from="2026-08-01",
            date_to="2026-08-31",
            dimensions=["brand; DROP TABLE"],
        )


def test_search_reports_rejects_empty_query():
    merchant = FakeMerchantClient()
    tools, _ = _register(merchant)
    with pytest.raises(ValueError, match="query must not be empty"):
        tools["search_merchant_center_reports"](merchant_id="123", query="")


def test_insert_product_is_a_pending_proposal_not_an_immediate_write():
    merchant = FakeMerchantClient(response={"name": "accounts/123/productInputs/x"})
    tools, ctx = _register(merchant, auto_approve=False)
    result = tools["insert_merchant_center_product"](
        offer_id="SKU1",
        content_language="en",
        feed_label="US",
        data_source_id="111",
        title="A shirt",
        price_amount_micros="15990000",
        price_currency_code="USD",
        merchant_id="123",
    )
    assert result["status"] == "pending_confirmation"
    # No live call yet: the write only happens once confirmed.
    assert merchant.calls == []
    action_id = result["pending_action_id"]
    confirmed = ctx.safety.confirm(action_id)
    assert confirmed["status"] == "executed"
    assert merchant.calls[0]["method"] == "POST"
    assert merchant.calls[0]["query"] == {"dataSource": "accounts/123/dataSources/111"}
    assert merchant.calls[0]["body"]["productAttributes"]["title"] == "A shirt"
    assert merchant.calls[0]["body"]["productAttributes"]["price"] == {
        "amountMicros": "15990000",
        "currencyCode": "USD",
    }


def test_insert_product_price_fields_must_be_set_together():
    merchant = FakeMerchantClient()
    tools, _ = _register(merchant)
    with pytest.raises(ValueError, match="must be set together"):
        tools["insert_merchant_center_product"](
            offer_id="SKU1",
            content_language="en",
            feed_label="US",
            data_source_id="111",
            price_amount_micros="15990000",
            merchant_id="123",
        )


def test_remove_product_is_gated_and_builds_expected_product_input_id():
    merchant = FakeMerchantClient(response={})
    tools, _ctx_obj = _register(merchant, auto_approve=True)
    result = tools["remove_merchant_center_product"](
        offer_id="SKU1",
        content_language="en",
        feed_label="US",
        data_source_id="111",
        merchant_id="123",
    )
    assert result["status"] == "executed"
    call = merchant.calls[0]
    assert call["method"] == "DELETE"
    assert call["path"] == "accounts/123/productInputs/en~US~SKU1"
    assert call["query"] == {"dataSource": "accounts/123/dataSources/111"}


def test_remove_product_is_destructive_risk_and_blocked_without_opt_in():
    merchant = FakeMerchantClient()
    ctx = _ctx(merchant, auto_approve=True, auto_approve_destructive=False)
    mcp = FakeMcp()
    merchant_center.register(mcp, ctx)
    result = mcp.registered["remove_merchant_center_product"](
        offer_id="SKU1",
        content_language="en",
        feed_label="US",
        data_source_id="111",
        merchant_id="123",
    )
    # Global auto-approve alone does not cover DESTRUCTIVE risk.
    assert result["status"] == "pending_confirmation"
    assert result["risk_level"] == "destructive"


def test_fetch_datasource_triggers_post_when_confirmed():
    merchant = FakeMerchantClient(response={})
    tools, _ctx_obj = _register(merchant, auto_approve=True)
    result = tools["fetch_merchant_center_datasource"](
        data_source_id="222", merchant_id="123"
    )
    assert result["status"] == "executed"
    call = merchant.calls[0]
    assert call["method"] == "POST"
    assert call["path"] == "accounts/123/dataSources/222:fetch"


def test_datasource_id_must_be_numeric():
    merchant = FakeMerchantClient()
    tools, _ = _register(merchant)
    with pytest.raises(ValueError, match="datasource_id must be the numeric"):
        tools["get_merchant_center_datasource"](data_source_id="not-a-number", merchant_id="123")


def test_read_only_mode_blocks_merchant_writes():
    from google_ads_mcp.read_only import ReadOnlySafetyProxy

    merchant = FakeMerchantClient()
    base_safety = SafetyLayer(auto_approve=True, ttl_minutes=30, audit_log=FakeAuditLog())
    ctx = AppContext(
        settings=_fake_settings(),
        client=None,
        safety=ReadOnlySafetyProxy(base_safety),
        audit=FakeAuditLog(),
        merchant=merchant,
    )
    mcp = FakeMcp()
    merchant_center.register(mcp, ctx)
    with pytest.raises(GoogleAdsMcpError, match="read-only mode"):
        mcp.registered["remove_merchant_center_product"](
            offer_id="SKU1",
            content_language="en",
            feed_label="US",
            data_source_id="111",
            merchant_id="123",
        )
    assert merchant.calls == []
