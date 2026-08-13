"""Conversion action management + offline conversion upload.

Offline upload is the key tool for a WhatsApp/CRM-driven funnel: when a
lead closes days after the click, you upload the conversion back against
the original gclid so Smart Bidding can learn from real outcomes.
"""

from __future__ import annotations

from google.protobuf import field_mask_pb2

from ..context import AppContext


def register(mcp, ctx: AppContext) -> None:
    @mcp.tool()
    def list_conversion_actions(customer_id: str) -> dict:
        """List conversion actions configured in the account (id, name, status, category)."""
        query = """
            SELECT conversion_action.id, conversion_action.name,
                   conversion_action.status, conversion_action.category,
                   conversion_action.type, conversion_action.origin,
                   conversion_action.primary_for_goal,
                   conversion_action.include_in_conversions_metric
            FROM conversion_action
            ORDER BY conversion_action.name
        """
        rows = ctx.client.search(customer_id, query)
        return {"conversion_actions": rows}

    @mcp.tool()
    def create_conversion_action(
        customer_id: str,
        name: str,
        category: str,
        counting_type: str = "ONE_PER_CLICK",
        value: float | None = None,
        currency_code: str = "USD",
    ) -> dict:
        """Propose creating a new website conversion action (e.g. "WhatsApp
        Click", "Formulario Enviado", "Compra"). Created ENABLED and
        included in the main Conversions metric/bidding by default.

        This is a WEBSITE-type conversion action tracked via the Google Ads
        tag — for a conversion coming from a click ID you'll upload later
        with upload_offline_conversion, still create it here first so there's
        a conversion_action_id to upload against.

        Args:
            category: One of PURCHASE, LEAD, SIGNUP, PAGE_VIEW, DOWNLOAD,
                CONTACT, SUBMIT_LEAD_FORM, BOOK_APPOINTMENT,
                REQUEST_QUOTE, GET_DIRECTIONS, OUTBOUND_CLICK, PHONE_CALL_LEAD,
                or OTHER — pick the closest match to what's actually happening.
            counting_type: ONE_PER_CLICK (leads/signups — count once per click)
                or MANY_PER_CLICK (purchases — count every conversion, e.g.
                repeat purchases from the same click).
            value: Optional default value credited per conversion when no
                dynamic value is passed at conversion time (e.g. average
                order value). Omit for actions with no clear monetary value
                (e.g. a WhatsApp click).
        """
        client = ctx.client.raw

        operation = client.get_type("ConversionActionOperation")
        action = operation.create
        action.name = name
        action.type_ = client.enums.ConversionActionTypeEnum.WEBSITE
        action.category = client.enums.ConversionActionCategoryEnum[category].value
        action.status = client.enums.ConversionActionStatusEnum.ENABLED
        action.counting_type = client.enums.ConversionActionCountingTypeEnum[
            counting_type
        ].value
        if value is not None:
            action.value_settings.default_value = value
            action.value_settings.default_currency_code = currency_code
            action.value_settings.always_use_default_value = False

        description = (
            f"Create conversion action '{name}' (category={category}, "
            f"counting={counting_type}), status ENABLED"
        )

        def execute():
            return ctx.client.mutate("ConversionActionService", customer_id, [operation])

        return ctx.safety.propose(
            tool_name="create_conversion_action",
            customer_id=customer_id,
            description=description,
            payload={
                "name": name,
                "category": category,
                "counting_type": counting_type,
                "value": value,
                "currency_code": currency_code,
            },
            execute=execute,
        )

    @mcp.tool()
    def upload_enhanced_conversion(
        customer_id: str,
        conversion_action_id: str,
        gclid: str,
        conversion_date_time: str,
        email: str | None = None,
        phone_number: str | None = None,
        conversion_value: float | None = None,
        currency_code: str = "USD",
    ) -> dict:
        """Propose uploading an offline click conversion WITH Enhanced
        Conversions user identifiers (hashed email and/or phone), which
        improves Google's ability to match the conversion back to the
        original ad click/user even when cookies or click IDs alone would
        miss it. Increasingly important as browser tracking restrictions
        tighten.

        Prefer this over plain upload_offline_conversion whenever you have
        the lead's email or phone at the time of upload (e.g. a WhatsApp
        lead that later left contact info in a CRM).

        Args:
            gclid: The Google Click ID from the original ad click.
            conversion_date_time: "YYYY-MM-DD HH:MM:SS+TZ:00".
            email: Lead's email, plain text — this tool hashes it (SHA-256,
                normalized lowercase/trimmed) before sending, per Google's
                Enhanced Conversions requirements. Never send pre-hashed values.
            phone_number: Lead's phone in E.164 format (e.g. "+5493416506894").
                Hashed the same way as email.
        """
        if not email and not phone_number:
            raise ValueError(
                "Provide at least one of email or phone_number for Enhanced "
                "Conversions to have anything to match on."
            )

        client = ctx.client.raw
        conversion_upload_service = client.get_service("ConversionUploadService")

        click_conversion = client.get_type("ClickConversion")
        click_conversion.conversion_action = client.get_service(
            "ConversionActionService"
        ).conversion_action_path(customer_id.replace("-", ""), conversion_action_id)
        click_conversion.gclid = gclid
        click_conversion.conversion_date_time = conversion_date_time
        if conversion_value is not None:
            click_conversion.conversion_value = conversion_value
            click_conversion.currency_code = currency_code

        description = (
            f"Upload Enhanced Conversion: action {conversion_action_id}, "
            f"gclid={gclid[:12]}…, has_email={bool(email)}, "
            f"has_phone={bool(phone_number)}"
        )

        def execute():
            import hashlib

            def _hash(value: str) -> str:
                return hashlib.sha256(value.strip().lower().encode("utf-8")).hexdigest()

            if email:
                identifier = client.get_type("UserIdentifier")
                identifier.hashed_email = _hash(email)
                click_conversion.user_identifiers.append(identifier)
            if phone_number:
                identifier = client.get_type("UserIdentifier")
                identifier.hashed_phone_number = _hash(phone_number)
                click_conversion.user_identifiers.append(identifier)

            return conversion_upload_service.upload_click_conversions(
                customer_id=customer_id.replace("-", ""),
                conversions=[click_conversion],
                partial_failure=True,
            )

        return ctx.safety.propose(
            tool_name="upload_enhanced_conversion",
            customer_id=customer_id,
            description=description,
            payload={
                "conversion_action_id": conversion_action_id,
                "gclid": gclid,
                "conversion_date_time": conversion_date_time,
                "has_email": bool(email),
                "has_phone": bool(phone_number),
                "conversion_value": conversion_value,
                "currency_code": currency_code,
            },
            execute=execute,
        )

    @mcp.tool()
    def update_conversion_action_status(
        customer_id: str, conversion_action_id: str, status: str
    ) -> dict:
        """Propose enabling, pausing, or removing a conversion action.

        Use PAUSED (not REMOVED) to stop a soft/vanity signal (e.g. a page_view
        or a "Test de Nivel" click) from being counted toward bidding without
        losing its historical data.

        Args:
            status: ENABLED, REMOVED, or HIDDEN.
        """
        client = ctx.client.raw
        resource_name = client.get_service(
            "ConversionActionService"
        ).conversion_action_path(customer_id.replace("-", ""), conversion_action_id)

        operation = client.get_type("ConversionActionOperation")
        operation.update.resource_name = resource_name
        operation.update.status = client.enums.ConversionActionStatusEnum[status].value
        operation.update_mask.CopyFrom(field_mask_pb2.FieldMask(paths=["status"]))

        description = f"Set conversion action {conversion_action_id} status -> {status}"

        def execute():
            return ctx.client.mutate(
                "ConversionActionService", customer_id, [operation]
            )

        return ctx.safety.propose(
            tool_name="update_conversion_action_status",
            customer_id=customer_id,
            description=description,
            payload={"conversion_action_id": conversion_action_id, "status": status},
            execute=execute,
        )

    @mcp.tool()
    def set_conversion_action_counting(
        customer_id: str,
        conversion_action_id: str,
        include_in_conversions_metric: bool,
    ) -> dict:
        """Propose including or excluding a conversion action from the account's
        main "Conversions" column and from automated bidding (Maximize
        Conversions / Target CPA / Target ROAS all optimize toward this metric).

        This is the tool for "stop letting Smart Bidding chase this soft signal"
        without touching whether the action still records data at all — prefer
        this over pausing when you just want it out of the optimization goal.

        Args:
            include_in_conversions_metric: False = tracked but excluded from
                bidding and the primary Conversions column.
        """
        client = ctx.client.raw
        resource_name = client.get_service(
            "ConversionActionService"
        ).conversion_action_path(customer_id.replace("-", ""), conversion_action_id)

        operation = client.get_type("ConversionActionOperation")
        operation.update.resource_name = resource_name
        operation.update.include_in_conversions_metric = include_in_conversions_metric
        operation.update_mask.CopyFrom(
            field_mask_pb2.FieldMask(paths=["include_in_conversions_metric"])
        )

        verb = "Include" if include_in_conversions_metric else "Exclude"
        description = (
            f"{verb} conversion action {conversion_action_id} in/from the Conversions "
            f"metric and automated bidding"
        )

        def execute():
            return ctx.client.mutate(
                "ConversionActionService", customer_id, [operation]
            )

        return ctx.safety.propose(
            tool_name="set_conversion_action_counting",
            customer_id=customer_id,
            description=description,
            payload={
                "conversion_action_id": conversion_action_id,
                "include_in_conversions_metric": include_in_conversions_metric,
            },
            execute=execute,
        )

    @mcp.tool()
    def upload_offline_conversion(
        customer_id: str,
        conversion_action_id: str,
        gclid: str,
        conversion_date_time: str,
        conversion_value: float,
        currency_code: str = "USD",
    ) -> dict:
        """Propose uploading an offline (click) conversion — e.g. a lead that closed later.

        Args:
            gclid: The Google Click ID captured at the time of the original ad click.
            conversion_date_time: "YYYY-MM-DD HH:MM:SS+TZ:00", must be after the click
                and within the conversion action's lookback window.
            conversion_value: Revenue/value to attribute, in currency_code units.
        """
        client = ctx.client.raw
        conversion_upload_service = client.get_service("ConversionUploadService")

        click_conversion = client.get_type("ClickConversion")
        click_conversion.conversion_action = client.get_service(
            "ConversionActionService"
        ).conversion_action_path(customer_id.replace("-", ""), conversion_action_id)
        click_conversion.gclid = gclid
        click_conversion.conversion_date_time = conversion_date_time
        click_conversion.conversion_value = conversion_value
        click_conversion.currency_code = currency_code

        description = (
            f"Upload offline conversion: action {conversion_action_id}, "
            f"gclid={gclid[:12]}…, value={conversion_value} {currency_code}"
        )

        def execute():
            return conversion_upload_service.upload_click_conversions(
                customer_id=customer_id.replace("-", ""),
                conversions=[click_conversion],
                partial_failure=True,
            )

        return ctx.safety.propose(
            tool_name="upload_offline_conversion",
            customer_id=customer_id,
            description=description,
            payload={
                "conversion_action_id": conversion_action_id,
                "gclid": gclid,
                "conversion_date_time": conversion_date_time,
                "conversion_value": conversion_value,
                "currency_code": currency_code,
            },
            execute=execute,
        )

    @mcp.tool()
    def create_conversion_value_rule(
        customer_id: str,
        action: str,
        action_value: float,
        geo_target_ids: list[str] | None = None,
        audience_condition: str | None = None,
        device_type: str | None = None,
    ) -> dict:
        """Propose creating a Conversion Value Rule — adjusts the reported
        value of a conversion based on who/where/what-device the click came
        from, without touching the underlying conversion action. Common use:
        count a converted sale as worth more when it comes from a
        high-value geography or from a remarketing audience, so
        value-based bidding (Maximize Conversion Value / Target ROAS)
        optimizes toward the segments that actually matter.

        Args:
            action: "MULTIPLY" (scale the value, action_value is the
                multiplier e.g. 1.5 for +50%) or "SET" (replace the value
                outright, action_value is the new absolute value).
            geo_target_ids: Optional list of geo target constant IDs — rule
                applies only to conversions from these locations.
            audience_condition: Optional user list resource name — rule
                applies only to conversions from users in this audience.
            device_type: Optional, one of MOBILE / DESKTOP / TABLET — rule
                applies only to conversions from this device.
        """
        if action not in ("MULTIPLY", "SET"):
            raise ValueError('action must be "MULTIPLY" or "SET".')
        if not (geo_target_ids or audience_condition or device_type):
            raise ValueError(
                "Provide at least one condition: geo_target_ids, "
                "audience_condition, or device_type."
            )

        client = ctx.client.raw
        operation = client.get_type("ConversionValueRuleOperation")
        rule = operation.create

        rule.action.operation = client.enums.ValueRuleOperationEnum[action]
        rule.action.value = action_value

        if geo_target_ids:
            geo_service = client.get_service("GeoTargetConstantService")
            for geo_id in geo_target_ids:
                rule.geo_location_condition.geo_target_constants.append(
                    geo_service.geo_target_constant_path(str(geo_id))
                )
            rule.geo_location_condition.excluded_geo_match_type = (
                client.enums.ValueRuleGeoLocationMatchTypeEnum.ANY
            )

        if audience_condition:
            rule.audience_condition.user_lists.append(audience_condition)

        if device_type:
            rule.device_condition.device_types.append(
                client.enums.ValueRuleDeviceTypeEnum[device_type]
            )

        description = (
            f"Create Conversion Value Rule: {action} value by {action_value}"
            + (f", geos={geo_target_ids}" if geo_target_ids else "")
            + (f", device={device_type}" if device_type else "")
        )

        def execute():
            return ctx.client.mutate(
                "ConversionValueRuleService", customer_id, [operation]
            )

        return ctx.safety.propose(
            tool_name="create_conversion_value_rule",
            customer_id=customer_id,
            description=description,
            payload={
                "action": action,
                "action_value": action_value,
                "geo_target_ids": geo_target_ids,
                "audience_condition": audience_condition,
                "device_type": device_type,
            },
            execute=execute,
        )

    @mcp.tool()
    def list_conversion_value_rules(customer_id: str) -> dict:
        """List all Conversion Value Rules on the account, read-only."""
        query = """
            SELECT
                conversion_value_rule.resource_name,
                conversion_value_rule.action.operation,
                conversion_value_rule.action.value,
                conversion_value_rule.status
            FROM conversion_value_rule
        """
        rows = ctx.client.search(customer_id, query)
        return {"conversion_value_rules": rows, "count": len(rows)}
