"""Atomic ExperimentArm traffic-split updates for Google Ads API v25."""

from __future__ import annotations

import re

from google.protobuf import field_mask_pb2

from ..context import AppContext

_ARM_RE = re.compile(r"^customers/(\d+)/experimentArms/(\d+)~(\d+)$")


def _propose_traffic_split_update(
    ctx: AppContext,
    customer_id: str,
    arms: list[dict],
    validate_only: bool,
) -> dict:
    customer = ctx.client.assert_customer_allowed(customer_id)
    if len(arms) != 2:
        raise ValueError("arms must contain exactly two experiment arms.")

    raw = ctx.client.raw
    operations = []
    normalized = []
    trial_ids: set[str] = set()
    resource_names: set[str] = set()
    total = 0

    for item in arms:
        resource = ctx.client.assert_resource_name_customer(
            customer,
            str(item.get("experiment_arm_resource_name", "")).strip(),
            field_name="experiment_arm_resource_name",
        )
        match = _ARM_RE.fullmatch(resource)
        if match is None:
            raise ValueError(
                "experiment_arm_resource_name must use "
                "customers/{customer_id}/experimentArms/{experiment_id}~{arm_id}."
            )
        if resource in resource_names:
            raise ValueError("Each experiment arm must be supplied exactly once.")
        resource_names.add(resource)
        trial_ids.add(match.group(2))

        try:
            split = int(item.get("traffic_split"))
        except (TypeError, ValueError) as ex:
            raise ValueError(
                "traffic_split must be an integer between 1 and 100."
            ) from ex
        if not 1 <= split <= 100:
            raise ValueError("traffic_split must be between 1 and 100.")
        total += split

        operation = raw.get_type("ExperimentArmOperation")
        operation.update.resource_name = resource
        operation.update.traffic_split = split
        operation.update_mask.CopyFrom(
            field_mask_pb2.FieldMask(paths=["traffic_split"])
        )
        operations.append(operation)
        normalized.append(
            {
                "experiment_arm_resource_name": resource,
                "traffic_split": split,
            }
        )

    if len(trial_ids) != 1:
        raise ValueError("Both experiment arms must belong to the same experiment.")
    if total != 100:
        raise ValueError(
            "The two experiment-arm traffic splits must total exactly 100."
        )

    def execute():
        return ctx.client.mutate(
            "ExperimentArmService",
            customer,
            operations,
            partial_failure=False,
            validate_only=validate_only,
        )

    # Reuse the established SPEND classification. Invocation tracking stores the
    # actual public MCP tool name separately, so either public alias remains
    # restart-safe while both share one conservative risk category.
    return ctx.safety.propose(
        tool_name="update_experiment_arm",
        customer_id=customer,
        description=(
            f"Atomically update experiment traffic split to "
            f"{normalized[0]['traffic_split']}/{normalized[1]['traffic_split']}"
        ),
        payload={"arms": normalized, "validate_only": bool(validate_only)},
        execute=execute,
    )


def register(mcp, ctx: AppContext) -> None:
    @mcp.tool()
    def update_experiment_arm_traffic_splits(
        customer_id: str,
        arms: list[dict],
        validate_only: bool = False,
    ) -> dict:
        """Propose updating both experiment-arm traffic splits in one RPC.

        Google Ads v25 requires each split to be between 1 and 100 and the two
        trial arms to total exactly 100. Supplying both updates in one
        ``MutateExperimentArms`` request avoids an invalid intermediate state.

        ``arms`` must contain exactly two objects with
        ``experiment_arm_resource_name`` and ``traffic_split``. Both resource
        names must belong to this customer and the same experiment/trial id.
        """
        return _propose_traffic_split_update(ctx, customer_id, arms, validate_only)

    @mcp.tool()
    def update_experiment_traffic_split(
        customer_id: str,
        arms: list[dict],
        validate_only: bool = False,
    ) -> dict:
        """Compatibility alias for ``update_experiment_arm_traffic_splits``.

        Kept so MCP clients/prompts using the shorter v0.16 documentation name do
        not fail. New integrations should prefer
        ``update_experiment_arm_traffic_splits`` because it makes the two-arm
        atomic behavior explicit.
        """
        return _propose_traffic_split_update(ctx, customer_id, arms, validate_only)
