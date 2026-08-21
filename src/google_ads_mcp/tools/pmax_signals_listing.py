"""Performance Max asset-group signals and listing-group filter trees for API v25."""

from __future__ import annotations

from google.protobuf import json_format

from ..context import AppContext
from ..errors import GoogleAdsMcpError

_SIGNAL_TYPES = {
    "AUDIENCE",
    "SEARCH_THEME",
    "LOCAL_SERVICES_ID",
    "VERTICAL_ADS_ITEM_GROUP_RULE_LIST",
}
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
    "retail_filter_bundle",
    "webpage",
}


def _id(value: str, field_name: str) -> str:
    text = str(value).strip()
    if not text.isdigit() or int(text) <= 0:
        raise ValueError(f"{field_name} must be a positive numeric ID.")
    return text


def _owned(ctx: AppContext, customer: str, resource: str, field_name: str) -> str:
    return ctx.client.assert_resource_name_customer(
        customer, resource, field_name=field_name
    )


def _depth(resource: str, parent_map: dict[str, str | None]) -> int:
    depth = 0
    seen: set[str] = set()
    current = resource
    while parent_map.get(current):
        if current in seen:
            raise GoogleAdsMcpError("Existing listing-group tree contains a cycle.")
        seen.add(current)
        depth += 1
        current = str(parent_map[current])
    return depth


def _parse_dimension(raw, value: dict):
    if not isinstance(value, dict) or len(value) != 1:
        raise ValueError(
            "case_value must be an object with exactly one listing dimension."
        )
    key = next(iter(value))
    if key not in _DIMENSION_KEYS:
        raise ValueError(
            f"Unsupported listing dimension {key!r}; use one of {sorted(_DIMENSION_KEYS)}."
        )
    message = raw.get_type("ListingGroupFilterDimension")
    try:
        json_format.ParseDict(value, message._pb, ignore_unknown_fields=False)
    except Exception as ex:
        raise ValueError(f"Invalid case_value for {key}: {ex}") from ex
    return message


def _normalize_case_value(
    ctx: AppContext,
    customer: str,
    source: str,
    case_value: dict | None,
    *,
    root: bool,
) -> dict | None:
    """Validate v25 listing-source/dimension combinations before mutation."""
    if case_value in (None, {}):
        if source == "WEBPAGE":
            raise ValueError(
                "WEBPAGE root filters require case_value={'webpage': {...}}."
            )
        return None
    if not isinstance(case_value, dict) or len(case_value) != 1:
        raise ValueError("case_value must contain exactly one listing dimension.")

    key = next(iter(case_value))
    if key not in _DIMENSION_KEYS:
        raise ValueError(
            f"Unsupported listing dimension {key!r}; use one of {sorted(_DIMENSION_KEYS)}."
        )

    if source == "WEBPAGE":
        if not root:
            raise ValueError("WEBPAGE listing filters are root nodes and cannot have a parent.")
        if key != "webpage":
            raise ValueError("WEBPAGE listing_source requires the webpage dimension.")
    elif source == "RETAIL":
        if key != "retail_filter_bundle":
            raise ValueError(
                "RETAIL listing_source is for Retail Product Tags and requires "
                "case_value.retail_filter_bundle.shared_set."
            )
    else:  # SHOPPING
        if key in {"webpage", "retail_filter_bundle"}:
            raise ValueError(
                "SHOPPING listing_source requires a product dimension, not "
                f"{key}."
            )

    normalized = dict(case_value)
    if key == "retail_filter_bundle":
        bundle = dict(normalized[key] or {})
        shared_set = str(bundle.get("shared_set", "")).strip()
        if not shared_set:
            raise ValueError("retail_filter_bundle.shared_set is required.")
        bundle["shared_set"] = _owned(
            ctx, customer, shared_set, "retail_filter_bundle.shared_set"
        )
        normalized[key] = bundle
    return normalized


def register(mcp, ctx: AppContext) -> None:
    @mcp.tool()
    def list_asset_group_signals(
        customer_id: str, asset_group_id: str | None = None
    ) -> dict:
        """List PMax audience/search/local/vertical-feed asset-group signals."""
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
        """Propose adding one PMax asset-group signal.

        ``signal_type`` may be AUDIENCE, SEARCH_THEME, LOCAL_SERVICES_ID, or
        VERTICAL_ADS_ITEM_GROUP_RULE_LIST. LOCAL_SERVICES_ID is Google-allowlisted.
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
                "AssetGroupSignalService",
                customer,
                [operation],
                validate_only=validate_only,
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
            ctx,
            customer,
            asset_group_signal_resource_name,
            "asset_group_signal_resource_name",
        )
        operation = ctx.client.raw.get_type("AssetGroupSignalOperation")
        operation.remove = resource

        def execute():
            return ctx.client.mutate(
                "AssetGroupSignalService",
                customer,
                [operation],
                validate_only=validate_only,
            )

        return ctx.safety.propose(
            tool_name="remove_asset_group_signal",
            customer_id=customer,
            description=f"Remove PMax asset-group signal {resource}",
            payload={
                "asset_group_signal_resource_name": resource,
                "validate_only": validate_only,
            },
            execute=execute,
        )

    @mcp.tool()
    def list_asset_group_listing_filters(
        customer_id: str, asset_group_id: str
    ) -> dict:
        """List all PMax listing-group filters for one asset group."""
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
        return {
            "asset_group_id": asset_group,
            "listing_group_filters": rows,
            "count": len(rows),
        }

    @mcp.tool()
    def replace_asset_group_listing_filter_tree(
        customer_id: str,
        asset_group_id: str,
        nodes: list[dict],
        listing_source: str = "SHOPPING",
        replace_existing: bool = True,
    ) -> dict:
        """Propose atomically replacing/creating PMax listing filters.

        For SHOPPING/RETAIL trees, nodes use unique negative ``temp_id`` values;
        exactly one root has no parent/case value and non-root nodes refine their
        parent. "Everything else" children are represented by an explicitly present
        empty dimension, for example ``{"product_brand": {}}``.

        For WEBPAGE source, every node is a root filter: omit ``parent_temp_id`` and
        provide ``case_value={"webpage": {"conditions": [...]}}``. Google permits
        several such roots and ORs them together.

        RETAIL source supports Retail Product Tags through
        ``case_value.retail_filter_bundle.shared_set``.
        """
        customer = ctx.client.assert_customer_allowed(customer_id)
        asset_group = _id(asset_group_id, "asset_group_id")
        if not nodes:
            raise ValueError("nodes must not be empty.")
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
            root = parent is None
            if root:
                roots += 1

            case_value = _normalize_case_value(
                ctx,
                customer,
                source,
                item.get("case_value"),
                root=root,
            )

            if source == "WEBPAGE":
                if parent is not None:
                    raise ValueError("WEBPAGE filters cannot have parent_temp_id.")
                if node_type == "SUBDIVISION":
                    raise ValueError("WEBPAGE root filters cannot be SUBDIVISION nodes.")
            else:
                if root and case_value is not None:
                    raise ValueError(
                        "The SHOPPING/RETAIL tree root cannot set case_value."
                    )
                if not root and case_value is None:
                    raise ValueError(
                        "Non-root SHOPPING/RETAIL nodes require case_value. For an "
                        "everything-else node use an explicitly present empty dimension, "
                        "for example {'product_brand': {}}."
                    )

            normalized.append(
                {
                    "temp_id": temp_id,
                    "type": node_type,
                    "parent_temp_id": parent,
                    "case_value": case_value,
                }
            )

        if source == "WEBPAGE":
            if roots != len(normalized):
                raise ValueError("Every WEBPAGE filter must be a root node.")
        elif roots != 1:
            raise ValueError("SHOPPING/RETAIL listing trees require exactly one root node.")

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
                        parent_map[str(resource)] = (
                            data.get("parent_listing_group_filter") or None
                        )
                for resource in sorted(
                    parent_map,
                    key=lambda value: _depth(value, parent_map),
                    reverse=True,
                ):
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
                node.type_ = getattr(
                    raw.enums.ListingGroupFilterTypeEnum, item["type"]
                )
                node.listing_source = getattr(
                    raw.enums.ListingGroupFilterListingSourceEnum, source
                )
                parent = item["parent_temp_id"]
                if parent is not None:
                    node.parent_listing_group_filter = (
                        f"customers/{customer}/assetGroupListingGroupFilters/"
                        f"{asset_group}~{parent}"
                    )
                if item["case_value"] is not None:
                    dimension = _parse_dimension(raw, item["case_value"])
                    raw.copy_from(node.case_value, dimension)
                operations.append(mutate)

            return ctx.client.mutate_atomic(customer, operations)

        return ctx.safety.propose(
            tool_name="replace_asset_group_listing_filter_tree",
            customer_id=customer,
            description=(
                f"{'Replace' if replace_existing else 'Create'} PMax {source} "
                f"listing filters for asset group {asset_group} with "
                f"{len(normalized)} node(s)"
            ),
            payload={
                "asset_group_id": asset_group,
                "listing_source": source,
                "replace_existing": bool(replace_existing),
                "nodes": normalized,
            },
            execute=execute,
        )
