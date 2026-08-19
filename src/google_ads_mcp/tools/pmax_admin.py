"""Performance Max administration and shareable preview helpers for API v25."""

from __future__ import annotations

import re

import proto

from ..context import AppContext
from ..errors import GoogleAdsMcpError, format_google_ads_exception

_FONTS = {
    "Open Sans",
    "Roboto",
    "Roboto Slab",
    "Montserrat",
    "Poppins",
    "Lato",
    "Oswald",
    "Playfair Display",
}
_HEX_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")


def _google_call(service, method_name: str, **kwargs):
    from google.ads.googleads.errors import GoogleAdsException

    try:
        return getattr(service, method_name)(**kwargs)
    except GoogleAdsException as ex:
        raise GoogleAdsMcpError(format_google_ads_exception(ex)) from ex


def _brand_options(
    *,
    main_color: str | None,
    accent_color: str | None,
    font_family: str | None,
) -> tuple[str | None, str | None, str | None]:
    if bool(main_color) != bool(accent_color):
        raise ValueError("main_color and accent_color must be supplied together.")
    if main_color and not _HEX_COLOR.fullmatch(main_color):
        raise ValueError("main_color must be a six-digit hex color such as #00ff00.")
    if accent_color and not _HEX_COLOR.fullmatch(accent_color):
        raise ValueError("accent_color must be a six-digit hex color such as #00ff00.")
    if font_family is not None and font_family not in _FONTS:
        raise ValueError("font_family must be one of: " + ", ".join(sorted(_FONTS)))
    return main_color, accent_color, font_family


def register(mcp, ctx: AppContext) -> None:
    @mcp.tool()
    def get_pmax_brand_guidelines(customer_id: str, campaign_id: str) -> dict:
        """Read Performance Max brand-guideline status and visual settings."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        campaign = str(campaign_id).strip()
        if not campaign.isdigit():
            raise ValueError("campaign_id must be numeric.")
        rows = ctx.client.search(
            customer,
            f"""
            SELECT
                campaign.resource_name,
                campaign.name,
                campaign.advertising_channel_type,
                campaign.brand_guidelines_enabled,
                campaign.brand_guidelines.main_color,
                campaign.brand_guidelines.accent_color,
                campaign.brand_guidelines.predefined_font_family
            FROM campaign
            WHERE campaign.id = {campaign}
            LIMIT 1
            """,
        )
        return {"campaign": rows[0] if rows else None, "found": bool(rows)}

    @mcp.tool()
    def enable_pmax_brand_guidelines(
        customer_id: str,
        campaign_id: str,
        auto_populate_brand_assets: bool = True,
        business_name_asset_resource_name: str | None = None,
        logo_asset_resource_names: list[str] | None = None,
        landscape_logo_asset_resource_names: list[str] | None = None,
        final_uri_domain: str | None = None,
        main_color: str | None = None,
        accent_color: str | None = None,
        font_family: str | None = None,
    ) -> dict:
        """Propose enabling Brand Guidelines on an existing PMax campaign.

        This operation is one-way: Google Ads does not support disabling Brand
        Guidelines on an existing campaign after enablement. When
        ``auto_populate_brand_assets`` is false, provide exactly one business-name
        text asset and at least one square logo asset already owned by this customer.
        """
        customer = ctx.client.assert_customer_allowed(customer_id)
        campaign = str(campaign_id).strip()
        if not campaign.isdigit():
            raise ValueError("campaign_id must be numeric.")
        main, accent, font = _brand_options(
            main_color=main_color,
            accent_color=accent_color,
            font_family=font_family,
        )
        if final_uri_domain is not None:
            domain = final_uri_domain.strip()
            if not domain or "/" in domain or ":" in domain:
                raise ValueError(
                    "final_uri_domain must be a bare domain such as example.com."
                )
        else:
            domain = None

        business_asset = None
        logos: list[str] = []
        landscape_logos: list[str] = []
        if not auto_populate_brand_assets:
            if not business_name_asset_resource_name:
                raise ValueError(
                    "business_name_asset_resource_name is required when "
                    "auto_populate_brand_assets=false."
                )
            if not logo_asset_resource_names:
                raise ValueError(
                    "At least one logo_asset_resource_name is required when "
                    "auto_populate_brand_assets=false."
                )
            business_asset = ctx.client.assert_resource_name_customer(
                customer,
                business_name_asset_resource_name,
                field_name="business_name_asset_resource_name",
            )
            logos = [
                ctx.client.assert_resource_name_customer(
                    customer, value, field_name="logo_asset_resource_names"
                )
                for value in logo_asset_resource_names
            ]
            landscape_logos = [
                ctx.client.assert_resource_name_customer(
                    customer, value, field_name="landscape_logo_asset_resource_names"
                )
                for value in landscape_logo_asset_resource_names or []
            ]

        raw = ctx.client.raw
        request = raw.get_type("EnablePMaxBrandGuidelinesRequest")
        request.customer_id = customer
        operation = raw.get_type("EnableOperation")
        operation.campaign = raw.get_service("CampaignService").campaign_path(
            customer, campaign
        )
        operation.auto_populate_brand_assets = bool(auto_populate_brand_assets)
        if not auto_populate_brand_assets:
            operation.brand_assets.business_name_asset = business_asset
            operation.brand_assets.logo_asset.extend(logos)
            operation.brand_assets.landscape_logo_asset.extend(landscape_logos)
        if domain:
            operation.final_uri_domain = domain
        if main:
            operation.main_color = main
            operation.accent_color = accent
        if font:
            operation.font_family = font
        request.operations.append(operation)
        service = ctx.client.service("CampaignService")

        def execute():
            response = _google_call(
                service,
                "enable_p_max_brand_guidelines",
                request=request,
            )
            return proto.Message.to_dict(response, preserving_proto_field_name=True)

        return ctx.safety.propose(
            tool_name="enable_pmax_brand_guidelines",
            customer_id=customer,
            description=(
                f"Enable Brand Guidelines for PMax campaign {campaign} "
                f"(auto assets={bool(auto_populate_brand_assets)})"
            ),
            payload={
                "campaign_id": campaign,
                "auto_populate_brand_assets": bool(auto_populate_brand_assets),
                "business_name_asset_resource_name": business_asset,
                "logo_asset_count": len(logos),
                "landscape_logo_asset_count": len(landscape_logos),
                "final_uri_domain": domain,
                "main_color": main,
                "accent_color": accent,
                "font_family": font,
            },
            execute=execute,
        )

    @mcp.tool()
    def generate_pmax_shareable_previews(
        customer_id: str,
        asset_group_resource_names: list[str],
    ) -> dict:
        """Generate shareable Google Ads UI preview URLs for PMax asset groups."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        if not asset_group_resource_names:
            raise ValueError("Provide at least one asset_group_resource_name.")
        if len(asset_group_resource_names) > 20:
            raise ValueError("Generate at most 20 previews per MCP call.")
        resources = [
            ctx.client.assert_resource_name_customer(
                customer, value, field_name="asset_group_resource_names"
            )
            for value in asset_group_resource_names
        ]
        raw = ctx.client.raw
        request = raw.get_type("GenerateShareablePreviewsRequest")
        request.customer_id = customer
        operation = raw.get_type("GenerateShareablePreviewsOperation")
        for resource in resources:
            preview = raw.get_type("ShareablePreview")
            preview.asset_group = resource
            preview.preview_type = raw.enums.PreviewTypeEnum.UI_PREVIEW
            operation.shareable_previews.append(preview)
        request.operation.CopyFrom(operation)
        response = _google_call(
            ctx.client.service("ShareablePreviewService"),
            "generate_shareable_previews",
            request=request,
        )
        return proto.Message.to_dict(response, preserving_proto_field_name=True)

    @mcp.tool()
    def generate_youtube_live_previews(
        customer_id: str,
        ad_group_ad_resource_names: list[str],
    ) -> dict:
        """Generate shareable YouTube live previews for supported video/audio ads."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        if not ad_group_ad_resource_names:
            raise ValueError("Provide at least one ad_group_ad_resource_name.")
        if len(ad_group_ad_resource_names) > 20:
            raise ValueError("Generate at most 20 previews per MCP call.")
        resources = [
            ctx.client.assert_resource_name_customer(
                customer, value, field_name="ad_group_ad_resource_names"
            )
            for value in ad_group_ad_resource_names
        ]
        raw = ctx.client.raw
        request = raw.get_type("GenerateShareablePreviewsRequest")
        request.customer_id = customer
        operation = raw.get_type("GenerateShareablePreviewsOperation")
        for resource in resources:
            preview = raw.get_type("ShareablePreview")
            preview.ad_group_ad = resource
            preview.preview_type = raw.enums.PreviewTypeEnum.YOUTUBE_LIVE_PREVIEW
            operation.shareable_previews.append(preview)
        request.operation.CopyFrom(operation)
        response = _google_call(
            ctx.client.service("ShareablePreviewService"),
            "generate_shareable_previews",
            request=request,
        )
        return proto.Message.to_dict(response, preserving_proto_field_name=True)
