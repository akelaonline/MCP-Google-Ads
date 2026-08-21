"""Geo, language, schedule, device, and placement targeting tools."""

from __future__ import annotations

from google.protobuf import field_mask_pb2

from ..context import AppContext


def register(mcp, ctx: AppContext) -> None:
    @mcp.tool()
    def add_location_targeting(
        customer_id: str,
        campaign_id: str,
        locations: list[str],
        negative: bool = False,
        country_code: str | None = None,
        locale: str = "en",
    ) -> dict:
        """Propose adding location targeting to a campaign.

        Numeric entries are treated as GeoTargetConstant criterion IDs. Text
        names are resolved live with ``SuggestGeoTargetConstants`` instead of
        relying on stale hard-coded IDs. If a name is ambiguous, pass a numeric
        criterion ID (or narrow it with ``country_code``).
        """
        if not locations:
            raise ValueError("Provide at least one location.")
        if country_code is not None and len(country_code) != 2:
            raise ValueError("country_code must be a two-letter country code.")

        client = ctx.client.raw
        customer_id_clean = customer_id.replace("-", "")
        campaign_resource_name = client.get_service("CampaignService").campaign_path(
            customer_id_clean, campaign_id
        )
        resolved = _resolve_location_resource_names(
            client,
            locations,
            country_code=country_code,
            locale=locale,
        )

        operations = []
        for original, resource_name in resolved:
            operation = client.get_type("CampaignCriterionOperation")
            criterion = operation.create
            criterion.campaign = campaign_resource_name
            criterion.negative = negative
            criterion.location.geo_target_constant = resource_name
            operations.append(operation)

        verb = "Exclude" if negative else "Target"
        description = (
            f"{verb} location(s) {[resource for _, resource in resolved]} "
            f"on campaign {campaign_id}"
        )

        def execute():
            return ctx.client.mutate(
                "CampaignCriterionService", customer_id, operations
            )

        return ctx.safety.propose(
            tool_name="add_location_targeting",
            customer_id=customer_id,
            description=description,
            payload={
                "campaign_id": campaign_id,
                "locations": locations,
                "resolved": [
                    {"input": original, "resource_name": resource}
                    for original, resource in resolved
                ],
                "negative": negative,
                "country_code": country_code,
                "locale": locale,
            },
            execute=execute,
        )

    @mcp.tool()
    def set_language_targeting(
        customer_id: str, campaign_id: str, language_codes: list[str]
    ) -> dict:
        """Replace all language criteria on a campaign atomically."""
        if not language_codes:
            raise ValueError("Provide at least one language constant ID.")
        normalized_codes = list(dict.fromkeys(str(code).strip() for code in language_codes))
        if any(not code.isdigit() for code in normalized_codes):
            raise ValueError("language_codes must contain numeric language constant IDs.")

        client = ctx.client.raw
        customer_id_clean = customer_id.replace("-", "")
        campaign_resource_name = client.get_service("CampaignService").campaign_path(
            customer_id_clean, campaign_id
        )

        existing_query = f"""
            SELECT campaign_criterion.criterion_id,
                   campaign_criterion.language.language_constant
            FROM campaign_criterion
            WHERE campaign.id = {int(campaign_id)}
              AND campaign_criterion.type = LANGUAGE
        """
        existing = ctx.client.search(customer_id, existing_query)

        operations = []
        criterion_service = client.get_service("CampaignCriterionService")
        for row in existing:
            criterion_id = row.get("campaign_criterion", {}).get("criterion_id")
            if criterion_id is None:
                continue
            operation = client.get_type("CampaignCriterionOperation")
            operation.remove = criterion_service.campaign_criterion_path(
                customer_id_clean, campaign_id, str(criterion_id)
            )
            operations.append(operation)

        for code in normalized_codes:
            operation = client.get_type("CampaignCriterionOperation")
            criterion = operation.create
            criterion.campaign = campaign_resource_name
            criterion.language.language_constant = f"languageConstants/{code}"
            operations.append(operation)

        description = (
            f"Replace campaign {campaign_id} language targeting with {normalized_codes}"
        )

        def execute():
            return ctx.client.mutate(
                "CampaignCriterionService", customer_id, operations
            )

        return ctx.safety.propose(
            tool_name="set_language_targeting",
            customer_id=customer_id,
            description=description,
            payload={
                "campaign_id": campaign_id,
                "language_codes": normalized_codes,
                "existing_language_count": len(existing),
            },
            execute=execute,
        )

    @mcp.tool()
    def add_ad_schedule(
        customer_id: str,
        campaign_id: str,
        day_of_week: str,
        start_hour: int,
        end_hour: int,
        bid_modifier: float | None = None,
    ) -> dict:
        """Propose adding an ad-schedule/daypart criterion."""
        if not (0 <= start_hour <= 23):
            raise ValueError("start_hour must be between 0 and 23.")
        if not (1 <= end_hour <= 24):
            raise ValueError("end_hour must be between 1 and 24.")
        if start_hour >= end_hour:
            raise ValueError("start_hour must be before end_hour.")
        if bid_modifier is not None and not (0.1 <= bid_modifier <= 10.0):
            raise ValueError("bid_modifier must be between 0.1 and 10.0.")
        if day_of_week not in {
            "MONDAY", "TUESDAY", "WEDNESDAY", "THURSDAY",
            "FRIDAY", "SATURDAY", "SUNDAY",
        }:
            raise ValueError("day_of_week must be a weekday enum name.")

        client = ctx.client.raw
        operation = client.get_type("CampaignCriterionOperation")
        criterion = operation.create
        criterion.campaign = client.get_service("CampaignService").campaign_path(
            customer_id.replace("-", ""), campaign_id
        )
        criterion.ad_schedule.day_of_week = client.enums.DayOfWeekEnum[
            day_of_week
        ].value
        criterion.ad_schedule.start_hour = start_hour
        criterion.ad_schedule.start_minute = client.enums.MinuteOfHourEnum.ZERO.value
        criterion.ad_schedule.end_hour = end_hour
        criterion.ad_schedule.end_minute = client.enums.MinuteOfHourEnum.ZERO.value
        if bid_modifier is not None:
            criterion.bid_modifier = bid_modifier

        description = (
            f"Add ad schedule {day_of_week} {start_hour}:00-{end_hour}:00 to campaign "
            f"{campaign_id}"
            + (f" (bid modifier x{bid_modifier})" if bid_modifier else "")
        )

        def execute():
            return ctx.client.mutate(
                "CampaignCriterionService", customer_id, [operation]
            )

        return ctx.safety.propose(
            tool_name="add_ad_schedule",
            customer_id=customer_id,
            description=description,
            payload={
                "campaign_id": campaign_id,
                "day_of_week": day_of_week,
                "start_hour": start_hour,
                "end_hour": end_hour,
                "bid_modifier": bid_modifier,
            },
            execute=execute,
        )

    @mcp.tool()
    def update_ad_schedule(
        customer_id: str,
        campaign_id: str,
        criterion_id: str,
        start_hour: int | None = None,
        end_hour: int | None = None,
        bid_modifier: float | None = None,
    ) -> dict:
        """Propose updating an existing ad-schedule/daypart criterion.

        ``criterion_id`` comes from ``list_campaign_criteria``. Only the fields
        provided are changed; pass ``bid_modifier=None`` to leave the existing
        modifier untouched.
        """
        if start_hour is None and end_hour is None and bid_modifier is None:
            raise ValueError(
                "Provide at least one of start_hour, end_hour, or bid_modifier."
            )
        if start_hour is not None and not (0 <= start_hour <= 23):
            raise ValueError("start_hour must be between 0 and 23.")
        if end_hour is not None and not (1 <= end_hour <= 24):
            raise ValueError("end_hour must be between 1 and 24.")
        if start_hour is not None and end_hour is not None and start_hour >= end_hour:
            raise ValueError("start_hour must be before end_hour.")
        if bid_modifier is not None and not (0.1 <= bid_modifier <= 10.0):
            raise ValueError("bid_modifier must be between 0.1 and 10.0.")

        client = ctx.client.raw
        criterion_service = client.get_service("CampaignCriterionService")
        operation = client.get_type("CampaignCriterionOperation")
        criterion = operation.update
        criterion.resource_name = criterion_service.campaign_criterion_path(
            customer_id.replace("-", ""), campaign_id, str(criterion_id)
        )
        if start_hour is not None:
            criterion.ad_schedule.start_hour = start_hour
            criterion.ad_schedule.start_minute = client.enums.MinuteOfHourEnum.ZERO.value
        if end_hour is not None:
            criterion.ad_schedule.end_hour = end_hour
            criterion.ad_schedule.end_minute = client.enums.MinuteOfHourEnum.ZERO.value
        if bid_modifier is not None:
            criterion.bid_modifier = bid_modifier

        paths = []
        if start_hour is not None:
            paths += ["ad_schedule.start_hour", "ad_schedule.start_minute"]
        if end_hour is not None:
            paths += ["ad_schedule.end_hour", "ad_schedule.end_minute"]
        if bid_modifier is not None:
            paths.append("bid_modifier")
        operation.update_mask.CopyFrom(field_mask_pb2.FieldMask(paths=paths))

        changed = []
        if start_hour is not None:
            changed.append(f"start={start_hour}:00")
        if end_hour is not None:
            changed.append(f"end={end_hour}:00")
        if bid_modifier is not None:
            changed.append(f"bid modifier x{bid_modifier}")
        description = (
            f"Update ad schedule criterion {criterion_id} on campaign {campaign_id}: "
            + ", ".join(changed)
        )

        def execute():
            return ctx.client.mutate(
                "CampaignCriterionService", customer_id, [operation]
            )

        return ctx.safety.propose(
            tool_name="update_ad_schedule",
            customer_id=customer_id,
            description=description,
            payload={
                "campaign_id": campaign_id,
                "criterion_id": criterion_id,
                "start_hour": start_hour,
                "end_hour": end_hour,
                "bid_modifier": bid_modifier,
            },
            execute=execute,
        )

    @mcp.tool()
    def remove_ad_schedule(
        customer_id: str,
        campaign_id: str,
        criterion_id: str,
    ) -> dict:
        """Propose removing one ad-schedule/daypart criterion."""
        client = ctx.client.raw
        criterion_service = client.get_service("CampaignCriterionService")
        operation = client.get_type("CampaignCriterionOperation")
        operation.remove = criterion_service.campaign_criterion_path(
            customer_id.replace("-", ""), campaign_id, str(criterion_id)
        )

        description = (
            f"Remove ad schedule criterion {criterion_id} from campaign {campaign_id}"
        )

        def execute():
            return ctx.client.mutate(
                "CampaignCriterionService", customer_id, [operation]
            )

        return ctx.safety.propose(
            tool_name="remove_ad_schedule",
            customer_id=customer_id,
            description=description,
            payload={"campaign_id": campaign_id, "criterion_id": criterion_id},
            execute=execute,
        )

    @mcp.tool()
    def set_device_bid_modifier(
        customer_id: str, campaign_id: str, device: str, bid_modifier: float
    ) -> dict:
        """Set a campaign-level device bid modifier idempotently.

        Existing device criteria are updated rather than recreated. Google
        allows 0 to opt out of a device, otherwise the valid range is 0.1-10.
        """
        if device not in {"MOBILE", "DESKTOP", "TABLET"}:
            raise ValueError("device must be MOBILE, DESKTOP, or TABLET.")
        if bid_modifier != 0 and not (0.1 <= bid_modifier <= 10.0):
            raise ValueError("bid_modifier must be 0 or between 0.1 and 10.0.")

        client = ctx.client.raw
        customer_id_clean = customer_id.replace("-", "")
        existing_query = f"""
            SELECT campaign_criterion.criterion_id,
                   campaign_criterion.device.type,
                   campaign_criterion.bid_modifier
            FROM campaign_criterion
            WHERE campaign.id = {int(campaign_id)}
              AND campaign_criterion.type = DEVICE
              AND campaign_criterion.device.type = {device}
            LIMIT 1
        """
        existing = ctx.client.search(customer_id, existing_query)
        operation = client.get_type("CampaignCriterionOperation")

        if existing:
            criterion_id = existing[0]["campaign_criterion"]["criterion_id"]
            criterion = operation.update
            criterion.resource_name = client.get_service(
                "CampaignCriterionService"
            ).campaign_criterion_path(
                customer_id_clean, campaign_id, str(criterion_id)
            )
            criterion.bid_modifier = bid_modifier
            operation.update_mask.CopyFrom(
                field_mask_pb2.FieldMask(paths=["bid_modifier"])
            )
            action = "Update"
        else:
            criterion = operation.create
            criterion.campaign = client.get_service("CampaignService").campaign_path(
                customer_id_clean, campaign_id
            )
            criterion.device.type_ = client.enums.DeviceEnum[device].value
            criterion.bid_modifier = bid_modifier
            action = "Create"

        description = (
            f"{action} {device} bid modifier x{bid_modifier} on campaign {campaign_id}"
        )

        def execute():
            return ctx.client.mutate(
                "CampaignCriterionService", customer_id, [operation]
            )

        return ctx.safety.propose(
            tool_name="set_device_bid_modifier",
            customer_id=customer_id,
            description=description,
            payload={
                "campaign_id": campaign_id,
                "device": device,
                "bid_modifier": bid_modifier,
                "updated_existing": bool(existing),
            },
            execute=execute,
        )

    @mcp.tool()
    def add_placement_exclusion(
        customer_id: str,
        campaign_id: str,
        placement_url: str,
        placement_type: str = "WEBSITE",
    ) -> dict:
        """Propose excluding a Display/YouTube/app placement from a campaign."""
        if not placement_url.strip():
            raise ValueError("placement_url must not be empty.")
        valid_types = {
            "WEBSITE", "YOUTUBE_CHANNEL", "YOUTUBE_VIDEO", "MOBILE_APPLICATION"
        }
        if placement_type not in valid_types:
            raise ValueError(
                "placement_type must be WEBSITE, YOUTUBE_CHANNEL, YOUTUBE_VIDEO, "
                "or MOBILE_APPLICATION."
            )
        if placement_type == "YOUTUBE_VIDEO" and len(placement_url.strip()) != 11:
            raise ValueError("YOUTUBE_VIDEO placement must be an 11-character video ID.")

        client = ctx.client.raw
        operation = client.get_type("CampaignCriterionOperation")
        criterion = operation.create
        criterion.campaign = client.get_service("CampaignService").campaign_path(
            customer_id.replace("-", ""), campaign_id
        )
        criterion.negative = True
        value = placement_url.strip()
        if placement_type == "WEBSITE":
            criterion.placement.url = value
        elif placement_type == "YOUTUBE_CHANNEL":
            criterion.youtube_channel.channel_id = value
        elif placement_type == "YOUTUBE_VIDEO":
            criterion.youtube_video.video_id = value
        else:
            criterion.mobile_application.app_id = value

        description = (
            f"Exclude {placement_type} placement '{value}' from campaign {campaign_id}"
        )

        def execute():
            return ctx.client.mutate(
                "CampaignCriterionService", customer_id, [operation]
            )

        return ctx.safety.propose(
            tool_name="add_placement_exclusion",
            customer_id=customer_id,
            description=description,
            payload={
                "campaign_id": campaign_id,
                "placement_url": value,
                "placement_type": placement_type,
            },
            execute=execute,
        )

    @mcp.tool()
    def list_campaign_criteria(customer_id: str, campaign_id: str) -> dict:
        """List targeting criteria on a campaign."""
        query = f"""
            SELECT campaign_criterion.criterion_id, campaign_criterion.type,
                   campaign_criterion.negative, campaign_criterion.bid_modifier,
                   campaign_criterion.location.geo_target_constant,
                   campaign_criterion.language.language_constant,
                   campaign_criterion.device.type,
                   campaign_criterion.ad_schedule.day_of_week,
                   campaign_criterion.ad_schedule.start_hour,
                   campaign_criterion.ad_schedule.end_hour,
                   campaign_criterion.keyword.text
            FROM campaign_criterion
            WHERE campaign.id = {int(campaign_id)}
        """
        rows = ctx.client.search(customer_id, query)
        return {"campaign_id": campaign_id, "criteria": rows, "count": len(rows)}


def _resolve_location_resource_names(
    client,
    locations: list[str],
    *,
    country_code: str | None,
    locale: str,
) -> list[tuple[str, str]]:
    numeric = []
    names = []
    for raw in locations:
        value = str(raw).strip()
        if not value:
            raise ValueError("Location entries must not be empty.")
        if value.isdigit():
            numeric.append((value, f"geoTargetConstants/{value}"))
        else:
            names.append(value)

    resolved: list[tuple[str, str]] = list(numeric)
    if not names:
        return resolved
    if len(names) > 25:
        raise ValueError("At most 25 location names may be resolved per call.")

    request = client.get_type("SuggestGeoTargetConstantsRequest")
    request.locale = locale
    if country_code:
        request.country_code = country_code.upper()
    request.location_names.names.extend(names)
    service = client.get_service("GeoTargetConstantService")
    response = service.suggest_geo_target_constants(request=request)

    suggestions_by_term: dict[str, list] = {}
    for suggestion in response.geo_target_constant_suggestions:
        suggestions_by_term.setdefault(suggestion.search_term.casefold(), []).append(
            suggestion.geo_target_constant
        )

    for name in names:
        candidates = [
            candidate
            for candidate in suggestions_by_term.get(name.casefold(), [])
            if candidate.status.name == "ENABLED"
        ]
        exact = [candidate for candidate in candidates if candidate.name.casefold() == name.casefold()]
        if exact:
            candidates = exact
        unique = {candidate.resource_name: candidate for candidate in candidates}
        if not unique:
            raise ValueError(
                f"No enabled geo target found for {name!r}. Pass a numeric criterion ID."
            )
        if len(unique) > 1:
            options = ", ".join(
                f"{candidate.name} [{candidate.target_type}] {candidate.resource_name}"
                for candidate in list(unique.values())[:8]
            )
            raise ValueError(
                f"Location {name!r} is ambiguous: {options}. Pass the numeric criterion ID."
            )
        candidate = next(iter(unique.values()))
        resolved.append((name, candidate.resource_name))

    return resolved
