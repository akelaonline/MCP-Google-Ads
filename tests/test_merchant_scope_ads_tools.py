"""Ads tools that name a Merchant Center account must honour the Merchant scope.

create_shopping_campaign, create_merchant_center_link and create_asset_set
(MERCHANT_CENTER_FEED) accept a Merchant account ID. That ID is in the Merchant
identifier space, so the Ads customer allowlist must not authorize it, and a
rejected target must not reach the Ads client (zero calls, nothing proposed).
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from conftest import FakeAuditLog, FakeMcp

from google_ads_mcp.context import AppContext
from google_ads_mcp.errors import GoogleAdsMcpError
from google_ads_mcp.merchant_scope import MerchantScope
from google_ads_mcp.safety import SafetyLayer
from google_ads_mcp.tools import asset_set_management, campaign_types, product_links

ALLOWED = "1111111111"
OUTSIDE = "9999999999"


class _ExplodingClient:
    """Any touch of the Ads client means the scope check came too late."""

    touched: list[str]

    def __init__(self):
        self.touched = []

    def assert_customer_allowed(self, customer_id):
        return str(customer_id).replace("-", "")

    @property
    def raw(self):
        self.touched.append("raw")
        raise AssertionError("Ads client used before the Merchant scope check")

    def service(self, name):
        self.touched.append(f"service:{name}")
        raise AssertionError("Ads service used before the Merchant scope check")


def _ctx(scope: MerchantScope):
    client = _ExplodingClient()
    safety = SafetyLayer(auto_approve=False, ttl_minutes=30, audit_log=FakeAuditLog())
    merchant = SimpleNamespace(scope=scope)
    ctx = AppContext(
        settings=SimpleNamespace(),
        client=client,
        safety=safety,
        audit=FakeAuditLog(),
        merchant=merchant,
    )
    mcp = FakeMcp()
    for module in (campaign_types, product_links, asset_set_management):
        module.register(mcp, ctx)
    return mcp.registered, client, safety


def _restricted():
    return MerchantScope.build(allowed_ids=[ALLOWED])


def _calls(tools):
    return [
        (
            "create_shopping_campaign",
            lambda: tools["create_shopping_campaign"](
                customer_id="1234567890",
                name="n",
                campaign_budget_resource_name="customers/1234567890/campaignBudgets/1",
                merchant_center_id=OUTSIDE,
            ),
        ),
        (
            "create_merchant_center_link",
            lambda: tools["create_merchant_center_link"](
                customer_id="1234567890", merchant_center_id=OUTSIDE
            ),
        ),
        (
            "create_asset_set",
            lambda: tools["create_asset_set"](
                customer_id="1234567890",
                name="feed",
                asset_set_type="MERCHANT_CENTER_FEED",
                merchant_id=OUTSIDE,
            ),
        ),
    ]


def test_rejected_merchant_target_never_reaches_ads_client():
    tools, client, _ = _ctx(_restricted())
    for name, call in _calls(tools):
        with pytest.raises(GoogleAdsMcpError, match="outside"):
            call()
        assert client.touched == [], name


def test_hardened_deployment_without_merchant_scope_refuses():
    scope = MerchantScope.build(ads_scope_configured=True)
    tools, client, _ = _ctx(scope)
    for name, call in _calls(tools):
        with pytest.raises(GoogleAdsMcpError, match="Merchant"):
            call()
        assert client.touched == [], name


def test_ads_customer_allowlist_does_not_authorize_a_merchant_id():
    # Same numeric value on both sides: the Ads side must not leak into Merchant.
    scope = MerchantScope.build(allowed_ids=[ALLOWED])
    with pytest.raises(GoogleAdsMcpError):
        scope.assert_allowed("1234567890")
