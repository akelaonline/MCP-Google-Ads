"""Audience / remarketing list tools."""

from __future__ import annotations

import hashlib
import re

from ..context import AppContext


def _normalize_customer_match_email(value: str) -> str:
    email = "".join(str(value).split()).lower()
    if not email or email.count("@") != 1:
        raise ValueError(f"Invalid email address: {value!r}")
    local, domain = email.split("@", 1)
    if not local or not domain:
        raise ValueError(f"Invalid email address: {value!r}")
    if domain in {"gmail.com", "googlemail.com"}:
        local = local.split("+", 1)[0].replace(".", "")
    return f"{local}@{domain}"


def _normalize_customer_match_phone(value: str) -> str:
    raw = str(value).strip()
    if raw.startswith("+"):
        normalized = "+" + re.sub(r"\D", "", raw[1:])
    else:
        normalized = re.sub(r"\D", "", raw)
    if not re.fullmatch(r"\+[1-9]\d{6,14}", normalized):
        raise ValueError(
            f"Phone number {value!r} must include a country code and be valid E.164 "
            "format, for example +541112345678."
        )
    return normalized


def _legacy_consent_enum(client, value: str, field_name: str):
    normalized = str(value).strip().upper()
    if normalized not in {"UNSPECIFIED", "GRANTED", "DENIED"}:
        raise ValueError(f"{field_name} must be UNSPECIFIED, GRANTED, or DENIED.")
    return getattr(client.enums.ConsentStatusEnum, normalized)


def _build_legacy_identifiers(client, emails, phone_numbers):
    identifiers = []
    for email in emails or []:
        normalized = _normalize_customer_match_email(email)
        identifier = client.get_type("UserIdentifier")
        identifier.hashed_email = _hash_pii(normalized)
        identifiers.append(identifier)
    for phone in phone_numbers or []:
        normalized = _normalize_customer_match_phone(phone)
        identifier = client.get_type("UserIdentifier")
        identifier.hashed_phone_number = _hash_pii(normalized)
        identifiers.append(identifier)
    if not identifiers:
        raise ValueError("No non-empty email or phone identifiers were supplied.")
    if len(identifiers) > 100_000:
        raise ValueError(
            "Google Ads OfflineUserDataJob accepts at most 100,000 identifiers per "
            "AddOfflineUserDataJobOperations request."
        )
    return identifiers


def register(mcp, ctx: AppContext) -> None:
    @mcp.tool()
    def list_user_lists(customer_id: str) -> dict:
        """List remarketing / customer-match audience lists available in the account."""
        query = """
            SELECT user_list.id, user_list.resource_name, user_list.name,
                   user_list.size_for_search, user_list.size_for_display,
                   user_list.membership_status, user_list.type
            FROM user_list
            WHERE user_list.membership_status = 'OPEN'
        """
        rows = ctx.client.search(customer_id, query)
        return {"user_lists": rows, "count": len(rows)}

    @mcp.tool()
    def attach_audience_to_ad_group(
        customer_id: str,
        ad_group_id: str,
        user_list_resource_name: str,
        bid_modifier: float | None = None,
    ) -> dict:
        """Propose attaching a user-list audience to an ad group."""
        if bid_modifier is not None and bid_modifier <= 0:
            raise ValueError("bid_modifier must be greater than 0.")
        customer = ctx.client.assert_customer_allowed(customer_id)
        user_list_resource = ctx.client.assert_resource_name_customer(
            customer,
            user_list_resource_name,
            field_name="user_list_resource_name",
        )
        client = ctx.client.raw
        operation = client.get_type("AdGroupCriterionOperation")
        criterion = operation.create
        criterion.ad_group = client.get_service("AdGroupService").ad_group_path(
            customer, ad_group_id
        )
        criterion.user_list.user_list = user_list_resource
        if bid_modifier is not None:
            criterion.bid_modifier = bid_modifier

        description = (
            f"Attach audience {user_list_resource} to ad group {ad_group_id}"
            + (f" (bid modifier x{bid_modifier})" if bid_modifier else "")
        )

        def execute():
            return ctx.client.mutate(
                "AdGroupCriterionService", customer, [operation]
            )

        return ctx.safety.propose(
            tool_name="attach_audience_to_ad_group",
            customer_id=customer,
            description=description,
            payload={
                "ad_group_id": ad_group_id,
                "user_list_resource_name": user_list_resource,
                "bid_modifier": bid_modifier,
            },
            execute=execute,
        )

    @mcp.tool()
    def remove_audience_from_ad_group(
        customer_id: str, ad_group_id: str, criterion_id: str
    ) -> dict:
        """Propose detaching an audience criterion from an ad group."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        client = ctx.client.raw
        operation = client.get_type("AdGroupCriterionOperation")
        operation.remove = client.get_service(
            "AdGroupCriterionService"
        ).ad_group_criterion_path(customer, ad_group_id, criterion_id)

        description = (
            f"Detach audience criterion {criterion_id} from ad group {ad_group_id}"
        )

        def execute():
            return ctx.client.mutate(
                "AdGroupCriterionService", customer, [operation]
            )

        return ctx.safety.propose(
            tool_name="remove_audience_from_ad_group",
            customer_id=customer,
            description=description,
            payload={"ad_group_id": ad_group_id, "criterion_id": criterion_id},
            execute=execute,
        )

    @mcp.tool()
    def create_remarketing_list(
        customer_id: str,
        name: str,
        membership_days: int = 30,
        description: str | None = None,
        url_contains: str | None = None,
        prepopulate: bool = True,
    ) -> dict:
        """Propose creating a website-visitor remarketing list.

        Google Ads requires an actual rule for a rule-based website audience;
        an empty FlexibleRuleUserList is not an "all visitors" wildcard. Pass
        ``url_contains`` as a hostname or URL fragment that every desired page
        contains (for example ``example.com`` for all pages on that domain).
        The Google Ads tag must already be installed and firing.
        """
        if not (1 <= membership_days <= 540):
            raise ValueError("membership_days must be between 1 and 540.")
        if not name.strip():
            raise ValueError("name must not be empty.")
        if not url_contains or not url_contains.strip():
            raise ValueError(
                "url_contains is required. Use the site hostname (for example "
                "'example.com') to create an all-pages remarketing list."
            )

        customer = ctx.client.assert_customer_allowed(customer_id)
        client = ctx.client.raw
        operation = client.get_type("UserListOperation")
        user_list = operation.create
        user_list.name = name
        if description:
            user_list.description = description
        user_list.membership_status = client.enums.UserListMembershipStatusEnum.OPEN
        user_list.membership_life_span = membership_days
        if prepopulate:
            user_list.rule_based_user_list.prepopulation_status = (
                client.enums.UserListPrepopulationStatusEnum.REQUESTED
            )

        rule_item = client.get_type("UserListRuleItemInfo")
        rule_item.name = "url__"
        rule_item.string_rule_item.operator = (
            client.enums.UserListStringRuleItemOperatorEnum.CONTAINS
        )
        rule_item.string_rule_item.value = url_contains.strip()

        rule_group = client.get_type("UserListRuleItemGroupInfo")
        rule_group.rule_items.append(rule_item)

        flexible_rule = user_list.rule_based_user_list.flexible_rule_user_list
        flexible_rule.inclusive_rule_operator = (
            client.enums.UserListFlexibleRuleOperatorEnum.AND
        )
        operand = client.get_type("FlexibleRuleOperandInfo")
        operand.rule.rule_item_groups.append(rule_group)
        operand.lookback_window_days = membership_days
        flexible_rule.inclusive_operands.append(operand)

        description_text = (
            f"Create remarketing list '{name}' ({membership_days}-day membership) "
            f"for URLs containing '{url_contains.strip()}'"
        )

        def execute():
            return ctx.client.mutate("UserListService", customer, [operation])

        return ctx.safety.propose(
            tool_name="create_remarketing_list",
            customer_id=customer,
            description=description_text,
            payload={
                "name": name,
                "membership_days": membership_days,
                "description": description,
                "url_contains": url_contains.strip(),
                "prepopulate": prepopulate,
            },
            execute=execute,
        )

    @mcp.tool()
    def create_customer_match_list(
        customer_id: str,
        name: str,
        description: str | None = None,
    ) -> dict:
        """Propose creating an empty legacy Google Ads API Customer Match list.

        Existing eligible Customer Match integrations can keep using this path.
        New integrations should prefer create_data_manager_customer_match_list.
        """
        if not name.strip():
            raise ValueError("name must not be empty.")
        customer = ctx.client.assert_customer_allowed(customer_id)
        client = ctx.client.raw
        operation = client.get_type("UserListOperation")
        user_list = operation.create
        user_list.name = name
        if description:
            user_list.description = description
        user_list.crm_based_user_list.upload_key_type = (
            client.enums.CustomerMatchUploadKeyTypeEnum.CONTACT_INFO
        )

        description_text = (
            f"Create legacy Customer Match list '{name}' (empty, ready for uploads)"
        )

        def execute():
            return ctx.client.mutate("UserListService", customer, [operation])

        return ctx.safety.propose(
            tool_name="create_customer_match_list",
            customer_id=customer,
            description=description_text,
            payload={"name": name, "description": description},
            execute=execute,
        )

    @mcp.tool()
    def upload_customer_match_members(
        customer_id: str,
        user_list_resource_name: str,
        emails: list[str] | None = None,
        phone_numbers: list[str] | None = None,
        ad_user_data_consent: str = "UNSPECIFIED",
        ad_personalization_consent: str = "UNSPECIFIED",
    ) -> dict:
        """Propose a legacy OfflineUserDataJob Customer Match upload.

        Existing eligible integrations may continue using this Google Ads API
        path. New Customer Match integrations should use the Data Manager tools.
        PII is normalized and SHA-256 hashed locally before transmission.
        """
        customer = ctx.client.assert_customer_allowed(customer_id)
        user_list_resource = ctx.client.assert_resource_name_customer(
            customer,
            user_list_resource_name,
            field_name="user_list_resource_name",
        )
        client = ctx.client.raw
        identifiers = _build_legacy_identifiers(client, emails, phone_numbers)
        ad_user_data = _legacy_consent_enum(
            client, ad_user_data_consent, "ad_user_data_consent"
        )
        ad_personalization = _legacy_consent_enum(
            client, ad_personalization_consent, "ad_personalization_consent"
        )

        description = (
            f"Upload {len(identifiers)} Customer Match identifier(s) to "
            f"{user_list_resource} via legacy Google Ads API"
        )

        def execute():
            job_service = client.get_service("OfflineUserDataJobService")
            new_job = client.get_type("OfflineUserDataJob")
            new_job.type_ = (
                client.enums.OfflineUserDataJobTypeEnum.CUSTOMER_MATCH_USER_LIST
            )
            metadata = new_job.customer_match_user_list_metadata
            metadata.user_list = user_list_resource
            metadata.consent.ad_user_data = ad_user_data
            metadata.consent.ad_personalization = ad_personalization

            create_job_response = job_service.create_offline_user_data_job(
                customer_id=customer,
                job=new_job,
                enable_match_rate_range_preview=True,
            )
            job_resource_name = create_job_response.resource_name

            add_ops = []
            for identifier in identifiers:
                op = client.get_type("OfflineUserDataJobOperation")
                op.create.user_identifiers.append(identifier)
                add_ops.append(op)

            add_response = job_service.add_offline_user_data_job_operations(
                resource_name=job_resource_name,
                operations=add_ops,
                enable_partial_failure=True,
            )
            partial_failure = getattr(add_response, "partial_failure_error", None)
            partial_failure_message = None
            if partial_failure and getattr(partial_failure, "code", 0):
                partial_failure_message = str(partial_failure)

            job_service.run_offline_user_data_job(resource_name=job_resource_name)
            return {
                "offline_user_data_job": job_resource_name,
                "members_submitted": len(add_ops),
                "partial_failure": partial_failure_message,
                "next_step": (
                    "Call get_customer_match_upload_job to inspect asynchronous status "
                    "and match-rate range."
                ),
            }

        return ctx.safety.propose(
            tool_name="upload_customer_match_members",
            customer_id=customer,
            description=description,
            payload={
                "user_list_resource_name": user_list_resource,
                "email_count": len(emails or []),
                "phone_count": len(phone_numbers or []),
                "identifier_count": len(identifiers),
                "ad_user_data_consent": str(ad_user_data_consent).upper(),
                "ad_personalization_consent": str(ad_personalization_consent).upper(),
            },
            execute=execute,
        )

    @mcp.tool()
    def remove_customer_match_members(
        customer_id: str,
        user_list_resource_name: str,
        emails: list[str] | None = None,
        phone_numbers: list[str] | None = None,
    ) -> dict:
        """Propose removing specific members through legacy OfflineUserDataJobService."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        user_list_resource = ctx.client.assert_resource_name_customer(
            customer,
            user_list_resource_name,
            field_name="user_list_resource_name",
        )
        client = ctx.client.raw
        identifiers = _build_legacy_identifiers(client, emails, phone_numbers)

        def execute():
            job_service = client.get_service("OfflineUserDataJobService")
            new_job = client.get_type("OfflineUserDataJob")
            new_job.type_ = (
                client.enums.OfflineUserDataJobTypeEnum.CUSTOMER_MATCH_USER_LIST
            )
            new_job.customer_match_user_list_metadata.user_list = user_list_resource
            created = job_service.create_offline_user_data_job(
                customer_id=customer,
                job=new_job,
                enable_match_rate_range_preview=True,
            )
            job_resource_name = created.resource_name
            remove_ops = []
            for identifier in identifiers:
                op = client.get_type("OfflineUserDataJobOperation")
                op.remove.user_identifiers.append(identifier)
                remove_ops.append(op)
            add_response = job_service.add_offline_user_data_job_operations(
                resource_name=job_resource_name,
                operations=remove_ops,
                enable_partial_failure=True,
            )
            partial_failure = getattr(add_response, "partial_failure_error", None)
            partial_failure_message = None
            if partial_failure and getattr(partial_failure, "code", 0):
                partial_failure_message = str(partial_failure)
            job_service.run_offline_user_data_job(resource_name=job_resource_name)
            return {
                "offline_user_data_job": job_resource_name,
                "members_submitted_for_removal": len(remove_ops),
                "partial_failure": partial_failure_message,
                "next_step": "Call get_customer_match_upload_job to inspect status.",
            }

        return ctx.safety.propose(
            tool_name="remove_customer_match_members",
            customer_id=customer,
            description=(
                f"Remove {len(identifiers)} Customer Match identifier(s) from "
                f"{user_list_resource} via legacy Google Ads API"
            ),
            payload={
                "user_list_resource_name": user_list_resource,
                "email_count": len(emails or []),
                "phone_count": len(phone_numbers or []),
                "identifier_count": len(identifiers),
            },
            execute=execute,
        )

    @mcp.tool()
    def remove_all_customer_match_members(
        customer_id: str,
        user_list_resource_name: str,
    ) -> dict:
        """Propose clearing all members through legacy OfflineUserDataJobService."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        user_list_resource = ctx.client.assert_resource_name_customer(
            customer,
            user_list_resource_name,
            field_name="user_list_resource_name",
        )
        client = ctx.client.raw

        def execute():
            job_service = client.get_service("OfflineUserDataJobService")
            new_job = client.get_type("OfflineUserDataJob")
            new_job.type_ = (
                client.enums.OfflineUserDataJobTypeEnum.CUSTOMER_MATCH_USER_LIST
            )
            new_job.customer_match_user_list_metadata.user_list = user_list_resource
            created = job_service.create_offline_user_data_job(
                customer_id=customer,
                job=new_job,
                enable_match_rate_range_preview=True,
            )
            job_resource_name = created.resource_name
            operation = client.get_type("OfflineUserDataJobOperation")
            operation.remove_all = True
            job_service.add_offline_user_data_job_operations(
                resource_name=job_resource_name,
                operations=[operation],
                enable_partial_failure=False,
            )
            job_service.run_offline_user_data_job(resource_name=job_resource_name)
            return {
                "offline_user_data_job": job_resource_name,
                "remove_all": True,
                "next_step": "Call get_customer_match_upload_job to inspect status.",
            }

        return ctx.safety.propose(
            tool_name="remove_all_customer_match_members",
            customer_id=customer,
            description=f"Remove ALL Customer Match members from {user_list_resource}",
            payload={"user_list_resource_name": user_list_resource},
            execute=execute,
        )

    @mcp.tool()
    def get_customer_match_upload_job(
        customer_id: str,
        offline_user_data_job_resource_name: str,
    ) -> dict:
        """Read legacy Customer Match job status, failure reason, and match-rate range."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        resource = ctx.client.assert_resource_name_customer(
            customer,
            offline_user_data_job_resource_name,
            field_name="offline_user_data_job_resource_name",
        )
        safe_resource = resource.replace("\\", "\\\\").replace("'", "\\'")
        rows = ctx.client.search(
            customer,
            f"""
            SELECT
                offline_user_data_job.resource_name,
                offline_user_data_job.id,
                offline_user_data_job.type,
                offline_user_data_job.status,
                offline_user_data_job.failure_reason,
                offline_user_data_job.operation_metadata.match_rate_range,
                offline_user_data_job.customer_match_user_list_metadata.user_list
            FROM offline_user_data_job
            WHERE offline_user_data_job.resource_name = '{safe_resource}'
            LIMIT 1
            """,
        )
        return {"job": rows[0] if rows else None, "found": bool(rows)}

    @mcp.tool()
    def search_user_interests(customer_id: str, name_query: str) -> dict:
        """Look up affinity/in-market user-interest segment IDs by name."""
        if not name_query.strip():
            raise ValueError("name_query must not be empty.")
        safe_query = name_query.replace("\\", "\\\\").replace("'", "\\'")
        query = f"""
            SELECT user_interest.user_interest_id, user_interest.name,
                   user_interest.taxonomy_type
            FROM user_interest
            WHERE user_interest.name LIKE '%{safe_query}%'
            LIMIT 50
        """
        rows = ctx.client.search(customer_id, query)
        return {"matches": rows, "count": len(rows)}

    @mcp.tool()
    def add_in_market_or_affinity_audience(
        customer_id: str,
        ad_group_id: str,
        user_interest_id: str,
        bid_modifier: float | None = None,
    ) -> dict:
        """Propose adding an affinity/in-market segment to an ad group."""
        if bid_modifier is not None and bid_modifier <= 0:
            raise ValueError("bid_modifier must be greater than 0.")
        customer = ctx.client.assert_customer_allowed(customer_id)
        client = ctx.client.raw
        operation = client.get_type("AdGroupCriterionOperation")
        criterion = operation.create
        criterion.ad_group = client.get_service("AdGroupService").ad_group_path(
            customer, ad_group_id
        )
        criterion.user_interest.user_interest_category = client.get_service(
            "UserInterestService"
        ).user_interest_path(customer, user_interest_id)
        if bid_modifier is not None:
            criterion.bid_modifier = bid_modifier

        description = (
            f"Add user interest segment {user_interest_id} to ad group {ad_group_id}"
            + (f" (bid modifier x{bid_modifier})" if bid_modifier else "")
        )

        def execute():
            return ctx.client.mutate(
                "AdGroupCriterionService", customer, [operation]
            )

        return ctx.safety.propose(
            tool_name="add_in_market_or_affinity_audience",
            customer_id=customer,
            description=description,
            payload={
                "ad_group_id": ad_group_id,
                "user_interest_id": user_interest_id,
                "bid_modifier": bid_modifier,
            },
            execute=execute,
        )

    @mcp.tool()
    def add_topic_targeting(
        customer_id: str,
        ad_group_id: str,
        topic_id: str,
        negative: bool = False,
    ) -> dict:
        """Propose adding or excluding Display/YouTube topic targeting."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        client = ctx.client.raw
        operation = client.get_type("AdGroupCriterionOperation")
        criterion = operation.create
        criterion.ad_group = client.get_service("AdGroupService").ad_group_path(
            customer, ad_group_id
        )
        criterion.negative = negative
        # Topic constants are global resources ("topicConstants/{id}"); v25 has
        # no TopicConstantService stub to build the path for us.
        criterion.topic.topic_constant = f"topicConstants/{topic_id}"

        verb = "Exclude" if negative else "Target"
        description = f"{verb} topic {topic_id} on ad group {ad_group_id}"

        def execute():
            return ctx.client.mutate(
                "AdGroupCriterionService", customer, [operation]
            )

        return ctx.safety.propose(
            tool_name="add_topic_targeting",
            customer_id=customer,
            description=description,
            payload={
                "ad_group_id": ad_group_id,
                "topic_id": topic_id,
                "negative": negative,
            },
            execute=execute,
        )


def _hash_pii(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
