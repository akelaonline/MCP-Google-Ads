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
        """Propose switching a campaign to Maximize Clicks bidding,
        optionally with a max CPC bid ceiling (the "techo" per click).

        Note: the Google Ads API models "Maximize Clicks" under the
        `target_spend` field on Campaign (a historical naming artifact —
        there is no `maximize_clicks` field). `cpc_bid_ceiling_micros` is
        the per-click bid cap; `target_spend_micros` is deprecated by
        Google and intentionally left unset.
        """
        _, operation = _campaign_operation(ctx, customer_id, campaign_id)
        if target_cpc is not None:
            operation.update.target_spend.cpc_bid_ceiling_micros = micros(
                target_cpc
            )
            mask = ["target_spend.cpc_bid_ceiling_micros"]
        else:
            operation.update.target_spend.SetInParent()
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
        """Propose switching a campaign to Maximize Conversions bidding,
        optionally with a target CPA cap."""
        _, operation = _campaign_operation(ctx, customer_id, campaign_id)
        if target_cpa is not None:
            operation.update.maximize_conversions.target_cpa_micros = micros(target_cpa)
            mask = ["maximize_conversions.target_cpa_micros"]
        else:
            operation.update.maximize_conversions.SetInParent()
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
    def set_target_cpa(customer_id: str, campaign_id: str, target_cpa: float) -> dict:
        """Propose switching a campaign to Target CPA bidding."""
        _, operation = _campaign_operation(ctx, customer_id, campaign_id)
        operation.update.target_cpa.target_cpa_micros = micros(target_cpa)
        operation.update_mask.CopyFrom(
            field_mask_pb2.FieldMask(paths=["target_cpa.target_cpa_micros"])
        )
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
    def set_target_roas(customer_id: str, campaign_id: str, target_roas: float) -> dict:
        """Propose switching a campaign to Target ROAS bidding.

        Args:
            target_roas: Ratio, e.g. 4.0 means 400% (aim for $4 revenue per $1 spent).
        """
        _, operation = _campaign_operation(ctx, customer_id, campaign_id)
        operation.update.target_roas.target_roas = target_roas
        operation.update_mask.CopyFrom(
            field_mask_pb2.FieldMask(paths=["target_roas.target_roas"])
        )
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
        """Propose switching a campaign to Maximize Conversion Value bidding
        — optimizes for total conversion VALUE (e.g. revenue), not just
        conversion count. Prefer this over Maximize Conversions for
        e-commerce/Shopping campaigns where a $200 sale and a $20 sale
        shouldn't count equally.

        Args:
            target_roas: Optional ROAS floor (e.g. 4.0 = 400%). Without it,
                the campaign spends the full budget maximizing value with no
                floor — set a target_roas once you have enough conversion
                value history to know what floor is realistic.
        """
        _, operation = _campaign_operation(ctx, customer_id, campaign_id)
        if target_roas is not None:
            operation.update.maximize_conversion_value.target_roas = target_roas
            mask = ["maximize_conversion_value.target_roas"]
        else:
            operation.update.maximize_conversion_value.SetInParent()
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
        """Propose switching a campaign to Target Impression Share bidding —
        bids to show your ad in a target % of eligible auctions at a chosen
        page location. Common for brand-defense campaigns (protect the #1
        spot on your own brand terms) or pure visibility plays where clicks/
        conversions aren't the primary goal.

        Args:
            location: One of ANYWHERE_ON_PAGE, TOP_OF_PAGE, ABSOLUTE_TOP_OF_PAGE.
            target_percent: 1-100, e.g. 90.0 = show in the target location 90%
                of the time.
            max_cpc_bid_ceiling: Optional max CPC cap, currency units — without
                one this strategy can bid arbitrarily high to hit the target,
                which is rarely what you want for a competitive term.
        """
        if not (1 <= target_percent <= 100):
            raise ValueError("target_percent must be between 1 and 100.")

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
        """Propose creating a portfolio (shared) bidding strategy — one
        strategy object that multiple campaigns can attach to, so they
        share one learning/optimization pool instead of each campaign
        learning independently. Common when several campaigns target the
        same audience/objective (e.g. three Search campaigns all selling
        the same product line).

        After creating it, attach campaigns to it with
        attach_shared_bidding_strategy.

        Args:
            strategy_type: TARGET_CPA or TARGET_ROAS.
            target_cpa: Required if strategy_type is TARGET_CPA.
            target_roas: Required if strategy_type is TARGET_ROAS.
        """
        if strategy_type == "TARGET_CPA" and target_cpa is None:
            raise ValueError("target_cpa is required when strategy_type is TARGET_CPA.")
        if strategy_type == "TARGET_ROAS" and target_roas is None:
            raise ValueError(
                "target_roas is required when strategy_type is TARGET_ROAS."
            )
        if strategy_type not in ("TARGET_CPA", "TARGET_ROAS"):
            raise ValueError("strategy_type must be TARGET_CPA or TARGET_ROAS.")

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
        """Propose attaching a campaign to an existing portfolio (shared)
        bidding strategy, created with create_portfolio_bidding_strategy.
        Overrides whatever standalone bidding strategy the campaign had.

        Args:
            bidding_strategy_resource_name: The resource_name returned by
                create_portfolio_bidding_strategy (or from
                list_portfolio_bidding_strategies).
        """
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
        """List portfolio (shared) bidding strategies in the account, with
        how many campaigns are currently attached to each."""
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
