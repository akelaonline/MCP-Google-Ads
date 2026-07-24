"""Campaign-level assets: sitelinks, call assets, and message assets.

These are the pieces that let an ad push the user straight into a
conversation (WhatsApp/SMS via Message Asset, a phone call via Call Asset,
or a specific landing section via Sitelink) instead of relying entirely on
the landing page to carry the user to the actual point of contact.

Each `create_*_asset` tool does the two-step Google Ads dance in one call:
1. Create the Asset itself (AssetService).
2. Link it to the campaign (CampaignAssetService).

Both mutate calls execute together inside the single `execute()` the
safety layer confirms — so a confirm either creates+links the asset, or
does nothing at all.
"""

from __future__ import annotations

from ..context import AppContext


def register(mcp, ctx: AppContext) -> None:
    @mcp.tool()
    def create_sitelink_asset(
        customer_id: str,
        campaign_id: str,
        link_text: str,
        final_url: str,
        description1: str | None = None,
        description2: str | None = None,
    ) -> dict:
        """Propose creating a sitelink and attaching it to a campaign.

        Args:
            link_text: Sitelink label, <=25 characters (e.g. "Escribinos por WhatsApp").
            final_url: Landing URL for the sitelink.
            description1 / description2: Optional lines, <=35 characters each.
        """
        if len(link_text) > 25:
            raise ValueError("link_text must be 25 characters or fewer.")
        for label, text in [("description1", description1), ("description2", description2)]:
            if text and len(text) > 35:
                raise ValueError(f"{label} must be 35 characters or fewer.")

        client = ctx.client.raw
        customer_id_clean = customer_id.replace("-", "")

        asset_operation = client.get_type("AssetOperation")
        asset = asset_operation.create
        asset.sitelink_asset.link_text = link_text
        asset.final_urls.append(final_url)
        if description1:
            asset.sitelink_asset.description1 = description1
        if description2:
            asset.sitelink_asset.description2 = description2

        campaign_resource_name = client.get_service("CampaignService").campaign_path(
            customer_id_clean, campaign_id
        )

        description = (
            f"Create sitelink '{link_text}' -> {final_url} and attach to campaign {campaign_id}"
        )

        def execute():
            asset_result = ctx.client.mutate("AssetService", customer_id, [asset_operation])
            asset_resource_name = asset_result.results[0].resource_name

            campaign_asset_operation = client.get_type("CampaignAssetOperation")
            campaign_asset = campaign_asset_operation.create
            campaign_asset.campaign = campaign_resource_name
            campaign_asset.asset = asset_resource_name
            campaign_asset.field_type = client.enums.AssetFieldTypeEnum.SITELINK

            link_result = ctx.client.mutate(
                "CampaignAssetService", customer_id, [campaign_asset_operation]
            )
            return {
                "asset_resource_name": asset_resource_name,
                "campaign_asset_resource_name": link_result.results[0].resource_name,
            }

        return ctx.safety.propose(
            tool_name="create_sitelink_asset",
            customer_id=customer_id,
            description=description,
            payload={
                "campaign_id": campaign_id,
                "link_text": link_text,
                "final_url": final_url,
                "description1": description1,
                "description2": description2,
            },
            execute=execute,
        )

    @mcp.tool()
    def create_call_asset(
        customer_id: str,
        campaign_id: str,
        phone_number: str,
        country_code: str = "AR",
    ) -> dict:
        """Propose creating a call asset (click-to-call extension) and attaching it
        to a campaign.

        Args:
            phone_number: Full phone number, e.g. "+541112345678".
            country_code: ISO 3166-1 alpha-2, e.g. "AR" for Argentina.
        """
        client = ctx.client.raw
        customer_id_clean = customer_id.replace("-", "")

        asset_operation = client.get_type("AssetOperation")
        asset = asset_operation.create
        asset.call_asset.phone_number = phone_number
        asset.call_asset.country_code = country_code

        campaign_resource_name = client.get_service("CampaignService").campaign_path(
            customer_id_clean, campaign_id
        )

        description = (
            f"Create call asset {phone_number} ({country_code}) and attach to "
            f"campaign {campaign_id}"
        )

        def execute():
            asset_result = ctx.client.mutate("AssetService", customer_id, [asset_operation])
            asset_resource_name = asset_result.results[0].resource_name

            campaign_asset_operation = client.get_type("CampaignAssetOperation")
            campaign_asset = campaign_asset_operation.create
            campaign_asset.campaign = campaign_resource_name
            campaign_asset.asset = asset_resource_name
            campaign_asset.field_type = client.enums.AssetFieldTypeEnum.CALL

            link_result = ctx.client.mutate(
                "CampaignAssetService", customer_id, [campaign_asset_operation]
            )
            return {
                "asset_resource_name": asset_resource_name,
                "campaign_asset_resource_name": link_result.results[0].resource_name,
            }

        return ctx.safety.propose(
            tool_name="create_call_asset",
            customer_id=customer_id,
            description=description,
            payload={
                "campaign_id": campaign_id,
                "phone_number": phone_number,
                "country_code": country_code,
            },
            execute=execute,
        )

    @mcp.tool()
    def create_message_asset(
        customer_id: str,
        campaign_id: str,
        phone_number: str,
        country_code: str,
        business_name: str,
        message_text: str,
        call_to_action_text: str = "Escribinos",
    ) -> dict:
        """Propose creating a message asset (click-to-message, e.g. WhatsApp/SMS)
        and attaching it to a campaign.

        This is the extension that lets a Search ad open a chat directly —
        no dependency on the landing page having a working WhatsApp button.

        Args:
            phone_number: Number the message opens a chat with, e.g. "1112345678"
                (no country code prefix — that's the separate country_code arg).
            country_code: ISO 3166-1 alpha-2, e.g. "AR".
            business_name: Shown to the user before they message you.
            message_text: Pre-filled text the user's message opens with,
                <=35 characters (Google Ads limit).
            call_to_action_text: Button label, e.g. "Escribinos por WhatsApp".
        """
        if len(message_text) > 35:
            raise ValueError("message_text must be 35 characters or fewer.")

        client = ctx.client.raw
        customer_id_clean = customer_id.replace("-", "")

        asset_operation = client.get_type("AssetOperation")
        asset = asset_operation.create
        asset.message_asset.business_name = business_name
        asset.message_asset.country_code = country_code
        asset.message_asset.phone_number = phone_number
        asset.message_asset.message_text = message_text
        asset.message_asset.call_to_action_text = call_to_action_text
        asset.message_asset.extension_text = message_text

        campaign_resource_name = client.get_service("CampaignService").campaign_path(
            customer_id_clean, campaign_id
        )

        description = (
            f"Create message asset ({business_name}, {country_code}{phone_number}) and "
            f"attach to campaign {campaign_id}"
        )

        def execute():
            asset_result = ctx.client.mutate("AssetService", customer_id, [asset_operation])
            asset_resource_name = asset_result.results[0].resource_name

            campaign_asset_operation = client.get_type("CampaignAssetOperation")
            campaign_asset = campaign_asset_operation.create
            campaign_asset.campaign = campaign_resource_name
            campaign_asset.asset = asset_resource_name
            campaign_asset.field_type = client.enums.AssetFieldTypeEnum.MESSAGE

            link_result = ctx.client.mutate(
                "CampaignAssetService", customer_id, [campaign_asset_operation]
            )
            return {
                "asset_resource_name": asset_resource_name,
                "campaign_asset_resource_name": link_result.results[0].resource_name,
            }

        return ctx.safety.propose(
            tool_name="create_message_asset",
            customer_id=customer_id,
            description=description,
            payload={
                "campaign_id": campaign_id,
                "phone_number": phone_number,
                "country_code": country_code,
                "business_name": business_name,
                "message_text": message_text,
                "call_to_action_text": call_to_action_text,
            },
            execute=execute,
        )

    @mcp.tool()
    def list_campaign_assets(customer_id: str, campaign_id: str) -> dict:
        """List assets currently attached to a campaign (sitelinks, calls,
        messages, images, etc.), with their status."""
        query = f"""
            SELECT campaign_asset.asset, campaign_asset.field_type,
                   campaign_asset.status, asset.type,
                   asset.sitelink_asset.link_text,
                   asset.call_asset.phone_number,
                   asset.message_asset.business_name,
                   asset.message_asset.phone_number
            FROM campaign_asset
            WHERE campaign.id = {campaign_id}
        """
        rows = ctx.client.search(customer_id, query)
        return {"campaign_id": campaign_id, "assets": rows, "count": len(rows)}

    @mcp.tool()
    def remove_campaign_asset(
        customer_id: str, campaign_id: str, asset_id: str, field_type: str
    ) -> dict:
        """Propose detaching an asset (sitelink/call/message/etc.) from a campaign.

        Args:
            field_type: The AssetFieldType the asset is linked as (e.g. SITELINK,
                CALL, MESSAGE) — must match how it was attached.
        """
        client = ctx.client.raw
        customer_id_clean = customer_id.replace("-", "")

        campaign_resource_name = client.get_service("CampaignService").campaign_path(
            customer_id_clean, campaign_id
        )
        asset_resource_name = client.get_service("AssetService").asset_path(
            customer_id_clean, asset_id
        )
        field_type_enum = client.enums.AssetFieldTypeEnum[field_type].value

        operation = client.get_type("CampaignAssetOperation")
        operation.remove = client.get_service("CampaignAssetService").campaign_asset_path(
            customer_id_clean, campaign_id, asset_id, field_type_enum
        )

        description = (
            f"Detach {field_type} asset {asset_id} from campaign {campaign_id}"
        )

        def execute():
            return ctx.client.mutate("CampaignAssetService", customer_id, [operation])

        return ctx.safety.propose(
            tool_name="remove_campaign_asset",
            customer_id=customer_id,
            description=description,
            payload={"campaign_id": campaign_id, "asset_id": asset_id, "field_type": field_type},
            execute=execute,
        )
