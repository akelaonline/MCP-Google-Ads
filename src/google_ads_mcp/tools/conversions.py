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
            return ctx.client.mutate("ConversionActionService", customer_id, [operation])

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
