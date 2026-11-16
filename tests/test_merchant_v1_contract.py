"""Merchant API v1 request contracts (v1beta was discontinued by Google).

Field and path facts below are taken from Google's v1 discovery documents:
ProductInput no longer has ``channel``; ``attributes`` is ``productAttributes``;
``gtin`` became ``gtins``; ``taxes``/``taxCategory`` were removed; product IDs
are ``contentLanguage~feedLabel~offerId`` and must be unpadded base64url when a
part contains ``/``, ``%`` or ``~``.
"""

from __future__ import annotations

import pytest
from conftest import FakeMcp
from test_merchant_center_tools import FakeMerchantClient, _ctx

from google_ads_mcp.merchant_client import (
    build_product_id,
    encode_product_id,
    normalize_product_id,
    product_path,
)
from google_ads_mcp.tools import merchant_center


def _tools(merchant):
    ctx = _ctx(merchant, auto_approve=True)
    mcp = FakeMcp()
    merchant_center.register(mcp, ctx)
    return mcp.registered


def test_no_tool_uses_a_beta_version():
    assert merchant_center._ACCOUNTS_VERSION == "v1"
    assert merchant_center._PRODUCTS_VERSION == "v1"
    assert merchant_center._DATASOURCES_VERSION == "v1"
    assert merchant_center._REPORTS_VERSION == "v1"


def test_every_tool_call_goes_to_v1():
    merchant = FakeMerchantClient(response={})
    tools = _tools(merchant)
    tools["list_merchant_center_accounts"]()
    tools["get_merchant_center_account"](merchant_id="1")
    tools["list_merchant_center_sub_accounts"](merchant_id="1")
    tools["list_merchant_center_account_issues"](merchant_id="1")
    tools["list_merchant_center_products"](merchant_id="1")
    tools["get_merchant_center_product"](product_id="en~US~a", merchant_id="1")
    tools["list_merchant_center_product_issues"](merchant_id="1")
    tools["search_merchant_center_reports"](merchant_id="1", query="SELECT id FROM product_view")
    tools["list_merchant_center_datasources"](merchant_id="1")
    tools["get_merchant_center_datasource"](data_source_id="2", merchant_id="1")
    tools["get_merchant_center_developer_registration"](merchant_id="1")
    tools["fetch_merchant_center_datasource"](data_source_id="2", merchant_id="1")
    tools["insert_merchant_center_product"](
        offer_id="a", content_language="en", feed_label="US", data_source_id="2", merchant_id="1"
    )
    tools["remove_merchant_center_product"](
        offer_id="a", content_language="en", feed_label="US", data_source_id="2", merchant_id="1"
    )
    assert merchant.calls
    assert {call["version"] for call in merchant.calls} == {"v1"}


def test_insert_body_matches_v1_product_input():
    merchant = FakeMerchantClient(response={})
    tools = _tools(merchant)
    tools["insert_merchant_center_product"](
        offer_id="SKU1",
        content_language="es",
        feed_label="AR",
        data_source_id="111",
        title="Piso",
        gtin="7790000000001",
        merchant_id="123",
    )
    call = merchant.calls[0]
    assert call["path"] == "accounts/123/productInputs:insert"
    body = call["body"]
    assert set(body) == {"offerId", "contentLanguage", "feedLabel", "productAttributes"}
    assert body["productAttributes"]["gtins"] == ["7790000000001"]
    assert "gtin" not in body["productAttributes"]


def test_insert_translates_legacy_gtin_and_rejects_removed_attributes():
    merchant = FakeMerchantClient(response={})
    tools = _tools(merchant)
    tools["insert_merchant_center_product"](
        offer_id="a", content_language="en", feed_label="US", data_source_id="2",
        extra_attributes={"gtin": "123"}, merchant_id="1",
    )
    assert merchant.calls[0]["body"]["productAttributes"]["gtins"] == ["123"]
    for removed in ("taxes", "taxCategory"):
        with pytest.raises(ValueError, match="removed"):
            tools["insert_merchant_center_product"](
                offer_id="a", content_language="en", feed_label="US", data_source_id="2",
                extra_attributes={removed: []}, merchant_id="1",
            )


@pytest.mark.parametrize("tool", ["insert_merchant_center_product", "remove_merchant_center_product"])
def test_retired_channel_values_are_rejected(tool):
    merchant = FakeMerchantClient(response={})
    tools = _tools(merchant)
    with pytest.raises(ValueError, match="channel"):
        tools[tool](
            offer_id="a", content_language="en", feed_label="US", data_source_id="2",
            channel="LOCAL", merchant_id="1",
        )
    assert merchant.calls == []


def test_product_id_encoding_matches_googles_documented_example():
    # Documented: en~US~sku/123 -> ZW5-VVN-c2t1LzEyMw
    assert encode_product_id("en~US~sku/123") == "ZW5-VVN-c2t1LzEyMw"
    assert build_product_id("en", "US", "sku/123") == "ZW5-VVN-c2t1LzEyMw"
    assert build_product_id("en", "US", "sku123") == "en~US~sku123"
    assert build_product_id("es", "AR", "PISO 10mm") == encode_product_id("es~AR~PISO 10mm")


def test_remove_uses_encoded_id_for_special_characters():
    merchant = FakeMerchantClient(response={})
    tools = _tools(merchant)
    tools["remove_merchant_center_product"](
        offer_id="sku/123", content_language="en", feed_label="US", data_source_id="2",
        merchant_id="1",
    )
    assert merchant.calls[0]["path"] == "accounts/1/productInputs/ZW5-VVN-c2t1LzEyMw"


def test_get_product_accepts_v1_legacy_beta_and_encoded_ids():
    assert product_path("1", "en~US~sku1") == "accounts/1/products/en~US~sku1"
    assert product_path("1", "online~en~US~sku1") == "accounts/1/products/en~US~sku1"
    assert product_path("1", "local~en~US~sku1") == "accounts/1/products/local~en~US~sku1"
    assert normalize_product_id("ZW5-VVN-c2t1LzEyMw") == "ZW5-VVN-c2t1LzEyMw"
    assert normalize_product_id("online~en~US~sku/1") == encode_product_id("en~US~sku/1")
    with pytest.raises(ValueError):
        normalize_product_id("  ")
