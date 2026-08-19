"""Smart Campaign suggestions, atomic creation, settings, and status for API v25."""

from __future__ import annotations

import proto
from google.protobuf import field_mask_pb2

from ..campaign_compat import DEFAULT_EU_POLITICAL_ADVERTISING, apply_required_campaign_fields
from ..client import micros
from ..context import AppContext
from ..errors import GoogleAdsMcpError, format_google_ads_exception

_BUDGET_TEMP_ID = "-1"
_CAMPAIGN_TEMP_ID = "-2"
_AD_GROUP_TEMP_ID = "-3"


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
        """Propose atomically creating a complete PAUSED Smart Campaign.

        Budget, campaign, SmartCampaignSetting, targeting criteria, single ad group,
        and Smart Campaign ad are created in one GoogleAdsService.Mutate request.
        Supply at least 3 non-empty headlines and 2 descriptions after reviewing
        SmartCampaignSuggestService output or writing your own.
        """
        customer = ctx.client.assert_customer_allowed(customer_id)
        campaign_name = name.strip()
        if not campaign_name:
            raise ValueError("name must not be empty.")
        if daily_budget <= 0:
            raise ValueError("daily_budget must be greater than 0.")
        url = final_url.strip()
        if not url.startswith(("https://", "http://")):
            raise ValueError("final_url must be an http:// or https:// URL.")
        business, profile = _clean_business(business_name, business_profile_location)
        language = language_code.strip().lower()
        if len(language) != 2 or not language.isalpha():
            raise ValueError("language_code must be a two-letter code such as en or es.")
        country = country_code.strip().upper()
        if len(country) != 2 or not country.isalpha():
            raise ValueError("country_code must be a two-letter ISO-3166 code.")
        clean_headlines = [str(v).strip() for v in headlines or [] if str(v).strip()]
        clean_descriptions = [str(v).strip() for v in descriptions or [] if str(v).strip()]
        if len(clean_headlines) < 3:
            raise ValueError("Smart Campaign ads require at least 3 non-empty headlines.")
        if len(clean_descriptions) < 2:
            raise ValueError("Smart Campaign ads require at least 2 non-empty descriptions.")
        keyword_infos = _keyword_theme_infos(ctx.client.raw, keyword_themes)
        if not keyword_infos:
            raise ValueError("Provide at least one keyword theme.")
        if not geo_target_ids:
            raise ValueError("Provide at least one geo_target_id.")

        raw = ctx.client.raw
        operations = []
        campaign_budget_service = raw.get_service("CampaignBudgetService")
        campaign_service = raw.get_service("CampaignService")
        smart_setting_service = raw.get_service("SmartCampaignSettingService")
        ad_group_service = raw.get_service("AdGroupService")
        geo_service = raw.get_service("GeoTargetConstantService")

        # Budget.
        op = raw.get_type("MutateOperation")
        budget = op.campaign_budget_operation.create
        budget.name = f"{campaign_name} budget"
        budget.amount_micros = micros(daily_budget)
        budget.delivery_method = raw.enums.BudgetDeliveryMethodEnum.STANDARD
        budget.type_ = raw.enums.BudgetTypeEnum.SMART_CAMPAIGN
        budget.resource_name = campaign_budget_service.campaign_budget_path(
            customer, _BUDGET_TEMP_ID
        )
        operations.append(op)

        # Campaign.
        op = raw.get_type("MutateOperation")
        campaign = op.campaign_operation.create
        campaign.name = campaign_name
        campaign.status = raw.enums.CampaignStatusEnum.PAUSED
        campaign.advertising_channel_type = raw.enums.AdvertisingChannelTypeEnum.SMART
        campaign.advertising_channel_sub_type = (
            raw.enums.AdvertisingChannelSubTypeEnum.SMART_CAMPAIGN
        )
        campaign.resource_name = campaign_service.campaign_path(customer, _CAMPAIGN_TEMP_ID)
        campaign.campaign_budget = campaign_budget_service.campaign_budget_path(
            customer, _BUDGET_TEMP_ID
        )
        apply_required_campaign_fields(
            raw,
            campaign,
            contains_eu_political_advertising=contains_eu_political_advertising,
        )
        operations.append(op)

        # SmartCampaignSetting is created via UPDATE.
        op = raw.get_type("MutateOperation")
        setting = op.smart_campaign_setting_operation.update
        setting.resource_name = smart_setting_service.smart_campaign_setting_path(
            customer, _CAMPAIGN_TEMP_ID
        )
        setting.final_url = url
        setting.advertising_language_code = language
        if profile:
            setting.business_profile_location = profile
        else:
            setting.business_name = business
        setting_paths = ["final_url", "advertising_language_code"]
        setting_paths.append("business_profile_location" if profile else "business_name")
        if phone_number:
            setting.phone_number.country_code = country
            setting.phone_number.phone_number = phone_number.strip()
            setting_paths.append("phone_number")
        op.smart_campaign_setting_operation.update_mask.CopyFrom(
            field_mask_pb2.FieldMask(paths=setting_paths)
        )
        operations.append(op)

        # Keyword themes.
        for keyword_info in keyword_infos:
            op = raw.get_type("MutateOperation")
            criterion = op.campaign_criterion_operation.create
            criterion.campaign = campaign_service.campaign_path(customer, _CAMPAIGN_TEMP_ID)
            criterion.keyword_theme.CopyFrom(keyword_info)
            operations.append(op)

        # Locations.
        for value in geo_target_ids:
            geo_id = str(value).strip()
            if not geo_id.isdigit():
                raise ValueError("geo_target_ids must contain numeric IDs.")
            op = raw.get_type("MutateOperation")
            criterion = op.campaign_criterion_operation.create
            criterion.campaign = campaign_service.campaign_path(customer, _CAMPAIGN_TEMP_ID)
            criterion.location.geo_target_constant = geo_service.geo_target_constant_path(geo_id)
            operations.append(op)

        # Single Smart Campaign ad group.
        op = raw.get_type("MutateOperation")
        ad_group = op.ad_group_operation.create
        ad_group.resource_name = ad_group_service.ad_group_path(customer, _AD_GROUP_TEMP_ID)
        ad_group.name = f"{campaign_name} ad group"
        ad_group.campaign = campaign_service.campaign_path(customer, _CAMPAIGN_TEMP_ID)
        ad_group.type_ = raw.enums.AdGroupTypeEnum.SMART_CAMPAIGN_ADS
        operations.append(op)

        # Smart Campaign ad.
        op = raw.get_type("MutateOperation")
        ad_group_ad = op.ad_group_ad_operation.create
        ad_group_ad.ad_group = ad_group_service.ad_group_path(customer, _AD_GROUP_TEMP_ID)
        ad_group_ad.ad.type_ = raw.enums.AdTypeEnum.SMART_CAMPAIGN_AD
        for text in clean_headlines:
            asset = raw.get_type("AdTextAsset")
            asset.text = text
            ad_group_ad.ad.smart_campaign_ad.headlines.append(asset)
        for text in clean_descriptions:
            asset = raw.get_type("AdTextAsset")
            asset.text = text
            ad_group_ad.ad.smart_campaign_ad.descriptions.append(asset)
        operations.append(op)

        def execute():
            return ctx.client.mutate_atomic(customer, operations)

        return ctx.safety.propose(
            tool_name="create_smart_campaign",
            customer_id=customer,
            description=(
                f"Atomically create complete Smart Campaign '{campaign_name}' PAUSED "
                f"with daily budget {daily_budget}"
            ),
            payload={
                "name": campaign_name,
                "daily_budget": daily_budget,
                "final_url": url,
                "business_name": business,
                "business_profile_location": profile,
                "language_code": language,
                "country_code": country,
                "geo_target_ids": [str(v) for v in geo_target_ids],
                "keyword_theme_count": len(keyword_infos),
                "headline_count": len(clean_headlines),
                "description_count": len(clean_descriptions),
                "contains_eu_political_advertising": contains_eu_political_advertising,
            },
            execute=execute,
        )

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
