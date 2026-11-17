"""Smart Campaign suggestions, settings, and status (API v26).

Google stopped allowing new Smart Campaigns on 2026-09-23: ``create_smart_campaign``
remains registered only to return guidance. Existing Smart Campaigns can still be
read and updated.
"""

from __future__ import annotations

import proto
from google.protobuf import field_mask_pb2

from ..campaign_compat import DEFAULT_EU_POLITICAL_ADVERTISING
from ..context import AppContext
from ..errors import GoogleAdsMcpError, format_google_ads_exception


def _clean_business(
    business_name: str | None,
    business_profile_location: str | None,
) -> tuple[str | None, str | None]:
    name = business_name.strip() if business_name else None
    location = business_profile_location.strip() if business_profile_location else None
    if bool(name) == bool(location):
        raise ValueError(
            "Provide exactly one of business_name or business_profile_location."
        )
    if location and not location.startswith("locations/"):
        raise ValueError(
            "business_profile_location must use the Business Profile resource format "
            "locations/{locationId}."
        )
    return name, location


def _keyword_theme_infos(raw, keyword_themes: list[str] | None):
    infos = []
    for value in keyword_themes or []:
        text = str(value).strip()
        if not text:
            continue
        info = raw.get_type("KeywordThemeInfo")
        if text.startswith("keywordThemeConstants/"):
            info.keyword_theme_constant = text
        else:
            info.free_form_keyword_theme = text
        infos.append(info)
    return infos


def _suggestion_info(
    ctx: AppContext,
    *,
    business_name: str | None,
    business_profile_location: str | None,
    final_url: str | None,
    language_code: str,
    geo_target_ids: list[str] | None,
    keyword_themes: list[str] | None,
):
    raw = ctx.client.raw
    name, location = _clean_business(business_name, business_profile_location)
    info = raw.get_type("SmartCampaignSuggestionInfo")
    if location:
        info.business_profile_location = location
    else:
        info.business_context.business_name = name
    if final_url:
        clean_url = final_url.strip()
        if not clean_url.startswith(("https://", "http://")):
            raise ValueError("final_url must be an http:// or https:// URL.")
        info.final_url = clean_url
    language = language_code.strip().lower()
    if len(language) != 2 or not language.isalpha():
        raise ValueError("language_code must be a two-letter language code such as en or es.")
    info.language_code = language
    geo_service = raw.get_service("GeoTargetConstantService")
    for value in geo_target_ids or []:
        geo_id = str(value).strip()
        if not geo_id.isdigit():
            raise ValueError("geo_target_ids must contain numeric geo target constant IDs.")
        location_info = raw.get_type("LocationInfo")
        location_info.geo_target_constant = geo_service.geo_target_constant_path(geo_id)
        info.location_list.locations.append(location_info)
    for keyword_info in _keyword_theme_infos(raw, keyword_themes):
        info.keyword_themes.append(keyword_info)
    return info


def _google_call(service, method_name: str, **kwargs):
    from google.ads.googleads.errors import GoogleAdsException

    try:
        return getattr(service, method_name)(**kwargs)
    except GoogleAdsException as ex:
        raise GoogleAdsMcpError(format_google_ads_exception(ex)) from ex


def register(mcp, ctx: AppContext) -> None:
    @mcp.tool()
    def suggest_smart_campaign_keyword_themes(
        customer_id: str,
        business_name: str | None = None,
        business_profile_location: str | None = None,
        final_url: str | None = None,
        language_code: str = "en",
        geo_target_ids: list[str] | None = None,
        keyword_themes: list[str] | None = None,
    ) -> dict:
        """Get Smart Campaign keyword-theme suggestions from business context."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        raw = ctx.client.raw
        info = _suggestion_info(
            ctx,
            business_name=business_name,
            business_profile_location=business_profile_location,
            final_url=final_url,
            language_code=language_code,
            geo_target_ids=geo_target_ids,
            keyword_themes=keyword_themes,
        )
        request = raw.get_type("SuggestKeywordThemesRequest")
        request.customer_id = customer
        request.suggestion_info.CopyFrom(info)
        response = _google_call(
            ctx.client.service("SmartCampaignSuggestService"),
            "suggest_keyword_themes",
            request=request,
        )
        themes = [
            proto.Message.to_dict(item, preserving_proto_field_name=True)
            for item in response.keyword_themes
        ]
        return {"keyword_themes": themes, "count": len(themes)}

    @mcp.tool()
    def suggest_smart_campaign_budget(
        customer_id: str,
        campaign_resource_name: str | None = None,
        business_name: str | None = None,
        business_profile_location: str | None = None,
        final_url: str | None = None,
        language_code: str = "en",
        geo_target_ids: list[str] | None = None,
        keyword_themes: list[str] | None = None,
    ) -> dict:
        """Get low/recommended/high Smart Campaign daily budget options."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        raw = ctx.client.raw
        request = raw.get_type("SuggestSmartCampaignBudgetOptionsRequest")
        request.customer_id = customer
        if campaign_resource_name:
            request.campaign = ctx.client.assert_resource_name_customer(
                customer,
                campaign_resource_name,
                field_name="campaign_resource_name",
            )
        else:
            info = _suggestion_info(
                ctx,
                business_name=business_name,
                business_profile_location=business_profile_location,
                final_url=final_url,
                language_code=language_code,
                geo_target_ids=geo_target_ids,
                keyword_themes=keyword_themes,
            )
            request.suggestion_info.CopyFrom(info)
        response = _google_call(
            ctx.client.service("SmartCampaignSuggestService"),
            "suggest_smart_campaign_budget_options",
            request=request,
        )
        return proto.Message.to_dict(response, preserving_proto_field_name=True)

    @mcp.tool()
    def suggest_smart_campaign_ad(
        customer_id: str,
        business_name: str | None = None,
        business_profile_location: str | None = None,
        final_url: str | None = None,
        language_code: str = "en",
        geo_target_ids: list[str] | None = None,
        keyword_themes: list[str] | None = None,
    ) -> dict:
        """Get up to three headline and two description suggestions for a Smart ad."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        raw = ctx.client.raw
        info = _suggestion_info(
            ctx,
            business_name=business_name,
            business_profile_location=business_profile_location,
            final_url=final_url,
            language_code=language_code,
            geo_target_ids=geo_target_ids,
            keyword_themes=keyword_themes,
        )
        request = raw.get_type("SuggestSmartCampaignAdRequest")
        request.customer_id = customer
        request.suggestion_info.CopyFrom(info)
        response = _google_call(
            ctx.client.service("SmartCampaignSuggestService"),
            "suggest_smart_campaign_ad",
            request=request,
        )
        return proto.Message.to_dict(response, preserving_proto_field_name=True)

    @mcp.tool()
    def create_smart_campaign(
        customer_id: str,
        name: str,
        daily_budget: float,
        final_url: str,
        business_name: str | None = None,
        business_profile_location: str | None = None,
        language_code: str = "en",
        country_code: str = "US",
        phone_number: str | None = None,
        geo_target_ids: list[str] | None = None,
        keyword_themes: list[str] | None = None,
        headlines: list[str] | None = None,
        descriptions: list[str] | None = None,
        contains_eu_political_advertising: str = DEFAULT_EU_POLITICAL_ADVERTISING,
    ) -> dict:
        """Smart Campaign creation is no longer available (retired by Google).

        Google Ads stopped allowing new Smart Campaigns on 2026-09-23. This tool
        is kept for compatibility, never mutates anything, and returns guidance.
        Existing Smart Campaigns can still be read and updated with
        ``get_smart_campaign_status``, ``update_smart_campaign_setting`` and the
        normal status/budget tools.
        """
        ctx.client.assert_customer_allowed(customer_id)
        return {
            "status": "unsupported",
            "mutations_executed": 0,
            "reason": (
                "Google Ads no longer allows creating new Smart Campaigns "
                "(effective 2026-09-23); existing ones keep serving and can be updated."
            ),
            "guidance": (
                "Create a Search campaign (create_campaign) or a Performance Max "
                "campaign (create_performance_max_campaign) instead."
            ),
        }

    @mcp.tool()
    def get_smart_campaign_status(customer_id: str, campaign_id: str) -> dict:
        """Return serve eligibility/status details for one Smart Campaign."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        campaign = str(campaign_id).strip()
        if not campaign.isdigit():
            raise ValueError("campaign_id must be numeric.")
        service = ctx.client.service("SmartCampaignSettingService")
        resource = service.smart_campaign_setting_path(customer, campaign)
        response = _google_call(
            service,
            "get_smart_campaign_status",
            resource_name=resource,
        )
        return proto.Message.to_dict(response, preserving_proto_field_name=True)

    @mcp.tool()
    def update_smart_campaign_setting(
        customer_id: str,
        campaign_id: str,
        final_url: str | None = None,
        business_name: str | None = None,
        business_profile_location: str | None = None,
        language_code: str | None = None,
        phone_country_code: str | None = None,
        phone_number: str | None = None,
        include_lead_form: bool | None = None,
    ) -> dict:
        """Propose updating mutable SmartCampaignSetting fields."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        campaign = str(campaign_id).strip()
        if not campaign.isdigit():
            raise ValueError("campaign_id must be numeric.")
        if business_name and business_profile_location:
            raise ValueError(
                "business_name and business_profile_location are mutually exclusive."
            )
        raw = ctx.client.raw
        operation = raw.get_type("SmartCampaignSettingOperation")
        setting = operation.update
        setting.resource_name = raw.get_service(
            "SmartCampaignSettingService"
        ).smart_campaign_setting_path(customer, campaign)
        paths = []
        if final_url is not None:
            url = final_url.strip()
            if not url.startswith(("https://", "http://")):
                raise ValueError("final_url must be an http:// or https:// URL.")
            setting.final_url = url
            paths.append("final_url")
        if business_name is not None:
            clean = business_name.strip()
            if not clean:
                raise ValueError("business_name must not be empty.")
            setting.business_name = clean
            paths.append("business_name")
        if business_profile_location is not None:
            clean = business_profile_location.strip()
            if not clean.startswith("locations/"):
                raise ValueError("business_profile_location must start with locations/.")
            setting.business_profile_location = clean
            paths.append("business_profile_location")
        if language_code is not None:
            language = language_code.strip().lower()
            if len(language) != 2 or not language.isalpha():
                raise ValueError("language_code must be two letters.")
            setting.advertising_language_code = language
            paths.append("advertising_language_code")
        if phone_country_code is not None or phone_number is not None:
            if not phone_country_code or not phone_number:
                raise ValueError(
                    "phone_country_code and phone_number must be supplied together."
                )
            country = phone_country_code.strip().upper()
            if len(country) != 2 or not country.isalpha():
                raise ValueError("phone_country_code must be a two-letter country code.")
            setting.phone_number.country_code = country
            setting.phone_number.phone_number = phone_number.strip()
            paths.append("phone_number")
        if include_lead_form is not None:
            setting.ad_optimized_business_profile_setting.include_lead_form = bool(
                include_lead_form
            )
            paths.append("ad_optimized_business_profile_setting.include_lead_form")
        if not paths:
            raise ValueError("Provide at least one Smart Campaign setting to update.")
        operation.update_mask.CopyFrom(field_mask_pb2.FieldMask(paths=paths))

        def execute():
            return ctx.client.mutate(
                "SmartCampaignSettingService", customer, [operation]
            )

        return ctx.safety.propose(
            tool_name="update_smart_campaign_setting",
            customer_id=customer,
            description=(
                f"Update Smart Campaign setting {setting.resource_name}: {', '.join(paths)}"
            ),
            payload={"campaign_id": campaign, "fields": paths},
            execute=execute,
        )
