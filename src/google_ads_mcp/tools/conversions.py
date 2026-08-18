"""Conversion action management and offline conversion uploads for API v25."""

from __future__ import annotations

import hashlib
import re

from google.protobuf import field_mask_pb2

from ..context import AppContext


def register(mcp, ctx: AppContext) -> None:
    @mcp.tool()
    def list_conversion_actions(customer_id: str) -> dict:
        """List conversion actions configured in the account."""
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
        return {"conversion_actions": rows, "count": len(rows)}

    @mcp.tool()
    def create_conversion_action(
        customer_id: str,
        name: str,
        category: str,
        counting_type: str = "ONE_PER_CLICK",
        value: float | None = None,
        currency_code: str = "USD",
        conversion_action_type: str = "WEBPAGE",
    ) -> dict:
        """Propose creating a conversion action.

        ``conversion_action_type`` defaults to ``WEBPAGE`` for tag-tracked web
        conversions. Use ``UPLOAD_CLICKS`` when the action will receive GCLID/
        GBRAID/WBRAID offline uploads through ``upload_offline_conversion`` or
        ``upload_enhanced_conversion``. The type is immutable after creation.
        """
        if not name.strip():
            raise ValueError("name must not be empty.")
        if counting_type not in {"ONE_PER_CLICK", "MANY_PER_CLICK"}:
            raise ValueError("counting_type must be ONE_PER_CLICK or MANY_PER_CLICK.")
        if value is not None and value < 0:
            raise ValueError("value must be zero or greater.")
        if not currency_code or len(currency_code) != 3:
            raise ValueError("currency_code must be a three-letter currency code.")

        client = ctx.client.raw
        try:
            action_type = client.enums.ConversionActionTypeEnum[
                conversion_action_type
            ].value
            category_value = client.enums.ConversionActionCategoryEnum[category].value
        except KeyError as ex:
            raise ValueError(f"Invalid conversion enum value: {ex.args[0]}") from ex

        operation = client.get_type("ConversionActionOperation")
        action = operation.create
        action.name = name
        action.type_ = action_type
        action.category = category_value
        action.status = client.enums.ConversionActionStatusEnum.ENABLED.value
        action.counting_type = client.enums.ConversionActionCountingTypeEnum[
            counting_type
        ].value
        if value is not None:
            action.value_settings.default_value = value
            action.value_settings.default_currency_code = currency_code.upper()
            action.value_settings.always_use_default_value = False

        description = (
            f"Create conversion action '{name}' (type={conversion_action_type}, "
            f"category={category}, counting={counting_type}), status ENABLED"
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
                "currency_code": currency_code.upper(),
                "conversion_action_type": conversion_action_type,
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
        """Propose uploading an enhanced offline click conversion.

        The conversion action must be ENABLED and type ``UPLOAD_CLICKS``.
        Email and phone are normalized according to Google's enhanced-conversion
        rules and SHA-256 hashed locally; raw identifiers are never included in
        the audit payload.
        """
        if not email and not phone_number:
            raise ValueError("Provide at least one of email or phone_number.")
        _validate_click_upload_inputs(gclid, conversion_date_time, conversion_value)
        _ensure_upload_click_action(ctx, customer_id, conversion_action_id)

        normalized_phone = _normalize_e164(phone_number) if phone_number else None
        hashed_email = _normalize_and_hash_email(email) if email else None
        hashed_phone = _hash_normalized(normalized_phone) if normalized_phone else None

        client = ctx.client.raw
        conversion_upload_service = client.get_service("ConversionUploadService")
        click_conversion = _build_click_conversion(
            client,
            customer_id,
            conversion_action_id,
            gclid,
            conversion_date_time,
            conversion_value,
            currency_code,
        )

        if hashed_email:
            identifier = client.get_type("UserIdentifier")
            identifier.user_identifier_source = (
                client.enums.UserIdentifierSourceEnum.FIRST_PARTY.value
            )
            identifier.hashed_email = hashed_email
            click_conversion.user_identifiers.append(identifier)
        if hashed_phone:
            identifier = client.get_type("UserIdentifier")
            identifier.user_identifier_source = (
                client.enums.UserIdentifierSourceEnum.FIRST_PARTY.value
            )
            identifier.hashed_phone_number = hashed_phone
            click_conversion.user_identifiers.append(identifier)

        description = (
            f"Upload Enhanced Conversion: action {conversion_action_id}, "
            f"gclid={gclid[:12]}…, has_email={bool(email)}, "
            f"has_phone={bool(phone_number)}"
        )

        def execute():
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
                "gclid_prefix": gclid[:12],
                "conversion_date_time": conversion_date_time,
                "has_email": bool(email),
                "has_phone": bool(phone_number),
                "conversion_value": conversion_value,
                "currency_code": currency_code.upper(),
            },
            execute=execute,
        )

    @mcp.tool()
    def update_conversion_action_status(
        customer_id: str, conversion_action_id: str, status: str
    ) -> dict:
        """Propose changing a conversion action status.

        Current writable statuses are ENABLED, HIDDEN and REMOVED; there is no
        PAUSED conversion-action status in Google Ads API v25.
        """
        if status not in {"ENABLED", "HIDDEN", "REMOVED"}:
            raise ValueError("status must be ENABLED, HIDDEN, or REMOVED.")
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
            return ctx.client.mutate("ConversionActionService", customer_id, [operation])

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
        """Set whether a conversion action is primary/biddable.

        ``include_in_conversions_metric`` is retained as the public argument for
        backwards compatibility, but Google made that resource field immutable.
        API v25 requires managing ``primary_for_goal`` instead. ``False`` makes
        the action secondary/non-biddable for normal customer/campaign goals.
        """
        client = ctx.client.raw
        resource_name = client.get_service(
            "ConversionActionService"
        ).conversion_action_path(customer_id.replace("-", ""), conversion_action_id)
        operation = client.get_type("ConversionActionOperation")
        operation.update.resource_name = resource_name
        operation.update.primary_for_goal = include_in_conversions_metric
        operation.update_mask.CopyFrom(
            field_mask_pb2.FieldMask(paths=["primary_for_goal"])
        )

        verb = "primary/biddable" if include_in_conversions_metric else "secondary/non-biddable"
        description = (
            f"Set conversion action {conversion_action_id} -> {verb} "
            "using primary_for_goal"
        )

        def execute():
            return ctx.client.mutate("ConversionActionService", customer_id, [operation])

        return ctx.safety.propose(
            tool_name="set_conversion_action_counting",
            customer_id=customer_id,
            description=description,
            payload={
                "conversion_action_id": conversion_action_id,
                "include_in_conversions_metric": include_in_conversions_metric,
                "primary_for_goal": include_in_conversions_metric,
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
        """Propose uploading an offline click conversion.

        The target conversion action must be ENABLED and type ``UPLOAD_CLICKS``.
        """
        _validate_click_upload_inputs(gclid, conversion_date_time, conversion_value)
        _ensure_upload_click_action(ctx, customer_id, conversion_action_id)

        client = ctx.client.raw
        conversion_upload_service = client.get_service("ConversionUploadService")
        click_conversion = _build_click_conversion(
            client,
            customer_id,
            conversion_action_id,
            gclid,
            conversion_date_time,
            conversion_value,
            currency_code,
        )
        description = (
            f"Upload offline conversion: action {conversion_action_id}, "
            f"gclid={gclid[:12]}…, value={conversion_value} {currency_code.upper()}"
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
                "gclid_prefix": gclid[:12],
                "conversion_date_time": conversion_date_time,
                "conversion_value": conversion_value,
                "currency_code": currency_code.upper(),
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
        """Propose creating an ENABLED Conversion Value Rule."""
        if action not in {"ADD", "MULTIPLY", "SET"}:
            raise ValueError('action must be "ADD", "MULTIPLY", or "SET".')
        if action == "MULTIPLY" and action_value <= 0:
            raise ValueError("MULTIPLY action_value must be greater than 0.")
        if action in {"ADD", "SET"} and action_value < 0:
            raise ValueError(f"{action} action_value must be zero or greater.")
        if not (geo_target_ids or audience_condition or device_type):
            raise ValueError(
                "Provide at least one condition: geo_target_ids, audience_condition, "
                "or device_type."
            )

        client = ctx.client.raw
        operation = client.get_type("ConversionValueRuleOperation")
        rule = operation.create
        rule.action.operation = client.enums.ValueRuleOperationEnum[action].value
        rule.action.value = action_value
        rule.status = client.enums.ConversionValueRuleStatusEnum.ENABLED.value

        if geo_target_ids:
            geo_service = client.get_service("GeoTargetConstantService")
            for geo_id in geo_target_ids:
                rule.geo_location_condition.geo_target_constants.append(
                    geo_service.geo_target_constant_path(str(geo_id))
                )
            rule.geo_location_condition.geo_match_type = (
                client.enums.ValueRuleGeoLocationMatchTypeEnum.ANY.value
            )

        if audience_condition:
            rule.audience_condition.user_lists.append(audience_condition)

        if device_type:
            rule.device_condition.device_types.append(
                client.enums.ValueRuleDeviceTypeEnum[device_type].value
            )

        description = (
            f"Create Conversion Value Rule: {action} value by {action_value}"
            + (f", geos={geo_target_ids}" if geo_target_ids else "")
            + (f", device={device_type}" if device_type else "")
        )

        def execute():
            return ctx.client.mutate("ConversionValueRuleService", customer_id, [operation])

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
        """List all Conversion Value Rules on the account."""
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


def _ensure_upload_click_action(
    ctx: AppContext,
    customer_id: str,
    conversion_action_id: str,
) -> None:
    query = f"""
        SELECT conversion_action.id, conversion_action.type, conversion_action.status
        FROM conversion_action
        WHERE conversion_action.id = {int(conversion_action_id)}
        LIMIT 1
    """
    rows = ctx.client.search(customer_id, query)
    if not rows:
        raise ValueError(
            f"Conversion action {conversion_action_id} was not found or is not accessible."
        )
    action = rows[0].get("conversion_action", {})
    if action.get("type") != "UPLOAD_CLICKS":
        raise ValueError(
            f"Conversion action {conversion_action_id} is type {action.get('type')!r}; "
            "offline click uploads require UPLOAD_CLICKS."
        )
    if action.get("status") != "ENABLED":
        raise ValueError(
            f"Conversion action {conversion_action_id} is not ENABLED "
            f"(status={action.get('status')!r})."
        )


def _build_click_conversion(
    client,
    customer_id: str,
    conversion_action_id: str,
    gclid: str,
    conversion_date_time: str,
    conversion_value: float | None,
    currency_code: str,
):
    click_conversion = client.get_type("ClickConversion")
    click_conversion.conversion_action = client.get_service(
        "ConversionActionService"
    ).conversion_action_path(customer_id.replace("-", ""), conversion_action_id)
    click_conversion.gclid = gclid.strip()
    click_conversion.conversion_date_time = conversion_date_time.strip()
    if conversion_value is not None:
        click_conversion.conversion_value = conversion_value
        click_conversion.currency_code = currency_code.upper()
    return click_conversion


def _validate_click_upload_inputs(
    gclid: str,
    conversion_date_time: str,
    conversion_value: float | None,
) -> None:
    if not gclid or not gclid.strip():
        raise ValueError("gclid must not be empty.")
    if not conversion_date_time or not conversion_date_time.strip():
        raise ValueError("conversion_date_time must not be empty.")
    if conversion_value is not None and conversion_value < 0:
        raise ValueError("conversion_value must be zero or greater.")


def _normalize_and_hash_email(email: str) -> str:
    normalized = email.strip().lower()
    if normalized.count("@") != 1:
        raise ValueError("email must contain exactly one @ sign.")
    local, domain = normalized.split("@", 1)
    if not local or not domain:
        raise ValueError("email is invalid.")
    if domain in {"gmail.com", "googlemail.com"}:
        local = local.split("+", 1)[0].replace(".", "")
    return _hash_normalized(f"{local}@{domain}")


def _normalize_e164(phone: str) -> str:
    normalized = re.sub(r"[\s().-]", "", phone.strip())
    if not re.fullmatch(r"\+[1-9]\d{7,14}", normalized):
        raise ValueError(
            "phone_number must be a valid E.164 number, for example +5491112345678."
        )
    return normalized


def _hash_normalized(value: str) -> str:
    return hashlib.sha256(value.strip().lower().encode("utf-8")).hexdigest()
