"""Performance Max asset-group signals and listing-group filter trees for API v25."""

from __future__ import annotations

from google.protobuf import json_format

from ..context import AppContext
from ..errors import GoogleAdsMcpError

_SIGNAL_TYPES = {"AUDIENCE", "SEARCH_THEME", "LOCAL_SERVICES_ID", "VERTICAL_ADS_ITEM_GROUP_RULE_LIST"}
_LISTING_TYPES = {"SUBDIVISION", "UNIT_INCLUDED", "UNIT_EXCLUDED"}
_LISTING_SOURCES = {"RETAIL", "SHOPPING", "WEBPAGE"}
_DIMENSION_KEYS = {
    "product_brand",
    "product_category",
    "product_channel",
    "product_condition",
    "product_custom_attribute",
    "product_item_id",
    "product_type",
    "webpage",
}


def _id(value: str, field_name: str) -> str:
    text = str(value).strip()
    if not text.isdigit() or int(text) <= 0:
        raise ValueError(f"{field_name} must be a positive numeric ID.")
    return text


def _owned(ctx: AppContext, customer: str, resource: str, field_name: str) -> str:
    return ctx.client.assert_resource_name_customer(customer, resource, field_name=field_name)


def _depth(resource: str, parent_map: dict[str, str | None]) -> int:
    depth = 0
    seen: set[str] = set()
    current = resource
    while current in parent_map and parent_map[current]:
        if current in seen:
            raise GoogleAdsMcpError("Existing listing-group tree contains a cycle.")
        seen.add(current)
        depth += 1
        current = str(parent_map[current])
    return depth


def _parse_dimension(raw, value: dict):
    if not isinstance(value, dict) or len(value) != 1:
        raise ValueError("case_value must be an object with exactly one listing dimension.")
    key = next(iter(value))
    if key not in _DIMENSION_KEYS:
        raise ValueError(f"Unsupported listing dimension {key!r}; use one of {sorted(_DIMENSION_KEYS)}.")
    message = raw.get_type("ListingGroupFilterDimension")
    try:
        json_format.ParseDict(value, message._pb, ignore_unknown_fields=False)
    except Exception as ex:
        raise ValueError(f"Invalid case_value for {key}: {ex}") from ex
    return message


def register(mcp, ctx: AppContext) -> None:
    @mcp.tool()
    def list_asset_group_signals(customer_id: str, asset_group_id: str | None = None) -> dict:
        """List PMax asset-group signals, including audience/search/local/vertical signals."""
        where = ""
        if asset_group_id is not None:
            where = f"WHERE asset_group.id = {_id(asset_group_id, 'asset_group_id')}"
        rows = ctx.client.search(
            customer_id,
            f"""
            SELECT asset_group_signal.resource_name,
                   asset_group_signal.asset_group,
                   asset_group_signal.approval_status,
                   asset_group_signal.disapproval_reasons,
                   asset_group_signal.audience.audience,
                   asset_group_signal.search_theme.text,
                   asset_group_signal.local_services_id.service_id,
                   asset_group_signal.vertical_ads_item_group_rule_list.shared_set
            FROM asset_group_signal
            {where}
            ORDER BY asset_group_signal.resource_name
            """,
        )
        return {"asset_group_signals": rows, "count": len(rows)}

    @mcp.tool()
    def add_asset_group_signal(
        customer_id: str,
        asset_group_id: str,
        signal_type: str,
        value: str,
        validate_only: bool = False,
    ) -> dict:
        """Propose adding one PMax signal.

        signal_type: AUDIENCE, SEARCH_THEME, LOCAL_SERVICES_ID, or
        VERTICAL_ADS_ITEM_GROUP_RULE_LIST. LOCAL_SERVICES_ID is allowlist-only.
        """
        customer = ctx.client.assert_customer_allowed(customer_id)
        asset_group = _id(asset_group_id, "asset_group_id")
        kind = signal_type.strip().upper()
        if kind not in _SIGNAL_TYPES:
            raise ValueError(f"signal_type must be one of {sorted(_SIGNAL_TYPES)}.")
        raw = ctx.client.raw
        operation = raw.get_type("AssetGroupSignalOperation")
        signal = operation.create
        signal.asset_group = f"customers/{customer}/assetGroups/{asset_group}"
        clean_value = str(value).strip()
        if not clean_value:
            raise ValueError("value must not be empty.")
        if kind == "AUDIENCE":
            resource = _owned(ctx, customer, clean_value, "audience_resource_name")
            signal.audience.audience = resource
            safe_value = resource
        elif kind == "SEARCH_THEME":
            if len(clean_value) > 80:
                raise ValueError("SEARCH_THEME must be at most 80 characters.")
            signal.search_theme.text = clean_value
            safe_value = clean_value
        elif kind == "LOCAL_SERVICES_ID":
            signal.local_services_id.service_id = clean_value
            safe_value = clean_value
        else:
            resource = _owned(ctx, customer, clean_value, "shared_set_resource_name")
            signal.vertical_ads_item_group_rule_list.shared_set = resource
            safe_value = resource

        def execute():
            return ctx.client.mutate(
                "AssetGroupSignalService", customer, [operation], validate_only=validate_only
            )

        return ctx.safety.propose(
            tool_name="add_asset_group_signal",
            customer_id=customer,
            description=f"Add {kind} signal to asset group {asset_group}",
            payload={
                "asset_group_id": asset_group,
                "signal_type": kind,
                "value": safe_value,
                "validate_only": validate_only,
            },
            execute=execute,
        )

    @mcp.tool()
    def remove_asset_group_signal(
        customer_id: str,
        asset_group_signal_resource_name: str,
        validate_only: bool = False,
    ) -> dict:
        """Propose removing one PMax asset-group signal."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        resource = _owned(
            ctx, customer, asset_group_signal_resource_name, "asset_group_signal_resource_name"
        )
        operation = ctx.client.raw.get_type("AssetGroupSignalOperation")
        operation.remove = resource

        def execute():
            return ctx.client.mutate(
                "AssetGroupSignalService", customer, [operation], validate_only=validate_only
            )

        return ctx.safety.propose(
            tool_name="remove_asset_group_signal",
            customer_id=customer,
            description=f"Remove PMax asset-group signal {resource}",
            payload={"asset_group_signal_resource_name": resource, "validate_only": validate_only},
            execute=execute,
        )

    @mcp.tool()
    def list_asset_group_listing_filters(customer_id: str, asset_group_id: str) -> dict:
        """List the full PMax listing-group filter tree for one asset group."""
        asset_group = _id(asset_group_id, "asset_group_id")
        rows = ctx.client.search(
            customer_id,
            f"""
            SELECT asset_group_listing_group_filter.resource_name,
                   asset_group_listing_group_filter.asset_group,
                   asset_group_listing_group_filter.id,
                   asset_group_listing_group_filter.type,
                   asset_group_listing_group_filter.listing_source,
                   asset_group_listing_group_filter.parent_listing_group_filter,
                   asset_group_listing_group_filter.case_value,
                   asset_group_listing_group_filter.path
            FROM asset_group_listing_group_filter
            WHERE asset_group.id = {asset_group}
            ORDER BY asset_group_listing_group_filter.id
            """,
        )
        return {"asset_group_id": asset_group, "listing_group_filters": rows, "count": len(rows)}

    @mcp.tool()
    def replace_asset_group_listing_filter_tree(
        customer_id: str,
        asset_group_id: str,
        nodes: list[dict],
        listing_source: str = "RETAIL",
        replace_existing: bool = True,
    ) -> dict:
        """Propose atomically replacing/creating a complete PMax listing tree.

        Each node requires a unique negative ``temp_id``, ``type`` and optional
        ``parent_temp_id``/``case_value``. Exactly one root must have no parent and
        no case_value. ``case_value`` uses protobuf JSON shape, e.g.
        {"product_brand": {"value": "Acme"}}. Supported top-level dimensions are
        brand/category/channel/condition/custom attribute/item id/type/webpage.
        """
        customer = ctx.client.assert_customer_allowed(customer_id)
        asset_group = _id(asset_group_id, "asset_group_id")
        if not nodes:
            raise ValueError("nodes must contain a complete listing-group tree.")
        source = listing_source.strip().upper()
        if source not in _LISTING_SOURCES:
            raise ValueError(f"listing_source must be one of {sorted(_LISTING_SOURCES)}.")
        raw = ctx.client.raw
        asset_group_resource = f"customers/{customer}/assetGroups/{asset_group}"

        normalized: list[dict] = []
        seen_ids: set[int] = set()
        roots = 0
        for item in nodes:
            temp_id = int(item.get("temp_id", 0))
            if temp_id >= 0:
                raise ValueError("Every node temp_id must be a unique negative integer.")
            if temp_id in seen_ids:
                raise ValueError(f"Duplicate temp_id {temp_id}.")
            seen_ids.add(temp_id)
            node_type = str(item.get("type", "")).strip().upper()
            if node_type not in _LISTING_TYPES:
                raise ValueError(f"Node type must be one of {sorted(_LISTING_TYPES)}.")
            parent = item.get("parent_temp_id")
            if parent is not None:
                parent = int(parent)
                if parent >= 0:
                    raise ValueError("parent_temp_id must be a negative temp_id from nodes.")
            case_value = item.get("case_value")
            if parent is None:
                roots += 1
                if case_value not in (None, {}):
                    raise ValueError("The root node cannot have case_value.")
            elif not case_value:
                raise ValueError("Non-root nodes require case_value, including explicit Other nodes.")
            normalized.append(
                {"temp_id": temp_id, "type": node_type, "parent_temp_id": parent, "case_value": case_value}
            )
        if roots != 1:
            raise ValueError("Exactly one root node is required.")
        for item in normalized:
            parent = item["parent_temp_id"]
            if parent is not None and parent not in seen_ids:
                raise ValueError(f"parent_temp_id {parent} is not present in nodes.")

        def execute():
            operations = []
            if replace_existing:
                existing = ctx.client.search(
                    customer,
                    f"""
                    SELECT asset_group_listing_group_filter.resource_name,
                           asset_group_listing_group_filter.parent_listing_group_filter
                    FROM asset_group_listing_group_filter
                    WHERE asset_group.id = {asset_group}
                    """,
                )
                parent_map: dict[str, str | None] = {}
                for row in existing:
                    data = row.get("asset_group_listing_group_filter", {})
                    resource = data.get("resource_name")
                    if resource:
                        parent_map[str(resource)] = data.get("parent_listing_group_filter") or None
                for resource in sorted(parent_map, key=lambda r: _depth(r, parent_map), reverse=True):
                    mutate = raw.get_type("MutateOperation")
                    mutate.asset_group_listing_group_filter_operation.remove = resource
                    operations.append(mutate)

            for item in normalized:
                mutate = raw.get_type("MutateOperation")
                node = mutate.asset_group_listing_group_filter_operation.create
                temp_id = item["temp_id"]
                node.resource_name = (
                    f"customers/{customer}/assetGroupListingGroupFilters/"
                    f"{asset_group}~{temp_id}"
                )
                node.asset_group = asset_group_resource
                node.type_ = getattr(raw.enums.ListingGroupFilterTypeEnum, item["type"])
                node.listing_source = getattr(raw.enums.ListingGroupFilterListingSourceEnum, source)
                parent = item["parent_temp_id"]
                if parent is not None:
                    node.parent_listing_group_filter = (
                        f"customers/{customer}/assetGroupListingGroupFilters/"
                        f"{asset_group}~{parent}"
                    )
                    dimension = _parse_dimension(raw, item["case_value"])
                    raw.copy_from(node.case_value, dimension)
                operations.append(mutate)

            return ctx.client.mutate_atomic(customer, operations)

        return ctx.safety.propose(
            tool_name="replace_asset_group_listing_filter_tree",
            customer_id=customer,
            description=(
                f"{'Replace' if replace_existing else 'Create'} PMax listing-group tree "
                f"for asset group {asset_group} with {len(normalized)} node(s)"
            ),
            payload={
                "asset_group_id": asset_group,
                "listing_source": source,
                "replace_existing": bool(replace_existing),
                "nodes": normalized,
            },
            execute=execute,
        )
