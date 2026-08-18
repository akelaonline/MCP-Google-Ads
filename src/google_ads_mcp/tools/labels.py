"""Label management tools for Google Ads API v25."""

from __future__ import annotations

import re

from google.protobuf import field_mask_pb2

from ..context import AppContext

_HEX_COLOR = re.compile(r"^#(?:[0-9A-Fa-f]{3}|[0-9A-Fa-f]{6})$")


def register(mcp, ctx: AppContext) -> None:
    @mcp.tool()
    def list_labels(customer_id: str) -> dict:
        """List labels defined in a Google Ads customer."""
        query = """
            SELECT
                label.id,
                label.name,
                label.status,
                label.text_label.background_color,
                label.text_label.description,
                label.resource_name
            FROM label
            ORDER BY label.name
        """
        rows = ctx.client.search(customer_id, query)
        return {"labels": rows, "count": len(rows)}

    @mcp.tool()
    def create_label(
        customer_id: str,
        name: str,
        background_color: str | None = None,
        description: str | None = None,
    ) -> dict:
        """Propose creating a customer label."""
        _validate_label(name, background_color, description)
        client = ctx.client.raw
        operation = client.get_type("LabelOperation")
        label = operation.create
        label.name = name.strip()
        if background_color:
            label.text_label.background_color = background_color
        if description:
            label.text_label.description = description

        def execute():
            return ctx.client.mutate("LabelService", customer_id, [operation])

        return ctx.safety.propose(
            tool_name="create_label",
            customer_id=customer_id,
            description=f"Create Google Ads label '{name.strip()}'",
            payload={
                "name": name.strip(),
                "background_color": background_color,
                "description": description,
            },
            execute=execute,
        )

    @mcp.tool()
    def update_label(
        customer_id: str,
        label_id: str,
        name: str | None = None,
        background_color: str | None = None,
        description: str | None = None,
    ) -> dict:
        """Propose updating label name/color/description."""
        if name is None and background_color is None and description is None:
            raise ValueError("Provide at least one field to update.")
        if name is not None:
            _validate_label(name, None, None)
        if background_color is not None and not _HEX_COLOR.fullmatch(background_color):
            raise ValueError("background_color must be #RGB or #RRGGBB.")
        if description is not None and len(description) > 200:
            raise ValueError("description must be 200 characters or fewer.")

        client = ctx.client.raw
        operation = client.get_type("LabelOperation")
        operation.update.resource_name = client.get_service("LabelService").label_path(
            customer_id.replace("-", ""), label_id
        )
        paths: list[str] = []
        if name is not None:
            operation.update.name = name.strip()
            paths.append("name")
        if background_color is not None:
            operation.update.text_label.background_color = background_color
            paths.append("text_label.background_color")
        if description is not None:
            operation.update.text_label.description = description
            paths.append("text_label.description")
        operation.update_mask.CopyFrom(field_mask_pb2.FieldMask(paths=paths))

        def execute():
            return ctx.client.mutate("LabelService", customer_id, [operation])

        return ctx.safety.propose(
            tool_name="update_label",
            customer_id=customer_id,
            description=f"Update Google Ads label {label_id}: {', '.join(paths)}",
            payload={
                "label_id": label_id,
                "name": name,
                "background_color": background_color,
                "description": description,
            },
            execute=execute,
        )

    @mcp.tool()
    def remove_label(customer_id: str, label_id: str) -> dict:
        """Propose permanently removing a label."""
        client = ctx.client.raw
        operation = client.get_type("LabelOperation")
        operation.remove = client.get_service("LabelService").label_path(
            customer_id.replace("-", ""), label_id
        )

        def execute():
            return ctx.client.mutate("LabelService", customer_id, [operation])

        return ctx.safety.propose(
            tool_name="remove_label",
            customer_id=customer_id,
            description=f"Permanently remove Google Ads label {label_id}",
            payload={"label_id": label_id},
            execute=execute,
        )

    @mcp.tool()
    def attach_label_to_campaign(
        customer_id: str,
        campaign_id: str,
        label_id: str,
    ) -> dict:
        """Propose attaching an existing label to a campaign."""
        client = ctx.client.raw
        operation = client.get_type("CampaignLabelOperation")
        relation = operation.create
        relation.campaign = client.get_service("CampaignService").campaign_path(
            customer_id.replace("-", ""), campaign_id
        )
        relation.label = client.get_service("LabelService").label_path(
            customer_id.replace("-", ""), label_id
        )

        def execute():
            return ctx.client.mutate("CampaignLabelService", customer_id, [operation])

        return ctx.safety.propose(
            tool_name="attach_label_to_campaign",
            customer_id=customer_id,
            description=f"Attach label {label_id} to campaign {campaign_id}",
            payload={"campaign_id": campaign_id, "label_id": label_id},
            execute=execute,
        )

    @mcp.tool()
    def remove_label_from_campaign(
        customer_id: str,
        campaign_id: str,
        label_id: str,
    ) -> dict:
        """Propose removing a campaign-label relationship."""
        customer = customer_id.replace("-", "")
        operation = ctx.client.raw.get_type("CampaignLabelOperation")
        operation.remove = f"customers/{customer}/campaignLabels/{campaign_id}~{label_id}"

        def execute():
            return ctx.client.mutate("CampaignLabelService", customer_id, [operation])

        return ctx.safety.propose(
            tool_name="remove_label_from_campaign",
            customer_id=customer_id,
            description=f"Detach label {label_id} from campaign {campaign_id}",
            payload={"campaign_id": campaign_id, "label_id": label_id},
            execute=execute,
        )

    @mcp.tool()
    def attach_label_to_ad_group(
        customer_id: str,
        ad_group_id: str,
        label_id: str,
    ) -> dict:
        """Propose attaching an existing label to an ad group."""
        client = ctx.client.raw
        operation = client.get_type("AdGroupLabelOperation")
        relation = operation.create
        relation.ad_group = client.get_service("AdGroupService").ad_group_path(
            customer_id.replace("-", ""), ad_group_id
        )
        relation.label = client.get_service("LabelService").label_path(
            customer_id.replace("-", ""), label_id
        )

        def execute():
            return ctx.client.mutate("AdGroupLabelService", customer_id, [operation])

        return ctx.safety.propose(
            tool_name="attach_label_to_ad_group",
            customer_id=customer_id,
            description=f"Attach label {label_id} to ad group {ad_group_id}",
            payload={"ad_group_id": ad_group_id, "label_id": label_id},
            execute=execute,
        )

    @mcp.tool()
    def remove_label_from_ad_group(
        customer_id: str,
        ad_group_id: str,
        label_id: str,
    ) -> dict:
        """Propose removing an ad-group-label relationship."""
        customer = customer_id.replace("-", "")
        operation = ctx.client.raw.get_type("AdGroupLabelOperation")
        operation.remove = f"customers/{customer}/adGroupLabels/{ad_group_id}~{label_id}"

        def execute():
            return ctx.client.mutate("AdGroupLabelService", customer_id, [operation])

        return ctx.safety.propose(
            tool_name="remove_label_from_ad_group",
            customer_id=customer_id,
            description=f"Detach label {label_id} from ad group {ad_group_id}",
            payload={"ad_group_id": ad_group_id, "label_id": label_id},
            execute=execute,
        )


def _validate_label(
    name: str,
    background_color: str | None,
    description: str | None,
) -> None:
    stripped = name.strip()
    if not (1 <= len(stripped) <= 80):
        raise ValueError("name must be between 1 and 80 characters.")
    if background_color is not None and not _HEX_COLOR.fullmatch(background_color):
        raise ValueError("background_color must be #RGB or #RRGGBB.")
    if description is not None and len(description) > 200:
        raise ValueError("description must be 200 characters or fewer.")
