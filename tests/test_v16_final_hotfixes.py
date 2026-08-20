"""Final v0.16 regression guards for contracts found during release audit."""

from types import SimpleNamespace

import pytest

from google_ads_mcp.client import _mutate_method_name
from google_ads_mcp.tools import advanced_audiences


class _FakeMcp:
    def __init__(self):
        self.tools = {}

    def tool(self):
        def decorator(fn):
            self.tools[fn.__name__] = fn
            return fn

        return decorator


class _AudienceClient:
    def assert_customer_allowed(self, customer_id):
        return str(customer_id).replace("-", "")

    def assert_resource_name_customer(self, customer_id, resource_name, **kwargs):
        return resource_name

    def search(self, customer_id, query):
        return [{"audience": {"scope": "ASSET_GROUP"}}]


def _audience_tools():
    mcp = _FakeMcp()
    ctx = SimpleNamespace(client=_AudienceClient(), safety=None)
    advanced_audiences.register(mcp, ctx)
    return mcp.tools


def test_customer_manager_link_uses_real_v25_singular_rpc_name():
    assert (
        _mutate_method_name("CustomerManagerLinkService")
        == "mutate_customer_manager_link"
    )


def test_asset_group_audience_cannot_be_renamed_without_promotion():
    update = _audience_tools()["update_audience_metadata"]
    with pytest.raises(ValueError, match="ASSET_GROUP-scoped audiences cannot"):
        update(
            customer_id="1234567890",
            audience_resource_name="customers/1234567890/audiences/7",
            name="Unsafe rename",
        )


def test_asset_group_audience_promotion_requires_customer_name():
    update = _audience_tools()["update_audience_metadata"]
    with pytest.raises(ValueError, match="requires a name"):
        update(
            customer_id="1234567890",
            audience_resource_name="customers/1234567890/audiences/7",
            promote_scope_to_customer=True,
        )
