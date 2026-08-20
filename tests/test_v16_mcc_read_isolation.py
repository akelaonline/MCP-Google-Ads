from __future__ import annotations

import pytest

from google_ads_mcp.client import GoogleAdsClientWrapper, _gaql_from_resource
from google_ads_mcp.config import Settings
from google_ads_mcp.errors import GoogleAdsMcpError
from google_ads_mcp.scoped_client import ScopedGoogleAdsClientWrapper


def _settings() -> Settings:
    return Settings(
        developer_token="dev",
        client_id="client",
        client_secret="secret",
        refresh_token="refresh",
        login_customer_id=None,
        auto_approve=False,
        pending_ttl_minutes=30,
        audit_db_path=":memory:",
        transport="stdio",
        http_port=8080,
        allowed_customer_ids=frozenset({"1111111111", "2222222222"}),
        require_customer_allowlist=True,
    )


def test_gaql_from_resource_is_case_insensitive():
    assert _gaql_from_resource("SELECT customer_client.id FROM customer_client") == "customer_client"
    assert _gaql_from_resource("select campaign.id FrOm campaign") == "campaign"


def test_customer_client_rows_outside_allowlist_are_filtered():
    client = GoogleAdsClientWrapper(_settings())
    rows = [
        {"customer_client": {"id": 1111111111, "descriptive_name": "manager"}},
        {"customer_client": {"id": 2222222222, "descriptive_name": "allowed child"}},
        {"customer_client": {"id": 3333333333, "descriptive_name": "other tenant"}},
    ]
    filtered = client._filter_allowed_hierarchy_rows(
        "SELECT customer_client.id, customer_client.descriptive_name FROM customer_client",
        rows,
    )
    assert [row["customer_client"]["id"] for row in filtered] == [
        1111111111,
        2222222222,
    ]


def test_customer_client_query_without_id_fails_closed():
    client = GoogleAdsClientWrapper(_settings())
    with pytest.raises(GoogleAdsMcpError, match="must select customer_client.id"):
        client._filter_allowed_hierarchy_rows(
            "SELECT customer_client.descriptive_name FROM customer_client",
            [{"customer_client": {"descriptive_name": "hidden child"}}],
        )


def test_customer_client_link_rows_filter_by_linked_client():
    client = GoogleAdsClientWrapper(_settings())
    rows = [
        {
            "customer_client_link": {
                "client_customer": "customers/2222222222",
                "status": "ACTIVE",
            }
        },
        {
            "customer_client_link": {
                "client_customer": "customers/3333333333",
                "status": "ACTIVE",
            }
        },
    ]
    filtered = client._filter_allowed_hierarchy_rows(
        "SELECT customer_client_link.client_customer FROM customer_client_link",
        rows,
    )
    assert len(filtered) == 1
    assert filtered[0]["customer_client_link"]["client_customer"] == "customers/2222222222"


def test_customer_manager_link_rows_filter_by_linked_manager():
    client = ScopedGoogleAdsClientWrapper(_settings())
    rows = [
        {
            "customer_manager_link": {
                "manager_customer": "customers/1111111111",
                "status": "ACTIVE",
            }
        },
        {
            "customer_manager_link": {
                "manager_customer": "customers/3333333333",
                "status": "ACTIVE",
            }
        },
    ]
    filtered = client._filter_allowed_hierarchy_rows(
        "SELECT customer_manager_link.manager_customer FROM customer_manager_link",
        rows,
    )
    assert len(filtered) == 1
    assert filtered[0]["customer_manager_link"]["manager_customer"] == "customers/1111111111"


def test_customer_manager_link_query_without_manager_fails_closed():
    client = ScopedGoogleAdsClientWrapper(_settings())
    with pytest.raises(
        GoogleAdsMcpError,
        match="must select customer_manager_link.manager_customer",
    ):
        client._filter_allowed_hierarchy_rows(
            "SELECT customer_manager_link.status FROM customer_manager_link",
            [{"customer_manager_link": {"status": "ACTIVE"}}],
        )


def test_non_hierarchy_rows_are_unchanged():
    client = ScopedGoogleAdsClientWrapper(_settings())
    rows = [{"campaign": {"id": 7, "name": "Search"}}]
    assert client._filter_allowed_hierarchy_rows(
        "SELECT campaign.id, campaign.name FROM campaign", rows
    ) == rows