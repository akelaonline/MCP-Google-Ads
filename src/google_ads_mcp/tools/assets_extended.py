"""Extended asset creators: lead form, price, location, mobile app, deep link.

These cover the standard agency extension types missing from the core asset
tools. Following the house pattern, each tool creates the asset and attaches
it atomically to a campaign (create + campaign-asset link in one mutation).
"""

from __future__ import annotations

from ..client import micros
from ..context import AppContext
from .assets import _create_asset_and_attach_to_campaign


def register(mcp, ctx: AppContext) -> None:
    @mcp.tool()
    def create_lead_form_asset(
        customer_id: str,
        campaign_id: str,
        business_name: str,
        headline: str,
        description: str,
        call_to_action_type: str,
        privacy_policy_url: str,
        fields: list[dict],
        desired_intent: str = "HIGH_INTENT",
        post_submit_headline: str | None = None,
        post_submit_description: str | None = None,
        post_submit_call_to_action_type: str = "VISIT_SITE",
        webhook_url: str | None = None,
    ) -> dict:
        """Propose creating a Lead Form asset and attaching it atomically.

        ``fields`` is a list of dicts, e.g.
        ``[{"input_type": "EMAIL"}, {"input_type": "PHONE_NUMBER"},
        {"input_type": "FIRST_NAME"}]``. For choice fields pass
        ``single_choice_answers``, for example
        ``{"input_type": "PRODUCT", "single_choice_answers": ["A", "B"]}``.
        ``webhook_url`` enables lead delivery via webhook.
        """
        if not business_name.strip() or not headline.strip() or not description.strip():
            raise ValueError("business_name, headline and description are required.")
        if not privacy_policy_url.strip():
            raise ValueError("privacy_policy_url is required.")
        if not fields:
            raise ValueError("Provide at least one field.")
        if desired_intent not in {"LOW_INTENT", "HIGH_INTENT"}:
            raise ValueError("desired_intent must be LOW_INTENT or HIGH_INTENT.")
        if post_submit_call_to_action_type not in {
            "VISIT_SITE", "DOWNLOAD", "LEARN_MORE", "SHOP_NOW",
        }:
            raise ValueError(
                "post_submit_call_to_action_type must be VISIT_SITE, DOWNLOAD, "
                "LEARN_MORE, or SHOP_NOW."
            )

        client = ctx.client.raw
        asset_operation = client.get_type("AssetOperation")
        asset = asset_operation.create
        lead_form = asset.lead_form_asset
        lead_form.business_name = business_name.strip()
        lead_form.headline = headline.strip()
        lead_form.description = description.strip()
        lead_form.call_to_action_type = client.enums.LeadFormCallToActionTypeEnum[
            call_to_action_type
        ].value
        lead_form.desired_intent = client.enums.LeadFormDesiredIntentEnum[
            desired_intent
        ].value
        lead_form.privacy_policy_url = privacy_policy_url.strip()
        if post_submit_headline:
            lead_form.post_submit_headline = post_submit_headline.strip()
        if post_submit_description:
            lead_form.post_submit_description = post_submit_description.strip()
        lead_form.post_submit_call_to_action_type = (
            client.enums.LeadFormPostSubmitCallToActionTypeEnum[
                post_submit_call_to_action_type
            ].value
        )
        for item in fields:
            input_type = str(item.get("input_type", "")).strip().upper()
            if not input_type:
                raise ValueError("Every lead form field needs an 'input_type'.")
            field_dict: dict = {
                "input_type": client.enums.LeadFormFieldUserInputTypeEnum[
                    input_type
                ].value,
            }
            answers = item.get("single_choice_answers")
            if answers:
                field_dict["single_choice_answers"] = {
                    "answers": [str(answer) for answer in answers]
                }
            lead_form.fields.append(field_dict)
        if webhook_url:
            lead_form.delivery_methods.append(
                {"webhook": {"advertiser_webhook_url": webhook_url.strip()}}
            )

        description = (
            f"Create Lead Form '{headline}' for {business_name} and attach to "
            f"campaign {campaign_id} atomically"
        )

        def execute():
            return _create_asset_and_attach_to_campaign(
                ctx,
                customer_id,
                campaign_id,
                asset_operation,
                "LEAD_FORM",
            )

        return ctx.safety.propose(
            tool_name="create_lead_form_asset",
            customer_id=customer_id,
            description=description,
            payload={
                "campaign_id": campaign_id,
                "business_name": business_name,
                "headline": headline,
                "call_to_action_type": call_to_action_type,
                "desired_intent": desired_intent,
                "field_input_types": [
                    str(item.get("input_type", "")).upper() for item in fields
                ],
                "webhook_enabled": bool(webhook_url),
            },
            execute=execute,
        )

    @mcp.tool()
    def create_price_asset(
        customer_id: str,
        campaign_id: str,
        price_type: str,
        language_code: str,
        offerings: list[dict],
        price_qualifier: str = "FROM",
        currency_code: str = "USD",
    ) -> dict:
        """Propose creating a Price asset and attaching it atomically.

        ``offerings`` is a list of dicts:
        ``{"header", "description", "price", "unit", "final_url"}`` where
        ``price`` is a numeric amount in ``currency_code`` and ``unit`` is the
        PriceExtensionPriceUnit (PER_HOUR, PER_DAY, PER_NIGHT, ...).
        ``price_type`` is the PriceExtensionType (BRANDS, EVENTS, LOCATIONS,
        PRODUCT_CATEGORIES, SERVICES, ...).
        """
        if price_type not in {
            "BRANDS", "EVENTS", "LOCATIONS", "NEIGHBORHOODS",
            "PRODUCT_CATEGORIES", "PRODUCT_TIERS", "SERVICES",
            "SERVICE_CATEGORIES", "SERVICE_TIERS",
        }:
            raise ValueError(f"Unknown price_type {price_type!r}.")
        if len(language_code) != 2:
            raise ValueError("language_code must be a two-letter language code.")
        if len(currency_code) != 3:
            raise ValueError("currency_code must be a three-letter currency code.")
        if not offerings:
            raise ValueError("Provide at least one price offering.")

        client = ctx.client.raw
        asset_operation = client.get_type("AssetOperation")
        asset = asset_operation.create
        price = asset.price_asset
        price.type_ = client.enums.PriceExtensionTypeEnum[price_type].value
        price.language_code = language_code
        price.price_qualifier = client.enums.PriceExtensionPriceQualifierEnum[
            price_qualifier
        ].value
        for item in offerings:
            header = str(item.get("header", "")).strip()
            if not header:
                raise ValueError("Every price offering needs a 'header'.")
            if not item.get("final_url"):
                raise ValueError(f"Price offering '{header}' needs a 'final_url'.")
            try:
                price_amount = float(item["price"])
            except (KeyError, TypeError, ValueError):
                raise ValueError(
                    f"Price offering '{header}' needs a numeric 'price'."
                )
            if price_amount < 0:
                raise ValueError("price must be zero or greater.")
            price.price_offerings.append(
                {
                    "header": header,
                    "description": str(item.get("description", "")).strip(),
                    "price": {
                        "amount_micros": micros(price_amount),
                        "currency_code": currency_code.upper(),
                    },
                    "unit": client.enums.PriceExtensionPriceUnitEnum[
                        str(item.get("unit", "PER_DAY")).upper()
                    ].value,
                    "final_url": str(item["final_url"]).strip(),
                }
            )

        description = (
            f"Create Price asset ({price_type}, {language_code.upper()}, "
            f"{len(offerings)} offering(s)) and attach to campaign {campaign_id} "
            "atomically"
        )

        def execute():
            return _create_asset_and_attach_to_campaign(
                ctx,
                customer_id,
                campaign_id,
                asset_operation,
                "PRICE",
            )

        return ctx.safety.propose(
            tool_name="create_price_asset",
            customer_id=customer_id,
            description=description,
            payload={
                "campaign_id": campaign_id,
                "price_type": price_type,
                "language_code": language_code,
                "price_qualifier": price_qualifier,
                "offering_headers": [item.get("header") for item in offerings],
            },
            execute=execute,
        )

    @mcp.tool()
    def create_location_asset(
        customer_id: str,
        place_id: str,
    ) -> dict:
        """Propose creating a Location asset (Google Business Profile link).

        ``place_id`` is the Google Place ID of the business location. v25 has
        no LOCATION value in AssetFieldType, so location assets are created at
        account level and Google serves them automatically for campaigns on
        accounts with a linked Business Profile — there is no campaign asset
        link to attach.
        """
        place = place_id.strip()
        if not place:
            raise ValueError("place_id is required.")
        if len(place) > 100 or " " in place:
            raise ValueError("place_id must be a valid Google Place ID.")

        client = ctx.client.raw
        asset_operation = client.get_type("AssetOperation")
        asset = asset_operation.create
        asset.location_asset.place_id = place

        description = f"Create Location asset for place {place}"

        def execute():
            return ctx.client.mutate("AssetService", customer_id, [asset_operation])

        return ctx.safety.propose(
            tool_name="create_location_asset",
            customer_id=customer_id,
            description=description,
            payload={"place_id": place},
            execute=execute,
        )

    @mcp.tool()
    def create_mobile_app_asset(
        customer_id: str,
        campaign_id: str,
        app_id: str,
        app_store: str,
        link_text: str,
    ) -> dict:
        """Propose creating a mobile-app extension asset and attaching it atomically."""
        if not app_id.strip() or not link_text.strip():
            raise ValueError("app_id and link_text are required.")
        if app_store not in {"APPLE_APP_STORE", "GOOGLE_APP_STORE"}:
            raise ValueError("app_store must be APPLE_APP_STORE or GOOGLE_APP_STORE.")

        client = ctx.client.raw
        asset_operation = client.get_type("AssetOperation")
        asset = asset_operation.create
        mobile = asset.mobile_app_asset
        mobile.app_id = app_id.strip()
        mobile.app_store = client.enums.AppCampaignAppStoreEnum[app_store].value
        mobile.link_text = link_text.strip()

        description = (
            f"Create mobile-app asset ({app_store}/{app_id}) and attach to "
            f"campaign {campaign_id} atomically"
        )

        def execute():
            return _create_asset_and_attach_to_campaign(
                ctx,
                customer_id,
                campaign_id,
                asset_operation,
                "MOBILE_APP",
            )

        return ctx.safety.propose(
            tool_name="create_mobile_app_asset",
            customer_id=customer_id,
            description=description,
            payload={
                "campaign_id": campaign_id,
                "app_id": app_id,
                "app_store": app_store,
                "link_text": link_text,
            },
            execute=execute,
        )

    @mcp.tool()
    def create_app_deep_link_asset(
        customer_id: str,
        app_deep_link_uri: str,
    ) -> dict:
        """Propose creating an app deep-link asset.

        v25 has no APP_DEEP_LINK value in AssetFieldType, so the asset is
        created at account level without a campaign link.
        """
        uri = app_deep_link_uri.strip()
        if not uri:
            raise ValueError("app_deep_link_uri is required.")

        client = ctx.client.raw
        asset_operation = client.get_type("AssetOperation")
        asset = asset_operation.create
        asset.app_deep_link_asset.app_deep_link_uri = uri

        description = f"Create app deep-link asset '{uri}'"

        def execute():
            return ctx.client.mutate("AssetService", customer_id, [asset_operation])

        return ctx.safety.propose(
            tool_name="create_app_deep_link_asset",
            customer_id=customer_id,
            description=description,
            payload={"app_deep_link_uri": uri},
            execute=execute,
        )
