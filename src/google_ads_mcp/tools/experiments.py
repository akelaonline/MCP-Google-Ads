"""Campaign experiments (A/B trials) compatible with Google Ads API v25."""

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
        suffix: str = " [experiment]",
    ) -> dict:
        """Propose setting up a system-managed campaign experiment.

        The control arm references ``base_campaign_id``. The treatment arm must
        NOT reference the base campaign: for system-managed experiments Google
        creates its in-design draft campaign automatically. Use
        ``list_experiments`` afterward to retrieve ``in_design_campaigns`` and
        modify that draft with the normal campaign/bidding/ad tools before
        scheduling the experiment.
        """
        if not (1 <= traffic_split_percent <= 99):
            raise ValueError("traffic_split_percent must be between 1 and 99.")
        if not name.strip():
            raise ValueError("name must not be empty.")
        if not suffix.strip():
            raise ValueError("suffix is required for system-managed experiments.")

        client = ctx.client.raw
        customer_id_clean = customer_id.replace("-", "")

        experiment_operation = client.get_type("ExperimentOperation")
        experiment = experiment_operation.create
        experiment.name = name
        experiment.suffix = suffix
        experiment.type_ = client.enums.ExperimentTypeEnum[experiment_type].value
        experiment.status = client.enums.ExperimentStatusEnum.SETUP.value

        description = (
            f"Create experiment '{name}' from campaign {base_campaign_id} "
            f"({traffic_split_percent}% traffic to treatment, {experiment_type})"
        )

        def execute():
            experiment_result = ctx.client.mutate(
                "ExperimentService", customer_id, [experiment_operation]
            )
            experiment_resource_name = experiment_result.results[0].resource_name

            base_campaign_resource_name = client.get_service(
                "CampaignService"
            ).campaign_path(customer_id_clean, base_campaign_id)

            control_arm_operation = client.get_type("ExperimentArmOperation")
            control_arm = control_arm_operation.create
            control_arm.experiment = experiment_resource_name
            control_arm.name = f"{name} - Control"
            control_arm.control = True
            control_arm.traffic_split = 100 - traffic_split_percent
            control_arm.campaigns.append(base_campaign_resource_name)

            treatment_arm_operation = client.get_type("ExperimentArmOperation")
            treatment_arm = treatment_arm_operation.create
            treatment_arm.experiment = experiment_resource_name
            treatment_arm.name = f"{name} - Treatment"
            treatment_arm.control = False
            treatment_arm.traffic_split = traffic_split_percent
            # Deliberately no campaigns here. Google generates the draft/in-design
            # campaign for the treatment arm in standard system-managed experiments.

            arm_result = ctx.client.mutate(
                "ExperimentArmService",
                customer_id,
                [control_arm_operation, treatment_arm_operation],
            )

            return {
                "experiment_resource_name": experiment_resource_name,
                "arms": [r.resource_name for r in arm_result.results],
                "next_step": (
                    "Call list_experiments to get the treatment arm's "
                    "in_design_campaigns, modify that draft, then schedule the experiment."
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
                "suffix": suffix,
            },
            execute=execute,
        )

    @mcp.tool()
    def list_experiments(customer_id: str) -> dict:
        """List experiments plus control/treatment arms and draft campaigns."""
        query = """
            SELECT
                experiment.resource_name, experiment.name, experiment.status,
                experiment.type, experiment.suffix,
                experiment.promote_status, experiment.long_running_operation
            FROM experiment
        """
        rows = ctx.client.search(customer_id, query)

        arms_query = """
            SELECT
                experiment_arm.resource_name, experiment_arm.experiment,
                experiment_arm.name, experiment_arm.control,
                experiment_arm.traffic_split, experiment_arm.campaigns,
                experiment_arm.in_design_campaigns
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
        """Propose promoting a completed experiment into its base campaign."""
        client = ctx.client.raw
        experiment_service = client.get_service("ExperimentService")
        description = (
            f"PROMOTE experiment {experiment_resource_name} — applies treatment "
            "changes to the base campaign (irreversible)"
        )

        def execute():
            operation = experiment_service.promote_experiment(
                resource_name=experiment_resource_name
            )
            return {"operation": str(operation)}

        return ctx.safety.propose(
            tool_name="promote_experiment",
            customer_id=customer_id,
            description=description,
            payload={"experiment_resource_name": experiment_resource_name},
            execute=execute,
        )

    @mcp.tool()
    def end_experiment(customer_id: str, experiment_resource_name: str) -> dict:
        """Propose ending an experiment without promoting its treatment."""
        client = ctx.client.raw
        experiment_service = client.get_service("ExperimentService")
        description = (
            f"End experiment {experiment_resource_name} without promoting treatment"
        )

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
