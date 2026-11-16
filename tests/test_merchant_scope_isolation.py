"""Merchant Center scope isolation (separate from the Google Ads allowlist).

Reproduces the audit finding: with a strict allowlist, reading a Merchant
account outside it used to perform the GET. Every read and write must be
refused before any request leaves the process.
"""

from __future__ import annotations

import io
import json
import urllib.error
from types import SimpleNamespace

import pytest
from conftest import FakeAuditLog, FakeMcp

from google_ads_mcp import merchant_client as mc
from google_ads_mcp.config import _merchant_id_set, load_settings
from google_ads_mcp.context import AppContext
from google_ads_mcp.errors import GoogleAdsMcpError
from google_ads_mcp.merchant_client import MerchantCenterClient
from google_ads_mcp.merchant_scope import MerchantScope
from google_ads_mcp.safety import SafetyLayer
from google_ads_mcp.tools import merchant_center

ALLOWED = "1111111111"
OUTSIDE = "9999999999"


def _settings(**overrides):
    base = {
        "merchant_center_refresh_token": "rt",
        "refresh_token": "",
        "client_id": "cid",
        "client_secret": "secret",
        "merchant_center_default_id": None,
        "allowed_merchant_ids": frozenset(),
        "require_merchant_allowlist": False,
        "allowed_customer_ids": frozenset(),
        "require_customer_allowlist": False,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


class _RecordingClient(MerchantCenterClient):
    """Real client (real scope + path enforcement); network is stubbed."""

    def __init__(self, settings, responses=None):
        super().__init__(settings)
        self.http_calls: list[tuple[str, str]] = []
        self._responses = responses or {}

    def _get_access_token(self):
        return "token"

    def _http(self, method, url):
        self.http_calls.append((method, url))


def _install_urlopen(monkeypatch, client, payload):
    class _Resp:
        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def read(self):
            return json.dumps(payload).encode()

    def fake_urlopen(request, timeout=0):
        client.http_calls.append((request.get_method(), request.full_url))
        return _Resp()

    monkeypatch.setattr(mc.urllib.request, "urlopen", fake_urlopen)


def _tools(client, settings=None, *, auto_approve=True, **safety_kwargs):
    safety = SafetyLayer(
        auto_approve=auto_approve,
        ttl_minutes=30,
        audit_log=FakeAuditLog(),
        **safety_kwargs,
    )
    ctx = AppContext(
        settings=settings or _settings(),
        client=None,
        safety=safety,
        audit=FakeAuditLog(),
        merchant=client,
    )
    mcp = FakeMcp()
    merchant_center.register(mcp, ctx)
    return mcp.registered, ctx


# ---------------------------------------------------------------- audit repro


def test_read_outside_allowlist_is_blocked_before_any_request(monkeypatch):
    client = _RecordingClient(_settings(allowed_merchant_ids=frozenset({ALLOWED})))
    _install_urlopen(monkeypatch, client, {"name": "accounts/x"})
    tools, _ = _tools(client)

    with pytest.raises(GoogleAdsMcpError, match="outside GOOGLE_ADS_MCP_ALLOWED_MERCHANT_IDS"):
        tools["get_merchant_center_account"](merchant_id=OUTSIDE)
    assert client.http_calls == []

    tools["get_merchant_center_account"](merchant_id=ALLOWED)
    assert client.http_calls[0][1].endswith(f"/accounts/v1/accounts/{ALLOWED}")


@pytest.mark.parametrize(
    "tool, kwargs",
    [
        ("list_merchant_center_account_issues", {}),
        ("list_merchant_center_sub_accounts", {}),
        ("list_merchant_center_products", {}),
        ("get_merchant_center_product", {"product_id": "en~US~sku"}),
        ("list_merchant_center_datasources", {}),
        ("get_merchant_center_datasource", {"data_source_id": "1"}),
        ("list_merchant_center_product_issues", {}),
        ("search_merchant_center_reports", {"query": "SELECT offer_id FROM product_view"}),
        ("get_merchant_center_developer_registration", {}),
    ],
)
def test_every_read_tool_enforces_scope(monkeypatch, tool, kwargs):
    client = _RecordingClient(_settings(allowed_merchant_ids=frozenset({ALLOWED})))
    _install_urlopen(monkeypatch, client, {})
    tools, _ = _tools(client)
    with pytest.raises(GoogleAdsMcpError, match="Merchant Center account"):
        tools[tool](merchant_id=OUTSIDE, **kwargs)
    assert client.http_calls == []


def test_default_merchant_id_is_also_checked(monkeypatch):
    client = _RecordingClient(
        _settings(
            allowed_merchant_ids=frozenset({ALLOWED}),
            merchant_center_default_id=OUTSIDE,
        )
    )
    _install_urlopen(monkeypatch, client, {})
    tools, _ = _tools(client)
    with pytest.raises(GoogleAdsMcpError, match="outside"):
        tools["get_merchant_center_account"]()
    assert client.http_calls == []


def test_request_layer_blocks_even_a_tool_that_forgot_to_check(monkeypatch):
    client = _RecordingClient(_settings(allowed_merchant_ids=frozenset({ALLOWED})))
    _install_urlopen(monkeypatch, client, {})
    with pytest.raises(GoogleAdsMcpError, match="outside"):
        client.request("GET", "products", "v1", f"accounts/{OUTSIDE}/products")
    with pytest.raises(GoogleAdsMcpError, match="outside"):
        client.request("POST", "accounts", "v1", f"accounts/{OUTSIDE}:listSubaccounts")
    assert client.http_calls == []


# ------------------------------------------------------------ discovery filter


def test_account_and_subaccount_listings_are_filtered(monkeypatch):
    client = _RecordingClient(_settings(allowed_merchant_ids=frozenset({ALLOWED, "2222222222"})))
    accounts = [
        {"name": f"accounts/{ALLOWED}", "accountId": ALLOWED},
        {"name": f"accounts/{OUTSIDE}", "accountId": OUTSIDE},
        {"name": "accounts/2222222222"},
        {"accountName": "no id at all"},
    ]
    _install_urlopen(monkeypatch, client, {"accounts": accounts, "nextPageToken": "n"})
    tools, _ = _tools(client)

    listed = tools["list_merchant_center_accounts"]()
    assert [a.get("accountId") or a["name"] for a in listed["accounts"]] == [
        ALLOWED,
        "accounts/2222222222",
    ]
    assert listed["count"] == 2

    subs = tools["list_merchant_center_sub_accounts"](merchant_id=ALLOWED)
    assert subs["count"] == 2
    assert all(OUTSIDE not in json.dumps(a) for a in subs["accounts"])


# ----------------------------------------------------------------- write scope


def test_write_outside_merchant_allowlist_is_blocked(monkeypatch):
    client = _RecordingClient(_settings(allowed_merchant_ids=frozenset({ALLOWED})))
    _install_urlopen(monkeypatch, client, {})
    tools, _ = _tools(
        client,
        allowed_merchant_ids={ALLOWED},
    )
    with pytest.raises(GoogleAdsMcpError, match="outside"):
        tools["fetch_merchant_center_datasource"](data_source_id="1", merchant_id=OUTSIDE)
    assert client.http_calls == []


def test_ads_allowlist_does_not_authorize_a_merchant_account():
    scope = MerchantScope.build(allowed_ids={ALLOWED}, ads_scope_configured=True)
    with pytest.raises(GoogleAdsMcpError):
        scope.assert_allowed("5555555555")  # an Ads customer id value is irrelevant


def test_merchant_write_not_gated_by_ads_allowlist(monkeypatch):
    """A Merchant ID need not (and must not have to) be an Ads customer ID."""
    client = _RecordingClient(_settings(allowed_merchant_ids=frozenset({ALLOWED})))
    _install_urlopen(monkeypatch, client, {})
    tools, _ = _tools(
        client,
        allowed_customer_ids={"7777777777"},
        require_customer_allowlist=True,
        allowed_merchant_ids={ALLOWED},
    )
    result = tools["fetch_merchant_center_datasource"](
        data_source_id="1", merchant_id=ALLOWED
    )
    assert result["status"] == "executed"


def test_confirm_rechecks_merchant_scope_for_pending_actions():
    client = _RecordingClient(_settings(allowed_merchant_ids=frozenset({ALLOWED})))
    tools, ctx = _tools(client, auto_approve=False, allowed_merchant_ids={ALLOWED})
    pending = tools["fetch_merchant_center_datasource"](
        data_source_id="1", merchant_id=ALLOWED
    )
    assert pending["status"] == "pending_confirmation"
    # Tighten the deployment scope after the proposal was created.
    ctx.safety._merchant_scope = MerchantScope.build(allowed_ids={"2222222222"})
    with pytest.raises(GoogleAdsMcpError, match="outside"):
        ctx.safety.confirm(pending["pending_action_id"])
    assert client.http_calls == []


# ------------------------------------------------------------------ fail closed


def test_hardened_ads_deployment_without_merchant_scope_refuses_merchant(monkeypatch):
    settings = _settings(allowed_customer_ids=frozenset({"7777777777"}))
    client = _RecordingClient(settings)
    _install_urlopen(monkeypatch, client, {})
    tools, _ = _tools(client, settings)
    with pytest.raises(GoogleAdsMcpError, match="GOOGLE_ADS_MCP_ALLOWED_MERCHANT_IDS"):
        tools["get_merchant_center_account"](merchant_id=ALLOWED)
    with pytest.raises(GoogleAdsMcpError, match="GOOGLE_ADS_MCP_ALLOWED_MERCHANT_IDS"):
        tools["list_merchant_center_accounts"]()
    assert client.http_calls == []
    cfg = tools["get_merchant_center_configuration"]()
    assert cfg["merchant_access_blocked_missing_scope"] is True


def test_unscoped_development_setup_is_unchanged(monkeypatch):
    client = _RecordingClient(_settings())
    _install_urlopen(monkeypatch, client, {"accounts": [{"name": "accounts/5"}]})
    tools, _ = _tools(client)
    assert tools["list_merchant_center_accounts"]()["count"] == 1


# ----------------------------------------------------------------------- config


def test_config_parses_and_validates_merchant_ids(monkeypatch):
    monkeypatch.setenv("GOOGLE_ADS_MCP_ALLOWED_MERCHANT_IDS", "123, 456 ,")
    assert _merchant_id_set("GOOGLE_ADS_MCP_ALLOWED_MERCHANT_IDS") == {"123", "456"}
    monkeypatch.setenv("GOOGLE_ADS_MCP_ALLOWED_MERCHANT_IDS", "12-3")
    with pytest.raises(ValueError, match="invalid Merchant Center account ID"):
        _merchant_id_set("GOOGLE_ADS_MCP_ALLOWED_MERCHANT_IDS")


def test_require_merchant_allowlist_needs_ids(monkeypatch):
    monkeypatch.delenv("GOOGLE_ADS_MCP_ALLOWED_MERCHANT_IDS", raising=False)
    monkeypatch.setenv("GOOGLE_ADS_MCP_REQUIRE_MERCHANT_ALLOWLIST", "true")
    with pytest.raises(ValueError, match="REQUIRE_MERCHANT_ALLOWLIST"):
        load_settings()
    monkeypatch.setenv("GOOGLE_ADS_MCP_ALLOWED_MERCHANT_IDS", ALLOWED)
    settings = load_settings()
    assert settings.allowed_merchant_ids == frozenset({ALLOWED})
    assert settings.require_merchant_allowlist is True


# ---------------------------------------------------------------- error hinting


def test_unregistered_gcp_error_gets_actionable_hint(monkeypatch):
    client = _RecordingClient(_settings())

    def boom(request, timeout=0):
        body = json.dumps(
            {"error": {"status": "PERMISSION_DENIED",
                       "message": "GCP project is not registered as a developer"}}
        ).encode()
        raise urllib.error.HTTPError(request.full_url, 403, "Forbidden", {}, io.BytesIO(body))

    monkeypatch.setattr(mc.urllib.request, "urlopen", boom)
    with pytest.raises(GoogleAdsMcpError, match="developer registration"):
        client.request("GET", "products", "v1", "accounts/123/products")
