"""Audience / remarketing list tools."""

from __future__ import annotations

import hashlib

from ..context import AppContext


def register(mcp, ctx: AppContext) -> None:
    @mcp.tool()
    def list_user_lists(customer_id: str) -> dict:
        """List remarketing / customer-match audience lists available in the account."""
        query = """
            SELECT user_list.id, user_list.name, user_list.size_for_search,
                   user_list.size_for_display, user_list.membership_status, user_list.type
            FROM user_list
            WHERE user_list.membership_status = 'OPEN'
        """
        rows = ctx.client.search(customer_id, query)
        return {"user_lists": rows}

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
        client = ctx.client.raw
        operation = client.get_type("AdGroupCriterionOperation")
        criterion = operation.create
        criterion.ad_group = client.get_service("AdGroupService").ad_group_path(
            customer_id.replace("-", ""), ad_group_id
        )
        criterion.user_list.user_list = user_list_resource_name
        if bid_modifier is not None:
            criterion.bid_modifier = bid_modifier

        description = (
            f"Attach audience {user_list_resource_name} to ad group {ad_group_id}"
            + (f" (bid modifier x{bid_modifier})" if bid_modifier else "")
        )

        def execute():
            return ctx.client.mutate(
                "AdGroupCriterionService", customer_id, [operation]
            )

        return ctx.safety.propose(
            tool_name="attach_audience_to_ad_group",
            customer_id=customer_id,
            description=description,
            payload={
                "ad_group_id": ad_group_id,
                "user_list_resource_name": user_list_resource_name,
                "bid_modifier": bid_modifier,
            },
            execute=execute,
        )

    @mcp.tool()
    def remove_audience_from_ad_group(
        customer_id: str, ad_group_id: str, criterion_id: str
    ) -> dict:
        """Propose detaching an audience criterion from an ad group."""
        client = ctx.client.raw
        operation = client.get_type("AdGroupCriterionOperation")
        operation.remove = client.get_service(
            "AdGroupCriterionService"
        ).ad_group_criterion_path(
            customer_id.replace("-", ""), ad_group_id, criterion_id
        )

        description = (
            f"Detach audience criterion {criterion_id} from ad group {ad_group_id}"
        )

        def execute():
            return ctx.client.mutate(
                "AdGroupCriterionService", customer_id, [operation]
            )

        return ctx.safety.propose(
            tool_name="remove_audience_from_ad_group",
            customer_id=customer_id,
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

        # Official v25 rule shape: URL built-in variable + CONTAINS condition,
        # wrapped in a flexible rule with one inclusive operand.
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
            return ctx.client.mutate("UserListService", customer_id, [operation])

        return ctx.safety.propose(
            tool_name="create_remarketing_list",
            customer_id=customer_id,
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
        """Propose creating an empty Customer Match list."""
        if not name.strip():
            raise ValueError("name must not be empty.")
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
            f"Create Customer Match list '{name}' (empty, ready for uploads)"
        )

        def execute():
            return ctx.client.mutate("UserListService", customer_id, [operation])

        return ctx.safety.propose(
            tool_name="create_customer_match_list",
            customer_id=customer_id,
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
    ) -> dict:
        """Propose uploading locally SHA-256-hashed Customer Match members."""
        if not emails and not phone_numbers:
            raise ValueError("Provide at least one of emails or phone_numbers.")

        client = ctx.client.raw
        operations = []
        for email in emails or []:
            normalized = email.strip().lower()
            if not normalized:
                continue
            identifier = client.get_type("UserIdentifier")
            identifier.hashed_email = _hash_pii(normalized)
            operations.append(identifier)
        for phone in phone_numbers or []:
            normalized = phone.strip()
            if not normalized:
                continue
            identifier = client.get_type("UserIdentifier")
            identifier.hashed_phone_number = _hash_pii(normalized)
            operations.append(identifier)
        if not operations:
            raise ValueError("No non-empty email or phone identifiers were supplied.")

        description = (
            f"Upload {len(emails or [])} email(s) and {len(phone_numbers or [])} phone(s) "
            f"to {user_list_resource_name}"
        )

        def execute():
            job_service = client.get_service("OfflineUserDataJobService")
            new_job = client.get_type("OfflineUserDataJob")
            new_job.type_ = (
                client.enums.OfflineUserDataJobTypeEnum.CUSTOMER_MATCH_USER_LIST
            )
            new_job.customer_match_user_list_metadata.user_list = (
                user_list_resource_name
            )

            create_job_response = job_service.create_offline_user_data_job(
                customer_id=customer_id.replace("-", ""), job=new_job
            )
            job_resource_name = create_job_response.resource_name

            add_ops = []
            for identifier in operations:
                op = client.get_type("OfflineUserDataJobOperation")
                op.create.user_identifiers.append(identifier)
                add_ops.append(op)

            job_service.add_offline_user_data_job_operations(
                resource_name=job_resource_name,
                operations=add_ops,
                enable_partial_failure=True,
            )
            job_service.run_offline_user_data_job(resource_name=job_resource_name)
            return {
                "offline_user_data_job": job_resource_name,
                "members_submitted": len(add_ops),
            }

        return ctx.safety.propose(
            tool_name="upload_customer_match_members",
            customer_id=customer_id,
            description=description,
            payload={
                "user_list_resource_name": user_list_resource_name,
                "email_count": len(emails or []),
                "phone_count": len(phone_numbers or []),
            },
            execute=execute,
        )

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
        client = ctx.client.raw
        operation = client.get_type("AdGroupCriterionOperation")
        criterion = operation.create
        criterion.ad_group = client.get_service("AdGroupService").ad_group_path(
            customer_id.replace("-", ""), ad_group_id
        )
        criterion.user_interest.user_interest_category = client.get_service(
            "UserInterestService"
        ).user_interest_path(customer_id.replace("-", ""), user_interest_id)
        if bid_modifier is not None:
            criterion.bid_modifier = bid_modifier

        description = (
            f"Add user interest segment {user_interest_id} to ad group {ad_group_id}"
            + (f" (bid modifier x{bid_modifier})" if bid_modifier else "")
        )

        def execute():
            return ctx.client.mutate(
                "AdGroupCriterionService", customer_id, [operation]
            )

        return ctx.safety.propose(
            tool_name="add_in_market_or_affinity_audience",
            customer_id=customer_id,
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
        client = ctx.client.raw
        topic_service = client.get_service("TopicConstantService")
        operation = client.get_type("AdGroupCriterionOperation")
        criterion = operation.create
        criterion.ad_group = client.get_service("AdGroupService").ad_group_path(
            customer_id.replace("-", ""), ad_group_id
        )
        criterion.negative = negative
        criterion.topic.topic_constant = topic_service.topic_constant_path(topic_id)

        verb = "Exclude" if negative else "Target"
        description = f"{verb} topic {topic_id} on ad group {ad_group_id}"

        def execute():
            return ctx.client.mutate(
                "AdGroupCriterionService", customer_id, [operation]
            )

        return ctx.safety.propose(
            tool_name="add_topic_targeting",
            customer_id=customer_id,
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
