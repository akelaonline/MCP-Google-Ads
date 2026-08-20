"""Modern Audience, CustomAudience and CustomInterest management for API v25."""

from __future__ import annotations

from google.protobuf import field_mask_pb2

from ..context import AppContext

_CUSTOM_AUDIENCE_MEMBER_TYPES = {"KEYWORD", "URL", "PLACE_CATEGORY", "APP"}
_CUSTOM_INTEREST_MEMBER_TYPES = {"KEYWORD", "URL"}
_CUSTOM_INTEREST_TYPES = {"CUSTOM_AFFINITY", "CUSTOM_INTENT"}
_AUDIENCE_SCOPES = {"CUSTOMER", "ASSET_GROUP"}


def _owned(ctx: AppContext, customer: str, resource: str, field_name: str) -> str:
    return ctx.client.assert_resource_name_customer(customer, resource, field_name=field_name)


def _build_custom_audience_members(raw, members: list[dict]) -> tuple[list, list[dict]]:
    if not members:
        raise ValueError("members must contain at least one member.")
    built = []
    safe = []
    for item in members:
        member_type = str(item.get("type", "")).strip().upper()
        if member_type not in _CUSTOM_AUDIENCE_MEMBER_TYPES:
            raise ValueError(
                f"CustomAudience member type must be one of {sorted(_CUSTOM_AUDIENCE_MEMBER_TYPES)}."
            )
        value = item.get("value")
        if value is None or str(value).strip() == "":
            raise ValueError("Every custom audience member requires a non-empty value.")
        member = raw.get_type("CustomAudienceMember")
        member.member_type = getattr(raw.enums.CustomAudienceMemberTypeEnum, member_type)
        if member_type == "PLACE_CATEGORY":
            text_value = str(value).strip()
            if not text_value.isdigit() or int(text_value) <= 0:
                raise ValueError("PLACE_CATEGORY member value must be a positive numeric ID.")
            member.place_category = int(text_value)
            normalized: str | int = int(text_value)
        elif member_type == "KEYWORD":
            normalized = str(value).strip()
            if len(normalized) > 80 or len(normalized.split()) > 10:
                raise ValueError(
                    "Custom audience KEYWORD must be at most 10 words and 80 characters."
                )
            member.keyword = normalized
        elif member_type == "URL":
            normalized = str(value).strip()
            if len(normalized) > 2048 or not normalized.startswith(("http://", "https://")):
                raise ValueError(
                    "Custom audience URL must be an http(s) URL up to 2048 characters."
                )
            member.url = normalized
        else:
            normalized = str(value).strip()
            member.app = normalized
        built.append(member)
        safe.append({"type": member_type, "value": normalized})
    return built, safe


def _build_custom_interest_members(raw, members: list[dict]) -> tuple[list, list[dict]]:
    if not members:
        raise ValueError("members must contain at least one member.")
    built = []
    safe = []
    for item in members:
        member_type = str(item.get("type", "")).strip().upper()
        if member_type not in _CUSTOM_INTEREST_MEMBER_TYPES:
            raise ValueError(
                f"CustomInterest member type must be one of {sorted(_CUSTOM_INTEREST_MEMBER_TYPES)}."
            )
        parameter = str(item.get("value", "")).strip()
        if not parameter:
            raise ValueError("Every custom interest member requires a non-empty value.")
        if member_type == "URL" and not parameter.startswith(("http://", "https://")):
            raise ValueError("CustomInterest URL members must start with http:// or https://.")
        member = raw.get_type("CustomInterestMember")
        member.member_type = getattr(raw.enums.CustomInterestMemberTypeEnum, member_type)
        member.parameter = parameter
        built.append(member)
        safe.append({"type": member_type, "value": parameter})
    return built, safe


def _append_audience_segment(raw, dimension, kind: str, resource: str) -> None:
    segment = raw.get_type("AudienceSegment")
    if kind == "USER_LIST":
        segment.user_list.user_list = resource
    elif kind == "CUSTOM_AUDIENCE":
        segment.custom_audience.custom_audience = resource
    elif kind == "USER_INTEREST":
        segment.user_interest.user_interest_category = resource
    elif kind == "LIFE_EVENT":
        segment.life_event.life_event = resource
    elif kind == "DETAILED_DEMOGRAPHIC":
        segment.detailed_demographic.detailed_demographic = resource
    else:
        raise ValueError(f"Unsupported Audience segment kind: {kind}")
    dimension.audience_segments.segments.append(segment)


def register(mcp, ctx: AppContext) -> None:
    @mcp.tool()
    def list_custom_audiences(customer_id: str) -> dict:
        """List modern CustomAudience resources and their members."""
        rows = ctx.client.search(
            customer_id,
            """
            SELECT custom_audience.resource_name, custom_audience.id,
                   custom_audience.name, custom_audience.description,
                   custom_audience.type, custom_audience.status,
                   custom_audience.members
            FROM custom_audience
            ORDER BY custom_audience.name
            """,
        )
        return {"custom_audiences": rows, "count": len(rows)}

    @mcp.tool()
    def create_custom_audience(
        customer_id: str,
        name: str,
        members: list[dict],
        description: str | None = None,
        audience_type: str = "AUTO",
        validate_only: bool = False,
    ) -> dict:
        """Propose creating a CustomAudience from keywords, URLs, apps or place categories."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        clean_name = str(name).strip()
        if not clean_name:
            raise ValueError("name must not be empty.")
        clean_type = audience_type.strip().upper()
        if clean_type not in {"AUTO", "SEARCH"}:
            raise ValueError(
                "New CustomAudience type must be AUTO or SEARCH; "
                "INTEREST/PURCHASE_INTENT are legacy-only."
            )
        raw = ctx.client.raw
        built_members, safe_members = _build_custom_audience_members(raw, members)
        operation = raw.get_type("CustomAudienceOperation")
        audience = operation.create
        audience.name = clean_name
        audience.type_ = getattr(raw.enums.CustomAudienceTypeEnum, clean_type)
        if description:
            audience.description = str(description).strip()
        audience.members.extend(built_members)

        def execute():
            return ctx.client.mutate(
                "CustomAudienceService", customer, [operation], validate_only=validate_only
            )

        return ctx.safety.propose(
            tool_name="create_custom_audience",
            customer_id=customer,
            description=f"Create CustomAudience '{clean_name}' with {len(built_members)} member(s)",
            payload={
                "name": clean_name,
                "audience_type": clean_type,
                "description": description,
                "members": safe_members,
                "validate_only": validate_only,
            },
            execute=execute,
        )

    @mcp.tool()
    def update_custom_audience(
        customer_id: str,
        custom_audience_resource_name: str,
        name: str | None = None,
        description: str | None = None,
        members: list[dict] | None = None,
        audience_type: str | None = None,
        validate_only: bool = False,
    ) -> dict:
        """Propose updating a CustomAudience; supplied members replace the full list."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        resource = _owned(
            ctx, customer, custom_audience_resource_name, "custom_audience_resource_name"
        )
        raw = ctx.client.raw
        operation = raw.get_type("CustomAudienceOperation")
        audience = operation.update
        audience.resource_name = resource
        paths: list[str] = []
        safe_members = None
        if name is not None:
            clean_name = str(name).strip()
            if not clean_name:
                raise ValueError("name must not be empty when supplied.")
            audience.name = clean_name
            paths.append("name")
        if description is not None:
            audience.description = str(description)
            paths.append("description")
        if members is not None:
            built_members, safe_members = _build_custom_audience_members(raw, members)
            audience.members.extend(built_members)
            paths.append("members")
        if audience_type is not None:
            clean_type = audience_type.strip().upper()
            if clean_type not in {"AUTO", "SEARCH"}:
                raise ValueError("audience_type must be AUTO or SEARCH.")
            audience.type_ = getattr(raw.enums.CustomAudienceTypeEnum, clean_type)
            paths.append("type")
        if not paths:
            raise ValueError("Provide at least one field to update.")
        operation.update_mask.CopyFrom(field_mask_pb2.FieldMask(paths=paths))

        def execute():
            return ctx.client.mutate(
                "CustomAudienceService", customer, [operation], validate_only=validate_only
            )

        return ctx.safety.propose(
            tool_name="update_custom_audience",
            customer_id=customer,
            description=f"Update CustomAudience {resource}: {', '.join(paths)}",
            payload={
                "custom_audience_resource_name": resource,
                "fields": paths,
                "members": safe_members,
                "validate_only": validate_only,
            },
            execute=execute,
        )

    @mcp.tool()
    def list_custom_interests(customer_id: str) -> dict:
        """List CustomInterest resources and their members."""
        rows = ctx.client.search(
            customer_id,
            """
            SELECT custom_interest.resource_name, custom_interest.id,
                   custom_interest.name, custom_interest.description,
                   custom_interest.type, custom_interest.status,
                   custom_interest.members
            FROM custom_interest
            ORDER BY custom_interest.name
            """,
        )
        return {"custom_interests": rows, "count": len(rows)}

    @mcp.tool()
    def create_custom_interest(
        customer_id: str,
        name: str,
        members: list[dict],
        interest_type: str = "CUSTOM_AFFINITY",
        description: str | None = None,
        validate_only: bool = False,
    ) -> dict:
        """Propose creating a CustomInterest from keyword/URL members."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        clean_name = str(name).strip()
        if not clean_name:
            raise ValueError("name must not be empty.")
        clean_type = interest_type.strip().upper()
        if clean_type not in _CUSTOM_INTEREST_TYPES:
            raise ValueError(f"interest_type must be one of {sorted(_CUSTOM_INTEREST_TYPES)}.")
        raw = ctx.client.raw
        built_members, safe_members = _build_custom_interest_members(raw, members)
        operation = raw.get_type("CustomInterestOperation")
        interest = operation.create
        interest.name = clean_name
        interest.type_ = getattr(raw.enums.CustomInterestTypeEnum, clean_type)
        if description:
            interest.description = str(description).strip()
        interest.members.extend(built_members)

        def execute():
            return ctx.client.mutate(
                "CustomInterestService", customer, [operation], validate_only=validate_only
            )

        return ctx.safety.propose(
            tool_name="create_custom_interest",
            customer_id=customer,
            description=f"Create {clean_type} CustomInterest '{clean_name}'",
            payload={
                "name": clean_name,
                "interest_type": clean_type,
                "description": description,
                "members": safe_members,
                "validate_only": validate_only,
            },
            execute=execute,
        )

    @mcp.tool()
    def update_custom_interest(
        customer_id: str,
        custom_interest_resource_name: str,
        name: str | None = None,
        description: str | None = None,
        members: list[dict] | None = None,
        interest_type: str | None = None,
        status: str | None = None,
        validate_only: bool = False,
    ) -> dict:
        """Propose updating a CustomInterest; supplied members replace the full list."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        resource = _owned(
            ctx, customer, custom_interest_resource_name, "custom_interest_resource_name"
        )
        raw = ctx.client.raw
        operation = raw.get_type("CustomInterestOperation")
        interest = operation.update
        interest.resource_name = resource
        paths: list[str] = []
        safe_members = None
        clean_status = None
        if name is not None:
            clean_name = str(name).strip()
            if not clean_name:
                raise ValueError("name must not be empty when supplied.")
            interest.name = clean_name
            paths.append("name")
        if description is not None:
            interest.description = str(description)
            paths.append("description")
        if members is not None:
            built_members, safe_members = _build_custom_interest_members(raw, members)
            interest.members.extend(built_members)
            paths.append("members")
        if interest_type is not None:
            clean_type = interest_type.strip().upper()
            if clean_type not in _CUSTOM_INTEREST_TYPES:
                raise ValueError(
                    f"interest_type must be one of {sorted(_CUSTOM_INTEREST_TYPES)}."
                )
            interest.type_ = getattr(raw.enums.CustomInterestTypeEnum, clean_type)
            paths.append("type")
        if status is not None:
            clean_status = status.strip().upper()
            if clean_status not in {"ENABLED", "REMOVED"}:
                raise ValueError("status must be ENABLED or REMOVED.")
            interest.status = getattr(raw.enums.CustomInterestStatusEnum, clean_status)
            paths.append("status")
        if not paths:
            raise ValueError("Provide at least one field to update.")
        operation.update_mask.CopyFrom(field_mask_pb2.FieldMask(paths=paths))

        def execute():
            return ctx.client.mutate(
                "CustomInterestService", customer, [operation], validate_only=validate_only
            )

        return ctx.safety.propose(
            tool_name="update_custom_interest",
            customer_id=customer,
            description=f"Update CustomInterest {resource}: {', '.join(paths)}",
            payload={
                "custom_interest_resource_name": resource,
                "fields": paths,
                "members": safe_members,
                "status": clean_status,
                "validate_only": validate_only,
            },
            execute=execute,
        )

    @mcp.tool()
    def list_audiences(customer_id: str) -> dict:
        """List reusable Audience resources used by Performance Max and Demand Gen."""
        rows = ctx.client.search(
            customer_id,
            """
            SELECT audience.resource_name, audience.id, audience.name,
                   audience.description, audience.scope, audience.status,
                   audience.dimensions, audience.exclusion_dimension
            FROM audience
            ORDER BY audience.id
            """,
        )
        return {"audiences": rows, "count": len(rows)}

    @mcp.tool()
    def create_audience(
        customer_id: str,
        name: str | None = None,
        user_list_resource_names: list[str] | None = None,
        custom_audience_resource_names: list[str] | None = None,
        user_interest_resource_names: list[str] | None = None,
        life_event_resource_names: list[str] | None = None,
        detailed_demographic_resource_names: list[str] | None = None,
        excluded_user_list_resource_names: list[str] | None = None,
        description: str | None = None,
        scope: str = "CUSTOMER",
        validate_only: bool = False,
    ) -> dict:
        """Propose creating an Audience from supported segment resources.

        CUSTOMER scope requires a unique name. ASSET_GROUP scope must not have a
        name. Positive segments are grouped into one OR dimension. Google only
        permits user-list segments in the exclusion dimension.
        """
        customer = ctx.client.assert_customer_allowed(customer_id)
        clean_scope = scope.strip().upper()
        if clean_scope not in _AUDIENCE_SCOPES:
            raise ValueError(f"scope must be one of {sorted(_AUDIENCE_SCOPES)}.")
        clean_name = str(name).strip() if name is not None else ""
        if clean_scope == "CUSTOMER":
            if not 1 <= len(clean_name) <= 255:
                raise ValueError("CUSTOMER-scoped Audience name must be 1-255 characters.")
        elif clean_name:
            raise ValueError("ASSET_GROUP-scoped audiences cannot set name.")

        raw = ctx.client.raw
        operation = raw.get_type("AudienceOperation")
        audience = operation.create
        if clean_scope == "CUSTOMER":
            audience.name = clean_name
        audience.scope = getattr(raw.enums.AudienceScopeEnum, clean_scope)
        if description:
            audience.description = str(description).strip()

        dimension = raw.get_type("AudienceDimension")
        safe_segments = []
        for kind, values in (
            ("USER_LIST", user_list_resource_names or []),
            ("CUSTOM_AUDIENCE", custom_audience_resource_names or []),
            ("USER_INTEREST", user_interest_resource_names or []),
            ("LIFE_EVENT", life_event_resource_names or []),
            ("DETAILED_DEMOGRAPHIC", detailed_demographic_resource_names or []),
        ):
            for value in values:
                resource = _owned(ctx, customer, value, f"{kind.lower()}_resource_name")
                _append_audience_segment(raw, dimension, kind, resource)
                safe_segments.append({"type": kind, "resource_name": resource})
        if safe_segments:
            audience.dimensions.append(dimension)

        exclusions = []
        for value in excluded_user_list_resource_names or []:
            resource = _owned(
                ctx, customer, value, "excluded_user_list_resource_name"
            )
            exclusion = raw.get_type("ExclusionSegment")
            exclusion.user_list.user_list = resource
            audience.exclusion_dimension.exclusions.append(exclusion)
            exclusions.append(resource)
        if not safe_segments and not exclusions:
            raise ValueError(
                "Audience requires at least one positive segment or excluded user list."
            )

        def execute():
            return ctx.client.mutate(
                "AudienceService", customer, [operation], validate_only=validate_only
            )

        return ctx.safety.propose(
            tool_name="create_audience",
            customer_id=customer,
            description=(
                f"Create {clean_scope} Audience "
                + (f"'{clean_name}' " if clean_name else "")
                + f"with {len(safe_segments)} segment(s)"
            ),
            payload={
                "name": clean_name or None,
                "scope": clean_scope,
                "segments": safe_segments,
                "excluded_user_lists": exclusions,
                "validate_only": validate_only,
            },
            execute=execute,
        )

    @mcp.tool()
    def update_audience_metadata(
        customer_id: str,
        audience_resource_name: str,
        name: str | None = None,
        description: str | None = None,
        promote_scope_to_customer: bool = False,
        validate_only: bool = False,
    ) -> dict:
        """Propose updating Audience metadata or promoting ASSET_GROUP scope to CUSTOMER."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        resource = _owned(ctx, customer, audience_resource_name, "audience_resource_name")

        current_scope = None
        if name is not None or promote_scope_to_customer:
            rows = ctx.client.search(
                customer,
                f"""
                SELECT audience.scope
                FROM audience
                WHERE audience.resource_name = '{resource}'
                LIMIT 1
                """,
            )
            if not rows:
                raise ValueError("Audience was not found or is not visible to this customer.")
            raw_scope = rows[0].get("audience", {}).get("scope")
            current_scope = str(getattr(raw_scope, "name", raw_scope)).upper().rsplit(".", 1)[-1]
            if current_scope not in _AUDIENCE_SCOPES:
                raise ValueError("Could not determine the current Audience scope safely.")
            if name is not None and current_scope == "ASSET_GROUP" and not promote_scope_to_customer:
                raise ValueError(
                    "ASSET_GROUP-scoped audiences cannot set or update name. "
                    "Set promote_scope_to_customer=true and provide the required customer-level name."
                )
            if promote_scope_to_customer and current_scope == "CUSTOMER":
                raise ValueError("Audience is already CUSTOMER-scoped; no scope promotion is needed.")
            if promote_scope_to_customer and current_scope == "ASSET_GROUP" and name is None:
                raise ValueError(
                    "Promoting an ASSET_GROUP audience to CUSTOMER requires a name."
                )

        raw = ctx.client.raw
        operation = raw.get_type("AudienceOperation")
        audience = operation.update
        audience.resource_name = resource
        paths: list[str] = []
        if name is not None:
            clean_name = str(name).strip()
            if not 1 <= len(clean_name) <= 255:
                raise ValueError("name must be between 1 and 255 characters.")
            audience.name = clean_name
            paths.append("name")
        if description is not None:
            audience.description = str(description)
            paths.append("description")
        if promote_scope_to_customer:
            audience.scope = raw.enums.AudienceScopeEnum.CUSTOMER
            paths.append("scope")
        if not paths:
            raise ValueError(
                "Provide name, description, or promote_scope_to_customer=true."
            )
        operation.update_mask.CopyFrom(field_mask_pb2.FieldMask(paths=paths))

        def execute():
            return ctx.client.mutate(
                "AudienceService", customer, [operation], validate_only=validate_only
            )

        return ctx.safety.propose(
            tool_name="update_audience_metadata",
            customer_id=customer,
            description=f"Update Audience {resource}: {', '.join(paths)}",
            payload={
                "audience_resource_name": resource,
                "fields": paths,
                "current_scope": current_scope,
                "validate_only": validate_only,
            },
            execute=execute,
        )
