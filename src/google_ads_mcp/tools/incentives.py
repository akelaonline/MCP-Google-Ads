"""Allowlisted Google Ads IncentiveService workflows for API v25."""

from __future__ import annotations

import proto
from google.ads.googleads.errors import GoogleAdsException

from ..context import AppContext
from ..errors import GoogleAdsMcpError, format_google_ads_exception

_ALLOWLIST_NOTE = (
    " IncentiveService is available only to users allowlisted by Google; "
    "an otherwise valid authorization error may mean this integration is not allowlisted."
)


def register(mcp, ctx: AppContext) -> None:
    @mcp.tool()
    def fetch_incentive(
        language_code: str = "en",
        country_code: str = "US",
        email: str | None = None,
        incentive_type: str = "ACQUISITION",
    ) -> dict:
        """Fetch an available Google Ads incentive (Google allowlist required)."""
        language = _language(language_code)
        country = _country(country_code)
        raw = ctx.client.raw
        request = raw.get_type("FetchIncentiveRequest")
        request.language_code = language
        request.country_code = country
        if email is not None:
            address = email.strip().lower()
            if not address or "@" not in address:
                raise ValueError("email must be a valid non-empty email address.")
            request.email = address
        kind = incentive_type.strip().upper()
        if kind in {"", "UNKNOWN", "UNSPECIFIED"}:
            raise ValueError("incentive_type must be a concrete IncentiveType enum name.")
        try:
            request.incentive_type = getattr(raw.enums.IncentiveTypeEnum, kind)
        except AttributeError as ex:
            raise ValueError(f"Unknown IncentiveType {kind!r} for v25.") from ex
        try:
            response = raw.get_service("IncentiveService").fetch_incentive(
                request=request
            )
        except GoogleAdsException as ex:
            raise GoogleAdsMcpError(
                format_google_ads_exception(ex) + _ALLOWLIST_NOTE
            ) from ex
        result = proto.Message.to_dict(
            response,
            preserving_proto_field_name=True,
            use_integers_for_enums=False,
        )
        result.update(
            {
                "language_code": language,
                "country_code": country,
                "incentive_type": kind,
                "google_allowlisted": True,
            }
        )
        return result

    @mcp.tool()
    def apply_incentive(
        customer_id: str,
        selected_incentive_id: str,
        country_code: str,
    ) -> dict:
        """Propose applying a fetched incentive (Google allowlist required)."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        incentive_id = int(_positive_id(selected_incentive_id, "selected_incentive_id"))
        country = _country(country_code)

        def execute():
            raw = ctx.client.raw
            request = raw.get_type("ApplyIncentiveRequest")
            request.selected_incentive_id = incentive_id
            request.customer_id = customer
            request.country_code = country
            try:
                response = raw.get_service("IncentiveService").apply_incentive(
                    request=request
                )
            except GoogleAdsException as ex:
                raise GoogleAdsMcpError(
                    format_google_ads_exception(ex) + _ALLOWLIST_NOTE
                ) from ex
            return {
                "selected_incentive_id": str(incentive_id),
                "coupon_code": response.coupon_code,
                "creation_time": response.creation_time,
                "google_allowlisted": True,
            }

        return ctx.safety.propose(
            tool_name="apply_incentive",
            customer_id=customer,
            description=(
                f"Apply Google Ads incentive {incentive_id} to customer {customer} "
                f"for billing country {country}"
            ),
            payload={
                "selected_incentive_id": str(incentive_id),
                "country_code": country,
            },
            execute=execute,
        )


def _country(value: str) -> str:
    code = value.strip().upper()
    if len(code) != 2 or not code.isalpha():
        raise ValueError("country_code must be a two-letter country code.")
    return code


def _language(value: str) -> str:
    code = value.strip().lower()
    if not code or not all(part.isalpha() for part in code.split("-")):
        raise ValueError("language_code must be a language code such as en or es.")
    return code


def _positive_id(value: str, name: str) -> str:
    try:
        number = int(str(value).strip())
    except ValueError as ex:
        raise ValueError(f"{name} must be numeric.") from ex
    if number <= 0:
        raise ValueError(f"{name} must be greater than 0.")
    return str(number)
