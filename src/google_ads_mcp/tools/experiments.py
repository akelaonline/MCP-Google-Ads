"""Campaign experiments (A/B trials) compatible with Google Ads API v25."""

from __future__ import annotations

from datetime import datetime

from google.protobuf.json_format import MessageToDict

from ..context import AppContext
from ..errors import GoogleAdsMcpError, format_google_ads_exception


def _validate_iso_date(value: str | None, field_name: str) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    try:
        datetime.strptime(text, "%Y-%m-%d")
    except ValueError as ex:
        raise ValueError(f"{field_name} must use YYYY-MM-DD.") from ex
    return text


def _lro_name(operation) -> str | None:
    nested = getattr(operation, "operation", None)
    if nested is not None:
        name = getattr(nested, "name", None)
        if name:
            return str(name)
    name = getattr(operation, "name", None)
    return str(name) if name else None


def _protobuf_to_dict(message) -> dict:
    pb = getattr(message, "_pb", message)
    try:
        return MessageToDict(pb, preserving_proto_field_name=True)
    except (TypeError, ValueError):
        return {"message": str(message)}


def register(mcp, ctx: AppContext) -> None:
    @mcp.tool()
    def create_experiment(
        customer_id: str,
        base_campaign_id: str,
        name: str,
        traffic_split_percent: int = 50,
        experiment_type: str = "SEARCH_CUSTOM",
        suffix: str = " [experiment]",
        start_date: str | None = None,
        end_date: str | None = None,
        sync_enabled: bool = False,
    ) -> dict:
        """Propose setting up a system-managed campaign experiment.

        Creates the experiment and its control/treatment arms. The treatment arm
        receives an in-design campaign from Google. Modify that draft with the
        normal campaign/bidding/ad tools, then call ``schedule_experiment``.
        ``start_date`` and ``end_date`` use YYYY-MM-DD in the customer time zone.
        """
        if not (1 <= traffic_split_percent <= 99):
            raise ValueError("traffic_split_percent must be between 1 and 99.")
        if not name.strip():
            raise ValueError("name must not be empty.")
        if len(name.strip()) > 1024:
            raise ValueError("name must be 1024 characters or fewer.")
        if not suffix.strip():
            raise ValueError("suffix is required for system-managed experiments.")

        start = _validate_iso_date(start_date, "start_date")
        end = _validate_iso_date(end_date, "end_date")
        if start and end and end < start:
            raise ValueError("end_date must not be earlier than start_date.")

        customer = ctx.client.assert_customer_allowed(customer_id)
        base_campaign = str(base_campaign_id).strip()
        if not base_campaign.isdigit():
            raise ValueError("base_campaign_id must be numeric.")

        client = ctx.client.raw
        experiment_operation = client.get_type("ExperimentOperation")
        experiment = experiment_operation.create
        experiment.name = name.strip()
        experiment.suffix = suffix
        try:
            experiment.type_ = client.enums.ExperimentTypeEnum[
                experiment_type.strip().upper()
            ].value
        except KeyError as ex:
            raise ValueError(
                f"Unknown experiment_type '{experiment_type}'. Use a current "
                "Google Ads ExperimentType enum name."
            ) from ex
        experiment.status = client.enums.ExperimentStatusEnum.SETUP.value
        experiment.sync_enabled = bool(sync_enabled)
        if start:
            experiment.start_date = start
        if end:
            experiment.end_date = end

        description = (
            f"Create experiment '{name.strip()}' from campaign {base_campaign} "
            f"({traffic_split_percent}% traffic to treatment, {experiment_type})"
        )

        def execute():
            experiment_result = ctx.client.mutate(
                "ExperimentService", customer, [experiment_operation]
            )
            experiment_resource_name = experiment_result.results[0].resource_name

            base_campaign_resource_name = client.get_service(
                "CampaignService"
            ).campaign_path(customer, base_campaign)

            control_arm_operation = client.get_type("ExperimentArmOperation")
            control_arm = control_arm_operation.create
            control_arm.experiment = experiment_resource_name
            control_arm.name = f"{name.strip()} - Control"
            control_arm.control = True
            control_arm.traffic_split = 100 - traffic_split_percent
            control_arm.campaigns.append(base_campaign_resource_name)

            treatment_arm_operation = client.get_type("ExperimentArmOperation")
            treatment_arm = treatment_arm_operation.create
            treatment_arm.experiment = experiment_resource_name
            treatment_arm.name = f"{name.strip()} - Treatment"
            treatment_arm.control = False
            treatment_arm.traffic_split = traffic_split_percent
            # Google creates the treatment in-design campaign for the standard
            # system-managed workflow when no treatment campaign is supplied.

            arm_result = ctx.client.mutate(
                "ExperimentArmService",
                customer,
                [control_arm_operation, treatment_arm_operation],
            )

            return {
                "experiment_resource_name": experiment_resource_name,
                "arms": [r.resource_name for r in arm_result.results],
                "next_step": (
                    "Call list_experiments to get the treatment arm's "
                    "in_design_campaigns, modify the draft, then call "
                    "schedule_experiment."
                ),
            }

        return ctx.safety.propose(
            tool_name="create_experiment",
            customer_id=customer,
            description=description,
            payload={
                "base_campaign_id": base_campaign,
                "name": name.strip(),
                "traffic_split_percent": traffic_split_percent,
                "experiment_type": experiment_type.strip().upper(),
                "suffix": suffix,
                "start_date": start,
                "end_date": end,
                "sync_enabled": bool(sync_enabled),
            },
            execute=execute,
        )

    @mcp.tool()
    def list_experiments(customer_id: str) -> dict:
        """List experiments plus control/treatment arms and draft campaigns."""
        query = """
            SELECT
                experiment.resource_name, experiment.name, experiment.status,
                experiment.type, experiment.suffix, experiment.start_date,
                experiment.end_date, experiment.sync_enabled,
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
    def schedule_experiment(customer_id: str, experiment_resource_name: str) -> dict:
        """Propose scheduling a fully configured system-managed experiment.

        Scheduling is asynchronous. Use ``list_experiment_async_errors`` if the
        operation completes with errors and ``list_experiments`` to inspect the
        resulting experiment state.
        """
        resource = ctx.client.assert_resource_name_customer(
            customer_id,
            experiment_resource_name,
            field_name="experiment_resource_name",
        )
        customer = ctx.client.assert_customer_allowed(customer_id)
        service = ctx.client.service("ExperimentService")

        def execute():
            from google.ads.googleads.errors import GoogleAdsException

            try:
                operation = service.schedule_experiment(resource_name=resource)
            except GoogleAdsException as ex:
                raise GoogleAdsMcpError(format_google_ads_exception(ex)) from ex
            return {
                "experiment_resource_name": resource,
                "long_running_operation": _lro_name(operation),
                "status": "scheduling",
                "next_step": (
                    "Call list_experiments to inspect status. If scheduling fails, "
                    "call list_experiment_async_errors for the detailed errors."
                ),
            }

        return ctx.safety.propose(
            tool_name="schedule_experiment",
            customer_id=customer,
            description=f"Schedule experiment {resource} and allow it to begin serving",
            payload={"experiment_resource_name": resource},
            execute=execute,
        )

    @mcp.tool()
    def list_experiment_async_errors(
        customer_id: str,
        experiment_resource_name: str,
        page_size: int = 1000,
        page_token: str | None = None,
    ) -> dict:
        """List detailed async errors from experiment schedule/promote operations."""
        resource = ctx.client.assert_resource_name_customer(
            customer_id,
            experiment_resource_name,
            field_name="experiment_resource_name",
        )
        if page_size < 1 or page_size > 1000:
            raise ValueError("page_size must be between 1 and 1000.")

        service = ctx.client.service("ExperimentService")
        kwargs = {"resource_name": resource, "page_size": page_size}
        if page_token:
            kwargs["page_token"] = page_token

        from google.ads.googleads.errors import GoogleAdsException

        try:
            pager = service.list_experiment_async_errors(**kwargs)
        except GoogleAdsException as ex:
            raise GoogleAdsMcpError(format_google_ads_exception(ex)) from ex

        page = None
        pages = getattr(pager, "pages", None)
        if pages is not None:
            page = next(iter(pages), None)
        if page is None:
            page = getattr(pager, "_response", pager)

        raw_errors = getattr(page, "errors", None)
        if raw_errors is None:
            raw_errors = list(pager)
        errors = [_protobuf_to_dict(error) for error in raw_errors]
        return {
            "experiment_resource_name": resource,
            "errors": errors,
            "count": len(errors),
            "next_page_token": getattr(page, "next_page_token", None) or None,
        }

    @mcp.tool()
    def promote_experiment(customer_id: str, experiment_resource_name: str) -> dict:
        """Propose promoting treatment changes into the control/base campaign."""
        resource = ctx.client.assert_resource_name_customer(
            customer_id,
            experiment_resource_name,
            field_name="experiment_resource_name",
        )
        customer = ctx.client.assert_customer_allowed(customer_id)
        experiment_service = ctx.client.service("ExperimentService")
        description = (
            f"PROMOTE experiment {resource} — applies treatment changes to the "
            "base campaign and stops the treatment"
        )

        def execute():
            from google.ads.googleads.errors import GoogleAdsException

            try:
                operation = experiment_service.promote_experiment(resource_name=resource)
            except GoogleAdsException as ex:
                raise GoogleAdsMcpError(format_google_ads_exception(ex)) from ex
            return {
                "experiment_resource_name": resource,
                "long_running_operation": _lro_name(operation),
                "status": "promoting",
                "next_step": (
                    "Call list_experiments to inspect status. If promotion fails, "
                    "call list_experiment_async_errors."
                ),
            }

        return ctx.safety.propose(
            tool_name="promote_experiment",
            customer_id=customer,
            description=description,
            payload={"experiment_resource_name": resource},
            execute=execute,
        )

    @mcp.tool()
    def graduate_experiment(
        customer_id: str,
        experiment_resource_name: str,
        experiment_campaign_resource_name: str,
        campaign_budget_resource_name: str,
    ) -> dict:
        """Propose graduating one treatment campaign into an independent campaign."""
        experiment = ctx.client.assert_resource_name_customer(
            customer_id,
            experiment_resource_name,
            field_name="experiment_resource_name",
        )
        campaign = ctx.client.assert_resource_name_customer(
            customer_id,
            experiment_campaign_resource_name,
            field_name="experiment_campaign_resource_name",
        )
        budget = ctx.client.assert_resource_name_customer(
            customer_id,
            campaign_budget_resource_name,
            field_name="campaign_budget_resource_name",
        )
        customer = ctx.client.assert_customer_allowed(customer_id)

        def execute():
            from google.ads.googleads.errors import GoogleAdsException

            raw = ctx.client.raw
            service = raw.get_service("ExperimentService")
            request = raw.get_type("GraduateExperimentRequest")
            request.experiment = experiment
            mapping = raw.get_type("CampaignBudgetMapping")
            mapping.experiment_campaign = campaign
            mapping.campaign_budget = budget
            request.campaign_budget_mappings.append(mapping)
            try:
                service.graduate_experiment(request=request)
            except GoogleAdsException as ex:
                raise GoogleAdsMcpError(format_google_ads_exception(ex)) from ex
            return {
                "experiment_resource_name": experiment,
                "graduated_campaign": campaign,
                "campaign_budget_resource_name": budget,
                "status": "graduated",
            }

        return ctx.safety.propose(
            tool_name="graduate_experiment",
            customer_id=customer,
            description=(
                f"Graduate treatment campaign {campaign} from experiment {experiment} "
                f"as an independent campaign using budget {budget}"
            ),
            payload={
                "experiment_resource_name": experiment,
                "experiment_campaign_resource_name": campaign,
                "campaign_budget_resource_name": budget,
            },
            execute=execute,
        )

    @mcp.tool()
    def end_experiment(customer_id: str, experiment_resource_name: str) -> dict:
        """Propose ending an experiment without promoting its treatment."""
        resource = ctx.client.assert_resource_name_customer(
            customer_id,
            experiment_resource_name,
            field_name="experiment_resource_name",
        )
        customer = ctx.client.assert_customer_allowed(customer_id)
        experiment_service = ctx.client.service("ExperimentService")
        description = f"End experiment {resource} without promoting treatment"

        def execute():
            from google.ads.googleads.errors import GoogleAdsException

            try:
                experiment_service.end_experiment(resource_name=resource)
            except GoogleAdsException as ex:
                raise GoogleAdsMcpError(format_google_ads_exception(ex)) from ex
            return {"ended": resource}

        return ctx.safety.propose(
            tool_name="end_experiment",
            customer_id=customer,
            description=description,
            payload={"experiment_resource_name": resource},
            execute=execute,
        )
