"""Standard Shopping listing-group (product group) criteria.

Listing groups build a tree of AdGroupCriterion resources on a
SHOPPING_PRODUCT_ADS ad group: a root SUBDIVISION ("All products") with
children that either subdivide again or are leaf UNITS that carry a
bid modifier. The v25 contract lives on AdGroupCriterion.listing_group with
a ListingDimensionInfo case value; the criterion path encodes the tree
position (customers/{id}/adGroupCriteria/{adGroupId}~{criterionId}).
"""

from __future__ import annotations

from google.protobuf import field_mask_pb2

from ..context import AppContext

_LISTING_GROUP_TYPES = {"SUBDIVISION", "UNIT"}

# dimension type -> (enum for values, needs level) ; None means plain string
_DIMENSIONS = {
    "PRODUCT_BRAND": ("value", None),
    "PRODUCT_ITEM_ID": ("value", None),
    "PRODUCT_GROUPING": ("value", None),
    "PRODUCT_LABELS": ("value", None),
    "PRODUCT_TYPE": ("value_level", None),
    "PRODUCT_CATEGORY": ("category", None),
    "PRODUCT_CONDITION": ("enum", "ProductConditionEnum", "condition"),
    "PRODUCT_CHANNEL": ("enum", "ProductChannelEnum", "channel"),
    "PRODUCT_CHANNEL_EXCLUSIVITY": (
        "enum",
        "ProductChannelExclusivityEnum",
        "channel_exclusivity",
    ),
}

# dimension type -> ListingDimensionInfo field name
_DIMENSION_FIELDS = {
    "PRODUCT_BRAND": "product_brand",
    "PRODUCT_ITEM_ID": "product_item_id",
    "PRODUCT_GROUPING": "product_grouping",
    "PRODUCT_LABELS": "product_labels",
    "PRODUCT_TYPE": "product_type",
    "PRODUCT_CATEGORY": "product_category",
    "PRODUCT_CONDITION": "product_condition",
    "PRODUCT_CHANNEL": "product_channel",
    "PRODUCT_CHANNEL_EXCLUSIVITY": "product_channel_exclusivity",
}

_LEVELS = {"LEVEL1", "LEVEL2", "LEVEL3", "LEVEL4", "LEVEL5"}


def _enum_values(client, enum_name: str) -> set[str]:
    """Upper-case member names of an enum, for both the real v25 client and
    the test fakes (which are plain enum.Enum)."""
    return {name for name in dir(getattr(client.enums, enum_name)) if name.isupper()}


def _set_case_value(client, case_value, dimension: dict) -> None:
    dim_type = str(dimension.get("type", "")).strip().upper()
    if dim_type not in _DIMENSIONS:
        raise ValueError(
            f"dimension.type must be one of {sorted(_DIMENSIONS)}, got {dim_type!r}."
        )
    kind = _DIMENSIONS[dim_type][0]
    field = _DIMENSION_FIELDS[dim_type]
    if kind == "value":
        value = str(dimension.get("value", "")).strip()
        if not value:
            raise ValueError(f"dimension.value is required for {dim_type}.")
        getattr(case_value, field).value = value
    elif kind == "value_level":
        value = str(dimension.get("value", "")).strip()
        level = str(dimension.get("level", "")).strip().upper()
        if not value:
            raise ValueError(f"dimension.value is required for {dim_type}.")
        if level not in _LEVELS:
            raise ValueError("dimension.level must be LEVEL1..LEVEL5 for PRODUCT_TYPE.")
        target = getattr(case_value, field)
        target.value = value
        target.level = client.enums.ProductCategoryLevelEnum[level].value
    elif kind == "category":
        try:
            category_id = int(dimension["category_id"])
        except (KeyError, TypeError, ValueError):
            raise ValueError(
                "dimension.category_id (integer) is required for PRODUCT_CATEGORY."
            )
        level = str(dimension.get("level", "")).strip().upper()
        if level not in _LEVELS:
            raise ValueError(
                "dimension.level must be LEVEL1..LEVEL5 for PRODUCT_CATEGORY."
            )
        target = getattr(case_value, field)
        target.category_id = category_id
        target.level = client.enums.ProductCategoryLevelEnum[level].value
    else:  # enum-backed dimension
        value = str(dimension.get("value", "")).strip().upper()
        enum_name = _DIMENSIONS[dim_type][1]
        inner_field = _DIMENSIONS[dim_type][2]
        if value not in _enum_values(client, enum_name):
            raise ValueError(
                f"dimension.value must be one of "
                f"{sorted(_enum_values(client, enum_name))} for {dim_type}."
            )
        setattr(
            getattr(case_value, field),
            inner_field,
            getattr(client.enums, enum_name)[value].value,
        )


def register(mcp, ctx: AppContext) -> None:
    @mcp.tool()
    def add_shopping_listing_group(
        customer_id: str,
        ad_group_id: str,
        listing_group_type: str,
        dimension: dict | None = None,
        parent_criterion_id: str | None = None,
        bid_modifier: float | None = None,
    ) -> dict:
        """Propose adding a listing-group criterion to a Standard Shopping ad group.

        ``listing_group_type`` is ``SUBDIVISION`` (a folder that splits the
        tree) or ``UNIT`` (a leaf that can carry a ``bid_modifier``). The root
        node is a SUBDIVISION with no dimension ("All products"); children are
        created by passing the parent's ``criterion_id``.

        ``dimension`` selects the split, for example::

            {"type": "PRODUCT_BRAND", "value": "Nike"}
            {"type": "PRODUCT_TYPE", "level": "LEVEL1", "value": "Electrónica"}
            {"type": "PRODUCT_CATEGORY", "level": "LEVEL1", "category_id": 6469}
            {"type": "PRODUCT_CONDITION", "value": "NEW"}
            {"type": "PRODUCT_ITEM_ID", "value": "SKU-123"}

        Removing a SUBDIVISION with children requires removing the children
        first.
        """
        if listing_group_type not in _LISTING_GROUP_TYPES:
            raise ValueError(
                "listing_group_type must be SUBDIVISION or UNIT."
            )
        if listing_group_type == "UNIT" and dimension is None:
            raise ValueError("UNIT listing groups require a dimension.")
        if bid_modifier is not None and not (0.0 <= bid_modifier <= 10.0):
            raise ValueError("bid_modifier must be between 0 and 10.")

        client = ctx.client.raw
        customer_clean = customer_id.replace("-", "")
        operation = client.get_type("AdGroupCriterionOperation")
        criterion = operation.create
        criterion.ad_group = client.get_service("AdGroupService").ad_group_path(
            customer_clean, ad_group_id
        )
        criterion.status = client.enums.AdGroupCriterionStatusEnum.ENABLED
        criterion.listing_group.type_ = client.enums.ListingGroupTypeEnum[
            listing_group_type
        ].value
        if parent_criterion_id is not None:
            criterion.listing_group.parent_ad_group_criterion = (
                client.get_service("AdGroupCriterionService").ad_group_criterion_path(
                    customer_clean, ad_group_id, str(parent_criterion_id)
                )
            )
        if dimension is not None:
            _set_case_value(client, criterion.listing_group.case_value, dimension)
        if bid_modifier is not None:
            criterion.bid_modifier = bid_modifier

        description = (
            f"Add {'root ' if dimension is None else ''}{listing_group_type} "
            f"listing group on ad group {ad_group_id}"
            + (f" [{dimension.get('type')} = {dimension.get('value', dimension.get('category_id'))}]" if dimension else " (all products)")
            + (f" under {parent_criterion_id}" if parent_criterion_id else "")
            + (f" (bid modifier x{bid_modifier})" if bid_modifier is not None else "")
        )

        def execute():
            return ctx.client.mutate("AdGroupCriterionService", customer_id, [operation])

        return ctx.safety.propose(
            tool_name="add_shopping_listing_group",
            customer_id=customer_id,
            description=description,
            payload={
                "ad_group_id": ad_group_id,
                "listing_group_type": listing_group_type,
                "dimension": dimension,
                "parent_criterion_id": parent_criterion_id,
                "bid_modifier": bid_modifier,
            },
            execute=execute,
        )

    @mcp.tool()
    def update_shopping_listing_group(
        customer_id: str,
        ad_group_id: str,
        criterion_id: str,
        bid_modifier: float | None = None,
        status: str | None = None,
    ) -> dict:
        """Propose updating a listing-group criterion (bid modifier or status)."""
        if bid_modifier is None and status is None:
            raise ValueError("Provide at least one of bid_modifier or status.")
        if bid_modifier is not None and not (0.0 <= bid_modifier <= 10.0):
            raise ValueError("bid_modifier must be between 0 and 10.")
        if status is not None and status not in {"ENABLED", "PAUSED", "REMOVED"}:
            raise ValueError("status must be ENABLED, PAUSED, or REMOVED.")

        client = ctx.client.raw
        operation = client.get_type("AdGroupCriterionOperation")
        criterion = operation.update
        criterion.resource_name = client.get_service(
            "AdGroupCriterionService"
        ).ad_group_criterion_path(
            customer_id.replace("-", ""), ad_group_id, str(criterion_id)
        )
        paths = []
        if bid_modifier is not None:
            criterion.bid_modifier = bid_modifier
            paths.append("bid_modifier")
        if status is not None:
            criterion.status = client.enums.AdGroupCriterionStatusEnum[status].value
            paths.append("status")
        operation.update_mask.CopyFrom(field_mask_pb2.FieldMask(paths=paths))

        description = (
            f"Update listing group {criterion_id} on ad group {ad_group_id}"
        )

        def execute():
            return ctx.client.mutate("AdGroupCriterionService", customer_id, [operation])

        return ctx.safety.propose(
            tool_name="update_shopping_listing_group",
            customer_id=customer_id,
            description=description,
            payload={
                "ad_group_id": ad_group_id,
                "criterion_id": criterion_id,
                "bid_modifier": bid_modifier,
                "status": status,
            },
            execute=execute,
        )

    @mcp.tool()
    def remove_shopping_listing_group(
        customer_id: str,
        ad_group_id: str,
        criterion_id: str,
    ) -> dict:
        """Propose removing one listing-group criterion.

        SUBDIVISIONs with live children must be removed bottom-up.
        """
        client = ctx.client.raw
        operation = client.get_type("AdGroupCriterionOperation")
        operation.remove = client.get_service(
            "AdGroupCriterionService"
        ).ad_group_criterion_path(
            customer_id.replace("-", ""), ad_group_id, str(criterion_id)
        )

        description = f"Remove listing group {criterion_id} from ad group {ad_group_id}"

        def execute():
            return ctx.client.mutate("AdGroupCriterionService", customer_id, [operation])

        return ctx.safety.propose(
            tool_name="remove_shopping_listing_group",
            customer_id=customer_id,
            description=description,
            payload={"ad_group_id": ad_group_id, "criterion_id": criterion_id},
            execute=execute,
        )

    @mcp.tool()
    def list_shopping_listing_groups(customer_id: str, ad_group_id: str) -> dict:
        """List the listing-group tree on a Standard Shopping ad group."""
        query = f"""
            SELECT ad_group_criterion.criterion_id,
                   ad_group_criterion.status,
                   ad_group_criterion.bid_modifier,
                   ad_group_criterion.listing_group.type,
                   ad_group_criterion.listing_group.parent_ad_group_criterion,
                   ad_group_criterion.listing_group.case_value,
                   ad_group_criterion.listing_group.path
            FROM ad_group_criterion
            WHERE ad_group.id = {int(ad_group_id)}
              AND ad_group_criterion.type = LISTING_GROUP
        """
        rows = ctx.client.search(customer_id, query)
        return {"ad_group_id": ad_group_id, "listing_groups": rows, "count": len(rows)}
