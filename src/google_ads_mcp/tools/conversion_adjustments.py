"""Conversion retraction/restatement tools for Google Ads API v25."""

from __future__ import annotations

import re

from ..context import AppContext
from ..errors import GoogleAdsMcpError

_ADJUSTMENT_DATETIME = re.compile(
    r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$"
)


def register(mcp, ctx: AppContext) -> None:
    @mcp.tool()
    def retract_conversion(
        customer_id: str,
        conversion_action_id: str,
        order_id: str,
        adjustment_date_time: str,
    ) -> dict:
        """Propose retracting a previously reported conversion by order ID."""
        _validate_common(order_id, adjustment_date_time)
        client = ctx.client.raw
        adjustment = client.get_type("ConversionAdjustment")
        adjustment.conversion_action = client.get_service(
            "ConversionActionService"
        ).conversion_action_path(
            customer_id.replace("-", ""), conversion_action_id
        )
        adjustment.adjustment_type = (
            client.enums.ConversionAdjustmentTypeEnum.RETRACTION.value
        )
        adjustment.order_id = order_id.strip()
        adjustment.adjustment_date_time = adjustment_date_time

        def execute():
            return _upload_adjustment(ctx, customer_id, adjustment)

        return ctx.safety.propose(
            tool_name="retract_conversion",
            customer_id=customer_id,
            description=(
                f"Retract conversion order_id={order_id.strip()} using action "
                f"{conversion_action_id}"
            ),
            payload={
                "conversion_action_id": str(conversion_action_id),
                "order_id": order_id.strip(),
                "adjustment_date_time": adjustment_date_time,
                "adjustment_type": "RETRACTION",
            },
            execute=execute,
        )

    @mcp.tool()
    def restate_conversion_value(
        customer_id: str,
        conversion_action_id: str,
        order_id: str,
        adjustment_date_time: str,
        adjusted_value: float,
        currency_code: str | None = None,
    ) -> dict:
        """Propose restating the value of a previously reported conversion."""
        _validate_common(order_id, adjustment_date_time)
        if adjusted_value < 0:
            raise ValueError("adjusted_value must be zero or greater.")
        if currency_code is not None and len(currency_code.strip()) != 3:
            raise ValueError("currency_code must be a three-letter ISO 4217 code.")

        client = ctx.client.raw
        adjustment = client.get_type("ConversionAdjustment")
        adjustment.conversion_action = client.get_service(
            "ConversionActionService"
        ).conversion_action_path(
            customer_id.replace("-", ""), conversion_action_id
        )
        adjustment.adjustment_type = (
            client.enums.ConversionAdjustmentTypeEnum.RESTATEMENT.value
        )
        adjustment.order_id = order_id.strip()
        adjustment.adjustment_date_time = adjustment_date_time
        adjustment.restatement_value.adjusted_value = float(adjusted_value)
        if currency_code:
            adjustment.restatement_value.currency_code = currency_code.strip().upper()

        def execute():
            return _upload_adjustment(ctx, customer_id, adjustment)

        return ctx.safety.propose(
            tool_name="restate_conversion_value",
            customer_id=customer_id,
            description=(
                f"Restate conversion order_id={order_id.strip()} to value "
                f"{adjusted_value}"
                + (f" {currency_code.strip().upper()}" if currency_code else "")
            ),
            payload={
                "conversion_action_id": str(conversion_action_id),
                "order_id": order_id.strip(),
                "adjustment_date_time": adjustment_date_time,
                "adjustment_type": "RESTATEMENT",
                "adjusted_value": adjusted_value,
                "currency_code": currency_code.strip().upper() if currency_code else None,
            },
            execute=execute,
        )


def _validate_common(order_id: str, adjustment_date_time: str) -> None:
    if not order_id.strip():
        raise ValueError("order_id is required.")
    if not _ADJUSTMENT_DATETIME.fullmatch(adjustment_date_time):
        raise ValueError(
            "adjustment_date_time must use yyyy-mm-dd hh:mm:ss+|-hh:mm, "
            "for example 2026-08-18 15:30:00-03:00."
        )


def _upload_adjustment(ctx: AppContext, customer_id: str, adjustment) -> dict:
    """Upload one adjustment and surface Google row-level partial failures."""
    customer = ctx.client.assert_customer_allowed(customer_id)
    service = ctx.client.service("ConversionAdjustmentUploadService")
    response = service.upload_conversion_adjustments(
        customer_id=customer,
        conversion_adjustments=[adjustment],
        partial_failure=True,
    )
    partial_error = getattr(response, "partial_failure_error", None)
    if partial_error is not None:
        code = int(getattr(partial_error, "code", 0) or 0)
        message = str(getattr(partial_error, "message", "") or "").strip()
        if code or message:
            raise GoogleAdsMcpError(
                "Google Ads rejected the conversion adjustment: "
                + (message or f"partial failure code {code}")
            )

    results = []
    for result in getattr(response, "results", []):
        results.append(
            {
                "conversion_action": getattr(result, "conversion_action", None),
                "order_id": getattr(result, "order_id", None),
            }
        )
    return {
        "job_id": int(getattr(response, "job_id", 0) or 0),
        "results": results,
        "count": len(results),
    }
