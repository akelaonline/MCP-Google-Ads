"""BrandSuggestionService wrapper for Google Ads API v25."""

from __future__ import annotations

from google.ads.googleads.errors import GoogleAdsException

from ..context import AppContext
from ..errors import GoogleAdsMcpError, format_google_ads_exception


def _enum(value) -> str:
    name = getattr(value, "name", None)
    return str(name) if name else str(value).rsplit(".", 1)[-1]


def register(mcp, ctx: AppContext) -> None:
    @mcp.tool()
    def suggest_brands(
        customer_id: str,
        brand_prefix: str,
        selected_brand_ids: list[str] | None = None,
    ) -> dict:
        """Suggest verified brands matching a prefix, excluding selected IDs."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        prefix = brand_prefix.strip()
        if not prefix:
            raise ValueError("brand_prefix must not be empty.")
        raw = ctx.client.raw
        request = raw.get_type("SuggestBrandsRequest")
        request.customer_id = customer
        request.brand_prefix = prefix
        request.selected_brands.extend(
            [
                str(value).strip()
                for value in (selected_brand_ids or [])
                if str(value).strip()
            ]
        )
        try:
            response = raw.get_service("BrandSuggestionService").suggest_brands(
                request=request
            )
        except GoogleAdsException as ex:
            raise GoogleAdsMcpError(format_google_ads_exception(ex)) from ex
        brands = [
            {
                "id": value.id,
                "name": value.name,
                "urls": list(value.urls),
                "state": _enum(value.state),
            }
            for value in response.brands
        ]
        return {"count": len(brands), "brands": brands}
