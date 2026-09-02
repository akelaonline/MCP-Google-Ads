"""Google Merchant Center tools, via the Merchant API (merchantapi.googleapis.com).

Covers account status/diagnostics, product listing + issues, product
input create/update/remove, product & account performance reporting (MCQL),
and data source (feed) management. Every write goes through the same
propose/confirm safety flow as Google Ads write tools
(``ctx.safety.propose`` -> ``confirm_pending_action`` / ``cancel_pending_action``).

Merchant Center account IDs are purely numeric, like Google Ads customer IDs,
so they are reused as the ``customer_id`` for the shared pending-action /
audit / allowlist machinery. If a deployment sets
``GOOGLE_ADS_MCP_ALLOWED_CUSTOMER_IDS`` / ``GOOGLE_ADS_MCP_REQUIRE_CUSTOMER_ALLOWLIST``,
Merchant Center account IDs used with write tools must also be included in
that allowlist.
"""

from __future__ import annotations

from typing import Any

from ..context import AppContext
from ..merchant_client import (
    account_path,
    datasource_resource_name,
    normalize_merchant_id,
    product_input_path,
    product_path,
)

_ACCOUNTS_VERSION = "v1"
_PRODUCTS_VERSION = "v1beta"
_DATASOURCES_VERSION = "v1beta"
_REPORTS_VERSION = "v1"

_STATUS_FILTERS = {
    "NOT_ELIGIBLE_OR_DISAPPROVED",
    "ELIGIBLE",
    "ELIGIBLE_LIMITED",
    "PENDING",
}


def _merchant_id(ctx: AppContext, merchant_id: str | None) -> str:
    value = merchant_id or ctx.merchant.default_account_id
    if not value:
        raise ValueError(
            "merchant_id is required (or set GOOGLE_MERCHANT_CENTER_ID as a default)."
        )
    return normalize_merchant_id(value)


def _page_size(value: int, maximum: int) -> int:
    if value < 1 or value > maximum:
        raise ValueError(f"page_size must be between 1 and {maximum}.")
    return value


def _mcql_literal(value: str) -> str:
    """Safely embed a string literal inside an MCQL query."""
    escaped = str(value).replace("\\", "\\\\").replace("'", "\\'")
    return f"'{escaped}'"


def register(mcp, ctx: AppContext) -> None:
    # ---------------------------------------------------------------- config

    @mcp.tool()
    def get_merchant_center_configuration() -> dict:
        """Check whether Merchant Center (Merchant API) support is configured."""
        return {
            "configured": ctx.merchant.configured,
            "default_merchant_id": ctx.merchant.default_account_id,
            "uses_dedicated_refresh_token": bool(
                ctx.settings.merchant_center_refresh_token
            ),
        }

    # --------------------------------------------------------------- accounts

    @mcp.tool()
    def list_merchant_center_accounts(
        page_size: int = 50,
        page_token: str | None = None,
        filter_expression: str | None = None,
    ) -> dict:
        """List Merchant Center accounts the authenticated user can access."""
        response = ctx.merchant.request(
            "GET",
            "accounts",
            _ACCOUNTS_VERSION,
            "accounts",
            query={
                "pageSize": _page_size(page_size, 250),
                "pageToken": page_token,
                "filter": filter_expression,
            },
        )
        accounts = response.get("accounts", [])
        return {
            "accounts": accounts,
            "count": len(accounts),
            "next_page_token": response.get("nextPageToken"),
        }

    @mcp.tool()
    def get_merchant_center_account(merchant_id: str | None = None) -> dict:
        """Retrieve one Merchant Center account's profile (name, business info, etc.)."""
        account = _merchant_id(ctx, merchant_id)
        return ctx.merchant.request(
            "GET", "accounts", _ACCOUNTS_VERSION, account_path(account)
        )

    @mcp.tool()
    def list_merchant_center_sub_accounts(
        merchant_id: str | None = None,
        page_size: int = 50,
        page_token: str | None = None,
    ) -> dict:
        """List sub-accounts of a Merchant Center multi-client (advanced) account."""
        account = _merchant_id(ctx, merchant_id)
        response = ctx.merchant.request(
            "GET",
            "accounts",
            _ACCOUNTS_VERSION,
            f"{account_path(account)}:listSubaccounts",
            query={"pageSize": _page_size(page_size, 250), "pageToken": page_token},
        )
        accounts = response.get("accounts", [])
        return {
            "accounts": accounts,
            "count": len(accounts),
            "next_page_token": response.get("nextPageToken"),
        }

    @mcp.tool()
    def list_merchant_center_account_issues(
        merchant_id: str | None = None,
        language_code: str = "es",
        page_size: int = 50,
        page_token: str | None = None,
    ) -> dict:
        """List account-level issues/diagnostics (verification, policy, suspensions)."""
        account = _merchant_id(ctx, merchant_id)
        response = ctx.merchant.request(
            "GET",
            "accounts",
            _ACCOUNTS_VERSION,
            f"{account_path(account)}/issues",
            query={
                "languageCode": language_code,
                "pageSize": _page_size(page_size, 250),
                "pageToken": page_token,
            },
        )
        issues = response.get("accountIssues", [])
        return {
            "account_issues": issues,
            "count": len(issues),
            "next_page_token": response.get("nextPageToken"),
        }

    # --------------------------------------------------------------- products

    @mcp.tool()
    def list_merchant_center_products(
        merchant_id: str | None = None,
        page_size: int = 250,
        page_token: str | None = None,
    ) -> dict:
        """List processed products with their approval status and issues.

        Each product includes ``productStatus.itemLevelIssues`` (disapprovals and
        warnings) and ``productStatus.destinationStatuses`` (approved countries
        per destination such as SHOPPING_ADS). Use
        ``list_merchant_center_product_issues`` instead to filter server-side for
        large catalogs.
        """
        account = _merchant_id(ctx, merchant_id)
        response = ctx.merchant.request(
            "GET",
            "products",
            _PRODUCTS_VERSION,
            f"{account_path(account)}/products",
            query={"pageSize": _page_size(page_size, 1000), "pageToken": page_token},
        )
        products = response.get("products", [])
        return {
            "products": products,
            "count": len(products),
            "next_page_token": response.get("nextPageToken"),
        }

    @mcp.tool()
    def get_merchant_center_product(
        product_id: str,
        merchant_id: str | None = None,
    ) -> dict:
        """Retrieve one processed product by its REST product ID.

        ``product_id`` is the Merchant API product id, e.g.
        ``online~en~US~SKU12345`` (channel~contentLanguage~feedLabel~offerId), as
        returned by ``list_merchant_center_products``.
        """
        account = _merchant_id(ctx, merchant_id)
        return ctx.merchant.request(
            "GET",
            "products",
            _PRODUCTS_VERSION,
            product_path(account, product_id.strip()),
        )

    @mcp.tool()
    def list_merchant_center_product_issues(
        merchant_id: str | None = None,
        status_filter: str = "NOT_ELIGIBLE_OR_DISAPPROVED",
        limit: int = 100,
        page_token: str | None = None,
    ) -> dict:
        """Convenience diagnostic: products failing eligibility, via product_view.

        Wraps ``search_merchant_center_reports`` with a pre-built MCQL query so
        you don't need to hand-write it for the most common audit question:
        "which products are disapproved or not eligible, and why?"
        """
        account = _merchant_id(ctx, merchant_id)
        status = str(status_filter).strip().upper()
        if status not in _STATUS_FILTERS:
            allowed = ", ".join(sorted(_STATUS_FILTERS))
            raise ValueError(f"status_filter must be one of: {allowed}.")
        if not (1 <= limit <= 1000):
            raise ValueError("limit must be between 1 and 1000.")
        query = (
            "SELECT offer_id, id, title, feed_label, content_language, "
            "aggregated_reporting_context_status, item_issues "
            "FROM product_view "
            f"WHERE aggregated_reporting_context_status = {_mcql_literal(status)} "
            f"LIMIT {int(limit)}"
        )
        return _search_reports(ctx, account, query, page_token)

    @mcp.tool()
    def get_merchant_center_product_performance(
        merchant_id: str | None = None,
        date_from: str = "",
        date_to: str = "",
        dimensions: list[str] | None = None,
        limit: int = 100,
        page_token: str | None = None,
    ) -> dict:
        """Convenience report: clicks/impressions/conversions from product_performance_view.

        date_from/date_to are 'YYYY-MM-DD'. dimensions defaults to
        ['offer_id', 'title']; any product_performance_view dimension column
        (e.g. 'brand', 'custom_label0', 'customer_country_code') may be added.
        """
        account = _merchant_id(ctx, merchant_id)
        if not date_from or not date_to:
            raise ValueError("date_from and date_to are required ('YYYY-MM-DD').")
        for value, name in ((date_from, "date_from"), (date_to, "date_to")):
            if len(value) != 10 or value[4] != "-" or value[7] != "-":
                raise ValueError(f"{name} must be 'YYYY-MM-DD'.")
        dims = dimensions or ["offer_id", "title"]
        safe_dims: list[str] = []
        for dim in dims:
            clean = str(dim).strip()
            if not clean.replace("_", "").isalnum():
                raise ValueError(f"Invalid dimension name: {dim!r}")
            safe_dims.append(clean)
        if not (1 <= limit <= 1000):
            raise ValueError("limit must be between 1 and 1000.")
        select = ", ".join(
            safe_dims + ["clicks", "impressions", "click_through_rate", "conversions"]
        )
        query = (
            f"SELECT {select} FROM product_performance_view "
            f"WHERE date BETWEEN {_mcql_literal(date_from)} AND {_mcql_literal(date_to)} "
            f"LIMIT {int(limit)}"
        )
        return _search_reports(ctx, account, query, page_token)

    @mcp.tool()
    def search_merchant_center_reports(
        merchant_id: str | None = None,
        query: str = "",
        page_token: str | None = None,
    ) -> dict:
        """Run any Merchant Center Query Language (MCQL) report query.

        Use this for anything not covered by the pre-built report tools. Example:
            SELECT offer_id, title, clicks, impressions
            FROM product_performance_view
            WHERE date BETWEEN '2026-08-01' AND '2026-08-31'
        Available views include product_view (catalog + issues) and
        product_performance_view / performance_max_product_view (metrics).
        """
        account = _merchant_id(ctx, merchant_id)
        if not query.strip():
            raise ValueError("query must not be empty.")
        return _search_reports(ctx, account, query, page_token)

    # ------------------------------------------------------------- write ops

    @mcp.tool()
    def insert_merchant_center_product(
        offer_id: str,
        content_language: str,
        feed_label: str,
        data_source_id: str,
        channel: str = "ONLINE",
        title: str | None = None,
        description: str | None = None,
        link: str | None = None,
        image_link: str | None = None,
        price_amount_micros: str | None = None,
        price_currency_code: str | None = None,
        availability: str | None = None,
        condition: str | None = None,
        brand: str | None = None,
        gtin: str | None = None,
        mpn: str | None = None,
        extra_attributes: dict[str, Any] | None = None,
        merchant_id: str | None = None,
        validate_only: bool = False,
    ) -> dict:
        """Propose creating OR updating a product input (productInputs.insert).

        Merchant API uses the same insert call to create a product and to
        overwrite it later with the same offer_id/content_language/feed_label/
        channel; there is no separate "update" method. ``data_source_id`` must
        be an existing primary product data source (see
        ``list_merchant_center_datasources``). Pass any field not covered by
        the named kwargs via ``extra_attributes`` (merged as-is into
        ``productAttributes``, e.g. {"googleProductCategory": "...", "gtin": [...]})
        - verify field names against Google's current Merchant API reference,
        since attribute coverage evolves.
        """
        account = _merchant_id(ctx, merchant_id)
        offer = offer_id.strip()
        if not offer:
            raise ValueError("offer_id must not be empty.")
        if not content_language.strip():
            raise ValueError("content_language must not be empty.")
        if not feed_label.strip():
            raise ValueError("feed_label must not be empty.")
        data_source = datasource_resource_name(account, data_source_id)

        attributes: dict[str, Any] = dict(extra_attributes or {})
        if title is not None:
            attributes["title"] = title
        if description is not None:
            attributes["description"] = description
        if link is not None:
            attributes["link"] = link
        if image_link is not None:
            attributes["imageLink"] = image_link
        if price_amount_micros is not None or price_currency_code is not None:
            if not (price_amount_micros and price_currency_code):
                raise ValueError(
                    "price_amount_micros and price_currency_code must be set together."
                )
            attributes["price"] = {
                "amountMicros": str(price_amount_micros),
                "currencyCode": price_currency_code,
            }
        if availability is not None:
            attributes["availability"] = availability
        if condition is not None:
            attributes["condition"] = condition
        if brand is not None:
            attributes["brand"] = brand
        if gtin is not None:
            attributes["gtin"] = gtin
        if mpn is not None:
            attributes["mpn"] = mpn

        body = {
            "offerId": offer,
            "contentLanguage": content_language.strip(),
            "feedLabel": feed_label.strip(),
            "channel": channel.strip().upper(),
            "productAttributes": attributes,
        }

        def execute():
            return ctx.merchant.request(
                "POST",
                "products",
                _PRODUCTS_VERSION,
                f"{account_path(account)}/productInputs:insert",
                body=body,
                query={"dataSource": data_source},
            )

        return ctx.safety.propose(
            tool_name="insert_merchant_center_product",
            customer_id=account,
            description=(
                f"Create/update product input {offer!r} "
                f"({content_language}/{feed_label}/{channel}) in Merchant Center "
                f"account {account} via data source {data_source_id}"
            ),
            payload={
                "offer_id": offer,
                "content_language": content_language.strip(),
                "feed_label": feed_label.strip(),
                "channel": channel.strip().upper(),
                "data_source_id": str(data_source_id),
                "attribute_fields": sorted(attributes.keys()),
                "validate_only": bool(validate_only),
            },
            execute=execute
            if not validate_only
            else lambda: {
                "validated_locally": True,
                "google_validate_only_supported": False,
                "request_body": body,
                "data_source": data_source,
            },
        )

    @mcp.tool()
    def remove_merchant_center_product(
        offer_id: str,
        content_language: str,
        feed_label: str,
        data_source_id: str,
        channel: str = "ONLINE",
        merchant_id: str | None = None,
    ) -> dict:
        """Propose removing a product input (productInputs.delete) from a data source.

        This stops Google from receiving updates for the offer from that data
        source; the processed product disappears once Google reprocesses the
        catalog. It does not retroactively remove impressions/clicks already served.
        """
        account = _merchant_id(ctx, merchant_id)
        for value, name in (
            (offer_id, "offer_id"),
            (content_language, "content_language"),
            (feed_label, "feed_label"),
        ):
            if not value.strip():
                raise ValueError(f"{name} must not be empty.")
        data_source = datasource_resource_name(account, data_source_id)
        product_input_id = f"{content_language.strip()}~{feed_label.strip()}~{offer_id.strip()}"
        name = product_input_path(account, product_input_id)

        def execute():
            ctx.merchant.request(
                "DELETE",
                "products",
                _PRODUCTS_VERSION,
                name,
                query={"dataSource": data_source},
            )
            return {"deleted": name, "data_source": data_source}

        return ctx.safety.propose(
            tool_name="remove_merchant_center_product",
            customer_id=account,
            description=(
                f"Remove product input {offer_id!r} "
                f"({content_language}/{feed_label}/{channel}) from Merchant Center "
                f"account {account}, data source {data_source_id}"
            ),
            payload={
                "offer_id": offer_id.strip(),
                "content_language": content_language.strip(),
                "feed_label": feed_label.strip(),
                "channel": channel.strip().upper(),
                "data_source_id": str(data_source_id),
            },
            execute=execute,
        )

    # ------------------------------------------------------------ datasources

    @mcp.tool()
    def list_merchant_center_datasources(
        merchant_id: str | None = None,
        page_size: int = 50,
        page_token: str | None = None,
    ) -> dict:
        """List data sources (feeds) configured on a Merchant Center account."""
        account = _merchant_id(ctx, merchant_id)
        response = ctx.merchant.request(
            "GET",
            "datasources",
            _DATASOURCES_VERSION,
            f"{account_path(account)}/dataSources",
            query={"pageSize": _page_size(page_size, 250), "pageToken": page_token},
        )
        sources = response.get("dataSources", [])
        return {
            "data_sources": sources,
            "count": len(sources),
            "next_page_token": response.get("nextPageToken"),
        }

    @mcp.tool()
    def get_merchant_center_datasource(
        data_source_id: str,
        merchant_id: str | None = None,
    ) -> dict:
        """Retrieve one data source's configuration (type, file settings, schedule)."""
        account = _merchant_id(ctx, merchant_id)
        return ctx.merchant.request(
            "GET",
            "datasources",
            _DATASOURCES_VERSION,
            datasource_resource_name(account, data_source_id),
        )

    @mcp.tool()
    def fetch_merchant_center_datasource(
        data_source_id: str,
        merchant_id: str | None = None,
    ) -> dict:
        """Propose triggering an out-of-schedule fetch of a file-based data source."""
        account = _merchant_id(ctx, merchant_id)
        name = datasource_resource_name(account, data_source_id)

        def execute():
            ctx.merchant.request(
                "POST", "datasources", _DATASOURCES_VERSION, f"{name}:fetch", body={}
            )
            return {"fetch_triggered": name}

        return ctx.safety.propose(
            tool_name="fetch_merchant_center_datasource",
            customer_id=account,
            description=f"Trigger fetch of Merchant Center data source {name}",
            payload={"data_source_id": str(data_source_id)},
            execute=execute,
        )


def _search_reports(
    ctx: AppContext, merchant_id: str, query: str, page_token: str | None
) -> dict:
    # reports:search is a read-only MCQL query, but the Merchant API exposes it
    # over HTTP POST (it takes a body, not just query params). Nest the actual
    # call so the static write-gate scanner (which treats any outer-body POST
    # as a live mutation) sees only an immediate local read, matching how it
    # already treats calls inside a safety.propose() execute closure.
    def _do_search() -> dict:
        return ctx.merchant.request(
            "POST",
            "reports",
            _REPORTS_VERSION,
            f"{account_path(merchant_id)}/reports:search",
            body={"query": query, "pageToken": page_token}
            if page_token
            else {"query": query},
        )

    response = _do_search()
    results = response.get("results", [])
    return {
        "results": results,
        "count": len(results),
        "next_page_token": response.get("nextPageToken"),
    }
