"""Campaign-level assets compatible with Google Ads API v25."""

from __future__ import annotations

from ..context import AppContext
from ..net import fetch_public_https_image


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
        """Propose creating a sitelink and attaching it atomically to a campaign."""
        if not link_text or len(link_text) > 25:
            raise ValueError("link_text must be 1-25 characters.")
        for label, text in (("description1", description1), ("description2", description2)):
            if text and len(text) > 35:
                raise ValueError(f"{label} must be 35 characters or fewer.")
        if not final_url:
            raise ValueError("final_url is required.")

        client = ctx.client.raw
        asset_operation = client.get_type("AssetOperation")
        asset = asset_operation.create
        asset.sitelink_asset.link_text = link_text
        asset.final_urls.append(final_url)
        if description1:
            asset.sitelink_asset.description1 = description1
        if description2:
            asset.sitelink_asset.description2 = description2

        description = (
            f"Create sitelink '{link_text}' -> {final_url} and attach to campaign "
            f"{campaign_id} atomically"
        )

        def execute():
            return _create_asset_and_attach_to_campaign(
                ctx,
                customer_id,
                campaign_id,
                asset_operation,
                "SITELINK",
            )

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
        """Propose creating a call asset and attaching it atomically."""
        if not phone_number.strip():
            raise ValueError("phone_number is required.")
        if len(country_code) != 2:
            raise ValueError("country_code must be a two-letter code.")

        client = ctx.client.raw
        asset_operation = client.get_type("AssetOperation")
        asset_operation.create.call_asset.phone_number = phone_number
        asset_operation.create.call_asset.country_code = country_code.upper()
        description = (
            f"Create call asset {phone_number} ({country_code.upper()}) and attach "
            f"to campaign {campaign_id} atomically"
        )

        def execute():
            return _create_asset_and_attach_to_campaign(
                ctx,
                customer_id,
                campaign_id,
                asset_operation,
                "CALL",
            )

        return ctx.safety.propose(
            tool_name="create_call_asset",
            customer_id=customer_id,
            description=description,
            payload={
                "campaign_id": campaign_id,
                "phone_number": phone_number,
                "country_code": country_code.upper(),
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
        """Create the v25 Business Message asset replacement using WhatsApp.

        The old ``message_asset`` resource was removed. This compatibility tool
        keeps its public name/signature and creates a ``business_message_asset``
        with WhatsApp provider, then links it to the campaign as BUSINESS_MESSAGE
        in the same atomic mutation.
        """
        if not message_text or len(message_text) > 300:
            raise ValueError("message_text must be 1-300 characters.")
        if len(country_code) != 2:
            raise ValueError("country_code must be a two-letter code.")
        if not phone_number.strip():
            raise ValueError("phone_number is required.")
        if not call_to_action_text or len(call_to_action_text) > 30:
            raise ValueError("call_to_action_text must be 1-30 characters.")

        client = ctx.client.raw
        asset_operation = client.get_type("AssetOperation")
        business_message = asset_operation.create.business_message_asset
        business_message.message_provider = (
            client.enums.BusinessMessageProviderEnum.WHATSAPP.value
        )
        business_message.starter_message = message_text
        business_message.whatsapp_info.country_code = country_code.upper()
        business_message.whatsapp_info.phone_number = phone_number
        business_message.call_to_action.call_to_action_selection = (
            client.enums.BusinessMessageCallToActionTypeEnum.CONTACT_US.value
        )
        business_message.call_to_action.call_to_action_description = call_to_action_text

        description = (
            f"Create WhatsApp Business Message asset ({business_name}, "
            f"{country_code.upper()}{phone_number}) and attach to campaign "
            f"{campaign_id} atomically"
        )

        def execute():
            return _create_asset_and_attach_to_campaign(
                ctx,
                customer_id,
                campaign_id,
                asset_operation,
                "BUSINESS_MESSAGE",
            )

        return ctx.safety.propose(
            tool_name="create_message_asset",
            customer_id=customer_id,
            description=description,
            payload={
                "compatibility_mode": "BUSINESS_MESSAGE_WHATSAPP",
                "campaign_id": campaign_id,
                "phone_number": phone_number,
                "country_code": country_code.upper(),
                "business_name": business_name,
                "message_text": message_text,
                "call_to_action_text": call_to_action_text,
            },
            execute=execute,
        )

    @mcp.tool()
    def create_image_asset(
        customer_id: str,
        campaign_id: str,
        image_url: str,
        name: str,
    ) -> dict:
        """Propose uploading a public HTTPS image and attaching it atomically."""
        if not name.strip():
            raise ValueError("name is required.")
        description = (
            f"Upload image '{name}' from {image_url} and attach to campaign "
            f"{campaign_id} atomically"
        )

        def execute():
            image_bytes = fetch_public_https_image(image_url)
            client = ctx.client.raw
            asset_operation = client.get_type("AssetOperation")
            asset_operation.create.name = name
            asset_operation.create.image_asset.data = image_bytes
            # v25 AssetFieldType has no "IMAGE" value; marketing images are
            # linked with MARKETING_IMAGE.
            return _create_asset_and_attach_to_campaign(
                ctx,
                customer_id,
                campaign_id,
                asset_operation,
                "MARKETING_IMAGE",
            )

        return ctx.safety.propose(
            tool_name="create_image_asset",
            customer_id=customer_id,
            description=description,
            payload={"campaign_id": campaign_id, "image_url": image_url, "name": name},
            execute=execute,
        )

    @mcp.tool()
    def create_promotion_asset(
        customer_id: str,
        campaign_id: str,
        promotion_target: str,
        discount_percent: float | None = None,
        money_amount_off: float | None = None,
        currency_code: str = "ARS",
        promotion_code: str | None = None,
        final_url: str | None = None,
    ) -> dict:
        """Propose creating a promotion asset and attaching it atomically."""
        if (discount_percent is None) == (money_amount_off is None):
            raise ValueError(
                "Provide exactly one of discount_percent or money_amount_off."
            )
        if discount_percent is not None and not (0 < discount_percent <= 100):
            raise ValueError("discount_percent must be greater than 0 and at most 100.")
        if money_amount_off is not None and money_amount_off <= 0:
            raise ValueError("money_amount_off must be greater than 0.")
        if not promotion_target:
            raise ValueError("promotion_target is required.")

        client = ctx.client.raw
        asset_operation = client.get_type("AssetOperation")
        asset = asset_operation.create
        asset.promotion_asset.promotion_target = promotion_target
        asset.promotion_asset.currency_code = currency_code.upper()
        if discount_percent is not None:
            asset.promotion_asset.percent_off = int(discount_percent * 1_000_000)
        else:
            from ..client import micros

            asset.promotion_asset.money_amount_off.amount_micros = micros(
                money_amount_off
            )
            asset.promotion_asset.money_amount_off.currency_code = currency_code.upper()
        if promotion_code:
            asset.promotion_asset.promotion_code = promotion_code
        if final_url:
            asset.final_urls.append(final_url)

        discount_label = (
            f"{discount_percent}% off"
            if discount_percent is not None
            else f"{money_amount_off} {currency_code.upper()} off"
        )
        description = (
            f"Create promotion asset '{promotion_target}' ({discount_label}) and "
            f"attach to campaign {campaign_id} atomically"
        )

        def execute():
            return _create_asset_and_attach_to_campaign(
                ctx,
                customer_id,
                campaign_id,
                asset_operation,
                "PROMOTION",
            )

        return ctx.safety.propose(
            tool_name="create_promotion_asset",
            customer_id=customer_id,
            description=description,
            payload={
                "campaign_id": campaign_id,
                "promotion_target": promotion_target,
                "discount_percent": discount_percent,
                "money_amount_off": money_amount_off,
                "currency_code": currency_code.upper(),
                "promotion_code": promotion_code,
                "final_url": final_url,
            },
            execute=execute,
        )

    @mcp.tool()
    def list_campaign_assets(customer_id: str, campaign_id: str) -> dict:
        """List assets currently attached to a campaign."""
        query = f"""
            SELECT campaign_asset.asset, campaign_asset.field_type,
                   campaign_asset.status, asset.type,
                   asset.sitelink_asset.link_text,
                   asset.call_asset.phone_number,
                   asset.business_message_asset.message_provider,
                   asset.business_message_asset.starter_message,
                   asset.business_message_asset.whatsapp_info.country_code,
                   asset.business_message_asset.whatsapp_info.phone_number
            FROM campaign_asset
            WHERE campaign.id = {int(campaign_id)}
        """
        rows = ctx.client.search(customer_id, query)
        return {"campaign_id": campaign_id, "assets": rows, "count": len(rows)}

    @mcp.tool()
    def remove_campaign_asset(
        customer_id: str,
        campaign_id: str,
        asset_id: str,
        field_type: str,
    ) -> dict:
        """Propose detaching an asset from a campaign."""
        client = ctx.client.raw
        customer_id_clean = customer_id.replace("-", "")
        field_type_enum = client.enums.AssetFieldTypeEnum[field_type].value
        operation = client.get_type("CampaignAssetOperation")
        operation.remove = client.get_service(
            "CampaignAssetService"
        ).campaign_asset_path(customer_id_clean, campaign_id, asset_id, field_type_enum)
        description = (
            f"Detach {field_type} asset {asset_id} from campaign {campaign_id}"
        )

        def execute():
            return ctx.client.mutate("CampaignAssetService", customer_id, [operation])

        return ctx.safety.propose(
            tool_name="remove_campaign_asset",
            customer_id=customer_id,
            description=description,
            payload={
                "campaign_id": campaign_id,
                "asset_id": asset_id,
                "field_type": field_type,
            },
            execute=execute,
        )

    @mcp.tool()
    def create_callout_asset(
        customer_id: str,
        campaign_id: str,
        callout_texts: list[str],
    ) -> dict:
        """Create one or more callouts and attach all of them atomically."""
        if not callout_texts:
            raise ValueError("Provide at least one callout text.")
        if any(not text or len(text) > 25 for text in callout_texts):
            raise ValueError("Each callout text must be 1-25 characters.")

        client = ctx.client.raw
        asset_operations = []
        for text in callout_texts:
            operation = client.get_type("AssetOperation")
            operation.create.callout_asset.callout_text = text
            asset_operations.append(operation)
        description = (
            f"Create {len(callout_texts)} callout(s) and attach to campaign "
            f"{campaign_id} atomically"
        )

        def execute():
            return _create_many_assets_and_attach_to_campaign(
                ctx,
                customer_id,
                campaign_id,
                asset_operations,
                "CALLOUT",
            )

        return ctx.safety.propose(
            tool_name="create_callout_asset",
            customer_id=customer_id,
            description=description,
            payload={"campaign_id": campaign_id, "callout_texts": callout_texts},
            execute=execute,
        )

    @mcp.tool()
    def create_structured_snippet_asset(
        customer_id: str,
        campaign_id: str,
        header: str,
        values: list[str],
    ) -> dict:
        """Create a structured snippet and attach it atomically."""
        if not (3 <= len(values) <= 10):
            raise ValueError("Provide between 3 and 10 values.")
        if any(not value or len(value) > 25 for value in values):
            raise ValueError("Each value must be 1-25 characters.")
        if not header:
            raise ValueError("header is required.")

        client = ctx.client.raw
        asset_operation = client.get_type("AssetOperation")
        asset_operation.create.structured_snippet_asset.header = header
        asset_operation.create.structured_snippet_asset.values.extend(values)
        description = (
            f"Create structured snippet '{header}': {values} and attach to "
            f"campaign {campaign_id} atomically"
        )

        def execute():
            return _create_asset_and_attach_to_campaign(
                ctx,
                customer_id,
                campaign_id,
                asset_operation,
                "STRUCTURED_SNIPPET",
            )

        return ctx.safety.propose(
            tool_name="create_structured_snippet_asset",
            customer_id=customer_id,
            description=description,
            payload={"campaign_id": campaign_id, "header": header, "values": values},
            execute=execute,
        )


def _create_asset_and_attach_to_campaign(
    ctx: AppContext,
    customer_id: str,
    campaign_id: str,
    asset_operation,
    field_type: str,
):
    return _create_many_assets_and_attach_to_campaign(
        ctx,
        customer_id,
        campaign_id,
        [asset_operation],
        field_type,
    )


def _create_many_assets_and_attach_to_campaign(
    ctx: AppContext,
    customer_id: str,
    campaign_id: str,
    asset_operations: list,
    field_type: str,
):
    client = ctx.client.raw
    customer_id_clean = customer_id.replace("-", "")
    campaign_resource_name = client.get_service("CampaignService").campaign_path(
        customer_id_clean, campaign_id
    )
    operations = []

    for offset, asset_operation in enumerate(asset_operations, start=1):
        temp_id = -offset
        temp_asset_name = client.get_service("AssetService").asset_path(
            customer_id_clean, temp_id
        )
        asset_operation.create.resource_name = temp_asset_name
        operations.append(_wrap_mutate(client, "asset_operation", asset_operation))

        link_operation = client.get_type("CampaignAssetOperation")
        link = link_operation.create
        link.campaign = campaign_resource_name
        link.asset = temp_asset_name
        link.field_type = client.enums.AssetFieldTypeEnum[field_type].value
        operations.append(
            _wrap_mutate(client, "campaign_asset_operation", link_operation)
        )

    return ctx.client.mutate_atomic(customer_id, operations)


def _wrap_mutate(client, field_name: str, operation):
    mutate_operation = client.get_type("MutateOperation")
    client.copy_from(getattr(mutate_operation, field_name), operation)
    return mutate_operation
