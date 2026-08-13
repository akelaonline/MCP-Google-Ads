"""Campaign experiments (A/B trials) — test a change (new bidding
strategy, new ad copy, budget change) against a control campaign on a
traffic split before rolling it out account-wide.

Workflow: create_experiment (draft, referencing a base campaign) ->
Google Ads UI or a future tool edits the draft/trial arm's settings ->
promote_experiment (roll the winning arm's changes into the base
campaign) or end_experiment (discard). This module covers the
create/list/end/promote lifecycle; editing the trial arm's own
settings once created is done with the normal campaign/bidding/ads
tools, targeting the trial campaign's own customer_id + campaign_id.
"""

from __future__ import annotations

from ..context import AppContext


def register(mcp, ctx: AppContext) -> None:
    @mcp.tool()
    def create_experiment(
        customer_id: str,
        base_campaign_id: str,
        name: str,
        traffic_split_percent: int = 50,
        experiment_type: str = "SEARCH_CUSTOM",
    ) -> dict:
        """Propose creating a campaign experiment (A/B trial) from an
        existing base campaign. Creates a trial arm campaign that starts as
        a copy of the base — make changes to the trial campaign afterward
        with the normal campaign/bidding/ads tools to define what's being
        tested.

        Args:
            base_campaign_id: The existing (control) campaign to branch from.
            traffic_split_percent: % of the base campaign's traffic diverted
                to the trial arm, 1-100. The remainder stays on the control.
            experiment_type: SEARCH_CUSTOM (most common — test anything on a
                Search campaign) or DISPLAY_CUSTOM / DISPLAY_AUTOMATED_BIDDING_STRATEGY
                / SEARCH_AUTOMATED_BIDDING_STRATEGY / SMART_MATCHING for
                narrower, Google-guided experiment types.
        """
        if not (1 <= traffic_split_percent <= 100):
            raise ValueError("traffic_split_percent must be between 1 and 100.")

        client = ctx.client.raw
        customer_id_clean = customer_id.replace("-", "")

        experiment_operation = client.get_type("ExperimentOperation")
        experiment = experiment_operation.create
        experiment.name = name
        experiment.type_ = client.enums.ExperimentTypeEnum[experiment_type]
        experiment.status = client.enums.ExperimentStatusEnum.SETUP
        experiment.traffic_split_percentage = traffic_split_percent

        description = (
            f"Create experiment '{name}' from campaign {base_campaign_id} "
            f"({traffic_split_percent}% traffic to trial arm, {experiment_type})"
        )

        def execute():
            experiment_result = ctx.client.mutate(
                "ExperimentService", customer_id, [experiment_operation]
            )
            experiment_resource_name = experiment_result.results[0].resource_name

            base_campaign_resource_name = client.get_service(
                "CampaignService"
            ).campaign_path(customer_id_clean, base_campaign_id)

            arm_operation = client.get_type("ExperimentArmOperation")
            arm = arm_operation.create
            arm.experiment = experiment_resource_name
            arm.name = f"{name} - Trial"
            arm.control = False
            arm.traffic_split = traffic_split_percent
            arm.campaigns.append(base_campaign_resource_name)

            control_arm_operation = client.get_type("ExperimentArmOperation")
            control_arm = control_arm_operation.create
            control_arm.experiment = experiment_resource_name
            control_arm.name = f"{name} - Control"
            control_arm.control = True
            control_arm.traffic_split = 100 - traffic_split_percent
            control_arm.campaigns.append(base_campaign_resource_name)

            arm_result = ctx.client.mutate(
                "ExperimentArmService",
                customer_id,
                [control_arm_operation, arm_operation],
            )

            return {
                "experiment_resource_name": experiment_resource_name,
                "arms": [r.resource_name for r in arm_result.results],
                "note": (
                    "Experiment created in SETUP status. Use the Google Ads UI "
                    "or scheduling to move it to RUNNING once the trial arm's "
                    "campaign changes are made."
                ),
            }

        return ctx.safety.propose(
            tool_name="create_experiment",
            customer_id=customer_id,
            description=description,
            payload={
                "base_campaign_id": base_campaign_id,
                "name": name,
                "traffic_split_percent": traffic_split_percent,
                "experiment_type": experiment_type,
            },
            execute=execute,
        )

    @mcp.tool()
    def list_experiments(customer_id: str) -> dict:
        """List campaign experiments (A/B trials) on the account, with
        status. Traffic split lives per-arm, not on the experiment itself —
        each arm's split is included via a second query."""
        query = """
            SELECT
                experiment.resource_name, experiment.name, experiment.status,
                experiment.type
            FROM experiment
        """
        rows = ctx.client.search(customer_id, query)

        arms_query = """
            SELECT
                experiment_arm.experiment, experiment_arm.name,
                experiment_arm.control, experiment_arm.traffic_split
            FROM experiment_arm
        """
        arm_rows = ctx.client.search(customer_id, arms_query)
        arms_by_experiment: dict[str, list] = {}
        for arm_row in arm_rows:
            exp_resource = arm_row.get("experiment_arm", {}).get("experiment")
            arms_by_experiment.setdefault(exp_resource, []).append(arm_row)

        for row in rows:
            exp_resource = row.get("experiment", {}).get("resource_name")
            row["arms"] = arms_by_experiment.get(exp_resource, [])

        return {"experiments": rows, "count": len(rows)}

    @mcp.tool()
    def promote_experiment(customer_id: str, experiment_resource_name: str) -> dict:
        """Propose promoting an experiment — permanently applies the trial
        arm's changes to the base campaign and ends the experiment.
        Irreversible; do this once the trial has shown a clear winner.
        """
        client = ctx.client.raw
        experiment_service = client.get_service("ExperimentService")

        description = (
            f"PROMOTE experiment {experiment_resource_name} — applies trial arm "
            f"changes to the base campaign permanently (irreversible)"
        )

        def execute():
            operation = experiment_service.promote_experiment(
                resource_name=experiment_resource_name
            )
            return {"result": str(operation)}

        return ctx.safety.propose(
            tool_name="promote_experiment",
            customer_id=customer_id,
            description=description,
            payload={"experiment_resource_name": experiment_resource_name},
            execute=execute,
        )

    @mcp.tool()
    def end_experiment(customer_id: str, experiment_resource_name: str) -> dict:
        """Propose ending an experiment without promoting it — discards the
        trial arm and its changes, base campaign is unaffected."""
        client = ctx.client.raw
        experiment_service = client.get_service("ExperimentService")

        description = f"End experiment {experiment_resource_name} without promoting (discard trial)"

        def execute():
            experiment_service.end_experiment(resource_name=experiment_resource_name)
            return {"ended": experiment_resource_name}

        return ctx.safety.propose(
            tool_name="end_experiment",
            customer_id=customer_id,
            description=description,
            payload={"experiment_resource_name": experiment_resource_name},
            execute=execute,
        )
