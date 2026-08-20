"""Allowlisted ReachPlanService workflows for Google Ads API v25."""

from __future__ import annotations

import proto
from google.ads.googleads.errors import GoogleAdsException

from ..client import micros
from ..context import AppContext
from ..errors import GoogleAdsMcpError, format_google_ads_exception

_REACH_DEVICES = {"DESKTOP", "MOBILE", "TABLET"}
_TAXONOMY_TYPES = {"AFFINITY", "IN_MARKET"}
_ALLOWLIST_NOTE = (
    " ReachPlanService is restricted by Google to allowlisted developer tokens; "
    "if the request is otherwise valid, confirm that this developer token has "
    "Reach Plan access."
)


def _dict(message) -> dict:
    return proto.Message.to_dict(message, preserving_proto_field_name=True)


def _call(raw, method_name: str, request):
    try:
        return getattr(raw.get_service("ReachPlanService"), method_name)(request=request)
    except GoogleAdsException as ex:
        raise GoogleAdsMcpError(
            format_google_ads_exception(ex) + _ALLOWLIST_NOTE
        ) from ex


def register(mcp, ctx: AppContext) -> None:
    @mcp.tool()
    def list_reach_plan_locations() -> dict:
        """List plannable Reach Plan locations (Google allowlist required)."""
        raw = ctx.client.raw
        response = _call(raw, "list_plannable_locations", raw.get_type("ListPlannableLocationsRequest"))
        result = _dict(response)
        result["google_allowlisted"] = True
        return result

    @mcp.tool()
    def list_reach_plan_products(plannable_location_id: str) -> dict:
        """List plannable Reach Plan products for a location."""
        location = str(plannable_location_id).strip()
        if not location:
            raise ValueError("plannable_location_id must not be empty.")
        raw = ctx.client.raw
        request = raw.get_type("ListPlannableProductsRequest")
        request.plannable_location_id = location
        response = _call(raw, "list_plannable_products", request)
        result = _dict(response)
        result.update({"plannable_location_id": location, "google_allowlisted": True})
        return result

    @mcp.tool()
    def list_reach_plan_user_interests(
        customer_id: str,
        name_query: str | None = None,
        path_query: str | None = None,
        taxonomy_types: list[str] | None = None,
    ) -> dict:
        """List plannable user interests for an allowlisted Reach Plan account."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        raw = ctx.client.raw
        request = raw.get_type("ListPlannableUserInterestsRequest")
        request.customer_id = customer
        if name_query:
            request.name_query = str(name_query).strip()
        if path_query:
            request.path_query = str(path_query).strip()
        normalized = []
        for value in taxonomy_types or []:
            name = str(value).strip().upper()
            if name not in _TAXONOMY_TYPES:
                raise ValueError("taxonomy_types may contain AFFINITY and/or IN_MARKET.")
            request.user_interest_taxonomy_types.append(
                getattr(raw.enums.UserInterestTaxonomyTypeEnum, name)
            )
            normalized.append(name)
        response = _call(raw, "list_plannable_user_interests", request)
        result = _dict(response)
        result.update(
            {
                "customer_id": customer,
                "taxonomy_types": normalized,
                "google_allowlisted": True,
            }
        )
        return result

    @mcp.tool()
    def list_reach_plan_user_lists(
        customer_id: str,
        customer_reach_group: str | None = None,
    ) -> dict:
        """List plannable first-party user lists for Reach Plan."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        raw = ctx.client.raw
        request = raw.get_type("ListPlannableUserListsRequest")
        request.customer_id = customer
        if customer_reach_group:
            request.customer_reach_group = str(customer_reach_group).strip()
        response = _call(raw, "list_plannable_user_lists", request)
        result = _dict(response)
        result.update({"customer_id": customer, "google_allowlisted": True})
        return result

    @mcp.tool()
    def generate_reach_conversion_rates(
        customer_id: str,
        customer_reach_group: str | None = None,
    ) -> dict:
        """Generate Reach Plan conversion-rate estimates for an allowlisted account."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        raw = ctx.client.raw
        request = raw.get_type("GenerateConversionRatesRequest")
        request.customer_id = customer
        if customer_reach_group:
            request.customer_reach_group = str(customer_reach_group).strip()
        response = _call(raw, "generate_conversion_rates", request)
        result = _dict(response)
        result.update({"customer_id": customer, "google_allowlisted": True})
        return result

    @mcp.tool()
    def generate_reach_forecast(
        customer_id: str,
        plannable_location_ids: list[str],
        products: list[dict],
        duration_days: int = 28,
        currency_code: str = "USD",
        devices: list[str] | None = None,
    ) -> dict:
        """Generate a Reach Plan curve for an allowlisted Google Ads account."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        locations = [str(v).strip() for v in plannable_location_ids if str(v).strip()]
        if not locations:
            raise ValueError("Provide at least one plannable_location_id.")
        if not 1 <= duration_days <= 90:
            raise ValueError("duration_days must be between 1 and 90.")
        if not products or len(products) > 15:
            raise ValueError("products must contain between 1 and 15 entries.")

        raw = ctx.client.raw
        request = raw.get_type("GenerateReachForecastRequest")
        request.customer_id = customer
        request.currency_code = currency_code.strip().upper()
        request.campaign_duration.duration_in_days = duration_days
        request.targeting.plannable_location_ids.extend(locations)

        normalized_devices = []
        for value in devices or []:
            name = str(value).strip().upper()
            if name not in _REACH_DEVICES:
                raise ValueError("devices may contain DESKTOP, MOBILE, or TABLET.")
            device = raw.get_type("DeviceInfo")
            device.type_ = getattr(raw.enums.DeviceEnum, name)
            request.targeting.devices.append(device)
            normalized_devices.append(name)

        normalized_products = []
        for payload in products:
            code = str(payload.get("plannable_product_code", "")).strip()
            budget = float(payload.get("budget", 0))
            if not code:
                raise ValueError("Each product requires plannable_product_code.")
            if budget <= 0:
                raise ValueError("Each product requires budget greater than 0.")
            product = raw.get_type("PlannedProduct")
            product.plannable_product_code = code
            product.budget_micros = micros(budget)
            conversion_rate = payload.get("conversion_rate")
            if conversion_rate is not None:
                rate = float(conversion_rate)
                if not 0 < rate < 1:
                    raise ValueError("conversion_rate must be greater than 0 and less than 1.")
                product.conversion_rate = rate
            request.planned_products.append(product)
            normalized_products.append(
                {
                    "plannable_product_code": code,
                    "budget": budget,
                    "conversion_rate": conversion_rate,
                }
            )

        response = _call(raw, "generate_reach_forecast", request)
        result = _dict(response)
        result.update(
            {
                "customer_id": customer,
                "currency_code": request.currency_code,
                "duration_days": duration_days,
                "plannable_location_ids": locations,
                "devices": normalized_devices,
                "products": normalized_products,
                "google_allowlisted": True,
            }
        )
        return result
