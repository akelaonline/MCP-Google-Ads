"""Bidding strategy tools — change how an existing campaign bids."""

from __future__ import annotations

from google.protobuf import field_mask_pb2

from ..client import micros
from ..context import AppContext


def _campaign_operation(ctx, customer_id, campaign_id):
    client = ctx.client.raw
    operation = client.get_type("CampaignOperation")
    resource_name = client.get_service("CampaignService").campaign_path(
        customer_id.replace("-", ""), campaign_id
    )
    operation.update.resource_name = resource_name
    return client, operation


def register(mcp, ctx: AppContext) -> None:
    @mcp.tool()
    def set_manual_cpc(
        customer_id: str, campaign_id: str, enhanced_cpc: bool = True
    ) -> dict:
        """Propose switching a campaign to Manual CPC bidding."""
        _, operation = _campaign_operation(ctx, customer_id, campaign_id)
        operation.update.manual_cpc.enhanced_cpc_enabled = enhanced_cpc
        operation.update_mask.CopyFrom(
            field_mask_pb2.FieldMask(paths=["manual_cpc.enhanced_cpc_enabled"])
        )
        description = (
            f"Set campaign {campaign_id} bidding -> Manual CPC (eCPC={enhanced_cpc})"
        )

        def execute():
            return ctx.client.mutate("CampaignService", customer_id, [operation])

        return ctx.safety.propose(
            tool_name="set_manual_cpc",
            customer_id=customer_id,
            description=description,
            payload={"campaign_id": campaign_id, "enhanced_cpc": enhanced_cpc},
            execute=execute,
        )

    @mcp.tool()
    def set_maximize_clicks(
        customer_id: str, campaign_id: str, target_cpc: float | None = None
    ) -> dict:
        """Propose switching a campaign to Maximize Clicks bidding."""
        if target_cpc is not None and target_cpc <= 0:
            raise ValueError("target_cpc must be greater than 0.")
        client, operation = _campaign_operation(ctx, customer_id, campaign_id)
        if target_cpc is not None:
            operation.update.target_spend.cpc_bid_ceiling_micros = micros(target_cpc)
            mask = ["target_spend.cpc_bid_ceiling_micros"]
        else:
            client.copy_from(
                operation.update.target_spend,
                client.get_type("TargetSpend"),
            )
            mask = ["target_spend"]
        operation.update_mask.CopyFrom(field_mask_pb2.FieldMask(paths=mask))

        description = f"Set campaign {campaign_id} bidding -> Maximize Clicks" + (
            f" (max CPC ceiling ${target_cpc:,.2f})" if target_cpc else ""
        )

        def execute():
            return ctx.client.mutate("CampaignService", customer_id, [operation])

        return ctx.safety.propose(
            tool_name="set_maximize_clicks",
            customer_id=customer_id,
            description=description,
            payload={"campaign_id": campaign_id, "target_cpc": target_cpc},
            execute=execute,
        )

    @mcp.tool()
    def set_maximize_conversions(
        customer_id: str, campaign_id: str, target_cpa: float | None = None
    ) -> dict:
        """Propose switching a campaign to Maximize Conversions bidding."""
        if target_cpa is not None and target_cpa <= 0:
            raise ValueError("target_cpa must be greater than 0.")
        client, operation = _campaign_operation(ctx, customer_id, campaign_id)
        if target_cpa is not None:
            operation.update.maximize_conversions.target_cpa_micros = micros(target_cpa)
            mask = ["maximize_conversions.target_cpa_micros"]
        else:
            client.copy_from(
                operation.update.maximize_conversions,
                client.get_type("MaximizeConversions"),
            )
            mask = ["maximize_conversions"]
        operation.update_mask.CopyFrom(field_mask_pb2.FieldMask(paths=mask))

        description = f"Set campaign {campaign_id} bidding -> Maximize Conversions" + (
            f" (target CPA ${target_cpa:,.2f})" if target_cpa else ""
        )

        def execute():
            return ctx.client.mutate("CampaignService", customer_id, [operation])

        return ctx.safety.propose(
            tool_name="set_maximize_conversions",
            customer_id=customer_id,
            description=description,
            payload={"campaign_id": campaign_id, "target_cpa": target_cpa},
            execute=execute,
        )

    @mcp.tool()
    def set_target_cpa(
        customer_id: str,
        campaign_id: str,
        target_cpa: float,
        cpc_bid_ceiling: float | None = None,
        cpc_bid_floor: float | None = None,
    ) -> dict:
        """Propose switching a campaign to Target CPA bidding.

        ``cpc_bid_ceiling`` and ``cpc_bid_floor`` bound the max/effective CPC
        in the target currency.
        """
        if target_cpa <= 0:
            raise ValueError("target_cpa must be greater than 0.")
        _validate_ceiling_floor(cpc_bid_ceiling, cpc_bid_floor)
        _, operation = _campaign_operation(ctx, customer_id, campaign_id)
        operation.update.target_cpa.target_cpa_micros = micros(target_cpa)
        paths = ["target_cpa.target_cpa_micros"]
        if cpc_bid_ceiling is not None:
            operation.update.target_cpa.cpc_bid_ceiling_micros = micros(cpc_bid_ceiling)
            paths.append("target_cpa.cpc_bid_ceiling_micros")
        if cpc_bid_floor is not None:
            operation.update.target_cpa.cpc_bid_floor_micros = micros(cpc_bid_floor)
            paths.append("target_cpa.cpc_bid_floor_micros")
        operation.update_mask.CopyFrom(field_mask_pb2.FieldMask(paths=paths))
        description = (
            f"Set campaign {campaign_id} bidding -> Target CPA ${target_cpa:,.2f}"
        )

        def execute():
            return ctx.client.mutate("CampaignService", customer_id, [operation])

        return ctx.safety.propose(
            tool_name="set_target_cpa",
            customer_id=customer_id,
            description=description,
            payload={"campaign_id": campaign_id, "target_cpa": target_cpa},
            execute=execute,
        )

    @mcp.tool()
    def set_target_roas(
        customer_id: str,
        campaign_id: str,
        target_roas: float,
        cpc_bid_ceiling: float | None = None,
        cpc_bid_floor: float | None = None,
    ) -> dict:
        """Propose switching a campaign to Target ROAS bidding.

        ``cpc_bid_ceiling`` and ``cpc_bid_floor`` bound the max/effective CPC
        in the target currency.
        """
        if target_roas <= 0:
            raise ValueError("target_roas must be greater than 0.")
        _validate_ceiling_floor(cpc_bid_ceiling, cpc_bid_floor)
        _, operation = _campaign_operation(ctx, customer_id, campaign_id)
        operation.update.target_roas.target_roas = target_roas
        paths = ["target_roas.target_roas"]
        if cpc_bid_ceiling is not None:
            operation.update.target_roas.cpc_bid_ceiling_micros = micros(cpc_bid_ceiling)
            paths.append("target_roas.cpc_bid_ceiling_micros")
        if cpc_bid_floor is not None:
            operation.update.target_roas.cpc_bid_floor_micros = micros(cpc_bid_floor)
            paths.append("target_roas.cpc_bid_floor_micros")
        operation.update_mask.CopyFrom(field_mask_pb2.FieldMask(paths=paths))
        description = (
            f"Set campaign {campaign_id} bidding -> Target ROAS {target_roas:.2f}"
        )

        def execute():
            return ctx.client.mutate("CampaignService", customer_id, [operation])

        return ctx.safety.propose(
            tool_name="set_target_roas",
            customer_id=customer_id,
            description=description,
            payload={"campaign_id": campaign_id, "target_roas": target_roas},
            execute=execute,
        )

    @mcp.tool()
    def set_maximize_conversion_value(
        customer_id: str, campaign_id: str, target_roas: float | None = None
    ) -> dict:
        """Propose switching to Maximize Conversion Value bidding."""
        if target_roas is not None and target_roas <= 0:
            raise ValueError("target_roas must be greater than 0.")
        client, operation = _campaign_operation(ctx, customer_id, campaign_id)
        if target_roas is not None:
            operation.update.maximize_conversion_value.target_roas = target_roas
            mask = ["maximize_conversion_value.target_roas"]
        else:
            client.copy_from(
                operation.update.maximize_conversion_value,
                client.get_type("MaximizeConversionValue"),
            )
            mask = ["maximize_conversion_value"]
        operation.update_mask.CopyFrom(field_mask_pb2.FieldMask(paths=mask))

        description = (
            f"Set campaign {campaign_id} bidding -> Maximize Conversion Value"
            + (f" (target ROAS {target_roas:.2f})" if target_roas else "")
        )

        def execute():
            return ctx.client.mutate("CampaignService", customer_id, [operation])

        return ctx.safety.propose(
            tool_name="set_maximize_conversion_value",
            customer_id=customer_id,
            description=description,
            payload={"campaign_id": campaign_id, "target_roas": target_roas},
            execute=execute,
        )

    @mcp.tool()
    def set_target_impression_share(
        customer_id: str,
        campaign_id: str,
        location: str,
        target_percent: float,
        max_cpc_bid_ceiling: float | None = None,
    ) -> dict:
        """Propose switching a campaign to Target Impression Share bidding."""
        if not (1 <= target_percent <= 100):
            raise ValueError("target_percent must be between 1 and 100.")
        if max_cpc_bid_ceiling is not None and max_cpc_bid_ceiling <= 0:
            raise ValueError("max_cpc_bid_ceiling must be greater than 0.")

        client, operation = _campaign_operation(ctx, customer_id, campaign_id)
        tis = operation.update.target_impression_share
        tis.location = client.enums.TargetImpressionShareLocationEnum[location].value
        tis.location_fraction_micros = round(target_percent * 10_000)
        mask = [
            "target_impression_share.location",
            "target_impression_share.location_fraction_micros",
        ]
        if max_cpc_bid_ceiling is not None:
            tis.cpc_bid_ceiling_micros = micros(max_cpc_bid_ceiling)
            mask.append("target_impression_share.cpc_bid_ceiling_micros")
        operation.update_mask.CopyFrom(field_mask_pb2.FieldMask(paths=mask))

        description = (
            f"Set campaign {campaign_id} bidding -> Target Impression Share "
            f"({target_percent:.0f}% {location})"
            + (f", max CPC ${max_cpc_bid_ceiling:,.2f}" if max_cpc_bid_ceiling else "")
        )

        def execute():
            return ctx.client.mutate("CampaignService", customer_id, [operation])

        return ctx.safety.propose(
            tool_name="set_target_impression_share",
            customer_id=customer_id,
            description=description,
            payload={
                "campaign_id": campaign_id,
                "location": location,
                "target_percent": target_percent,
                "max_cpc_bid_ceiling": max_cpc_bid_ceiling,
            },
            execute=execute,
        )

    @mcp.tool()
    def create_portfolio_bidding_strategy(
        customer_id: str,
        name: str,
        strategy_type: str,
        target_cpa: float | None = None,
        target_roas: float | None = None,
    ) -> dict:
        """Propose creating a portfolio/shared TARGET_CPA or TARGET_ROAS strategy."""
        if strategy_type == "TARGET_CPA" and target_cpa is None:
            raise ValueError("target_cpa is required when strategy_type is TARGET_CPA.")
        if strategy_type == "TARGET_ROAS" and target_roas is None:
            raise ValueError("target_roas is required when strategy_type is TARGET_ROAS.")
        if strategy_type not in ("TARGET_CPA", "TARGET_ROAS"):
            raise ValueError("strategy_type must be TARGET_CPA or TARGET_ROAS.")
        if target_cpa is not None and target_cpa <= 0:
            raise ValueError("target_cpa must be greater than 0.")
        if target_roas is not None and target_roas <= 0:
            raise ValueError("target_roas must be greater than 0.")

        client = ctx.client.raw
        operation = client.get_type("BiddingStrategyOperation")
        strategy = operation.create
        strategy.name = name
        if strategy_type == "TARGET_CPA":
            strategy.target_cpa.target_cpa_micros = micros(target_cpa)
        else:
            strategy.target_roas.target_roas = target_roas

        description = (
            f"Create portfolio bidding strategy '{name}' ({strategy_type}"
            + (f", target CPA ${target_cpa:,.2f}" if target_cpa else "")
            + (f", target ROAS {target_roas:.2f}" if target_roas else "")
            + ")"
        )

        def execute():
            return ctx.client.mutate("BiddingStrategyService", customer_id, [operation])

        return ctx.safety.propose(
            tool_name="create_portfolio_bidding_strategy",
            customer_id=customer_id,
            description=description,
            payload={
                "name": name,
                "strategy_type": strategy_type,
                "target_cpa": target_cpa,
                "target_roas": target_roas,
            },
            execute=execute,
        )

    @mcp.tool()
    def attach_shared_bidding_strategy(
        customer_id: str, campaign_id: str, bidding_strategy_resource_name: str
    ) -> dict:
        """Propose attaching a campaign to an existing portfolio strategy."""
        _, operation = _campaign_operation(ctx, customer_id, campaign_id)
        operation.update.bidding_strategy = bidding_strategy_resource_name
        operation.update_mask.CopyFrom(
            field_mask_pb2.FieldMask(paths=["bidding_strategy"])
        )

        description = (
            f"Attach campaign {campaign_id} to portfolio bidding strategy "
            f"{bidding_strategy_resource_name}"
        )

        def execute():
            return ctx.client.mutate("CampaignService", customer_id, [operation])

        return ctx.safety.propose(
            tool_name="attach_shared_bidding_strategy",
            customer_id=customer_id,
            description=description,
            payload={
                "campaign_id": campaign_id,
                "bidding_strategy_resource_name": bidding_strategy_resource_name,
            },
            execute=execute,
        )

    @mcp.tool()
    def list_portfolio_bidding_strategies(customer_id: str) -> dict:
        """List portfolio/shared bidding strategies in the account."""
        query = """
            SELECT
                bidding_strategy.id, bidding_strategy.name,
                bidding_strategy.type, bidding_strategy.status,
                bidding_strategy.campaign_count,
                bidding_strategy.target_cpa.target_cpa_micros,
                bidding_strategy.target_roas.target_roas
            FROM bidding_strategy
            ORDER BY bidding_strategy.name
        """
        rows = ctx.client.search(customer_id, query)
        return {"bidding_strategies": rows, "count": len(rows)}


def _validate_ceiling_floor(
    cpc_bid_ceiling: float | None,
    cpc_bid_floor: float | None,
) -> None:
    if cpc_bid_ceiling is not None and cpc_bid_ceiling <= 0:
        raise ValueError("cpc_bid_ceiling must be greater than 0.")
    if cpc_bid_floor is not None and cpc_bid_floor <= 0:
        raise ValueError("cpc_bid_floor must be greater than 0.")
    if (
        cpc_bid_ceiling is not None
        and cpc_bid_floor is not None
        and cpc_bid_floor > cpc_bid_ceiling
    ):
        raise ValueError("cpc_bid_floor cannot exceed cpc_bid_ceiling.")
