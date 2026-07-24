"""Audience / remarketing list tools.

Covers three layers: reading existing lists, creating new ones (remarketing
from a site tag, or customer match from an uploaded contact list), and
attaching a list to an ad group for targeting/observation.
"""

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
        """Propose attaching an audience (user list) to an ad group for observation or targeting.

        Args:
            user_list_resource_name: e.g. "customers/123/userLists/456" (from list_user_lists).
            bid_modifier: Optional bid modifier, e.g. 1.2 for +20%.
        """
        client = ctx.client.raw
        operation = client.get_type("AdGroupCriterionOperation")
        criterion = operation.create
        criterion.ad_group = client.get_service("AdGroupService").ad_group_path(
            customer_id.replace("-", ""), ad_group_id
        )
        criterion.user_list.user_list = user_list_resource_name
        if bid_modifier is not None:
            criterion.bid_modifier = bid_modifier

        description = f"Attach audience {user_list_resource_name} to ad group {ad_group_id}" + (
            f" (bid modifier x{bid_modifier})" if bid_modifier else ""
        )

        def execute():
            return ctx.client.mutate("AdGroupCriterionService", customer_id, [operation])

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
    def remove_audience_from_ad_group(customer_id: str, ad_group_id: str, criterion_id: str) -> dict:
        """Propose detaching an audience criterion from an ad group.

        Args:
            criterion_id: The ad_group_criterion.criterion_id of the audience
                attachment (visible in get_ad_group_performance / GAQL on
                ad_group_criterion where criterion.type = 'USER_LIST').
        """
        client = ctx.client.raw
        operation = client.get_type("AdGroupCriterionOperation")
        operation.remove = client.get_service("AdGroupCriterionService").ad_group_criterion_path(
            customer_id.replace("-", ""), ad_group_id, criterion_id
        )

        description = f"Detach audience criterion {criterion_id} from ad group {ad_group_id}"

        def execute():
            return ctx.client.mutate("AdGroupCriterionService", customer_id, [operation])

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
    ) -> dict:
        """Propose creating a website-visitor remarketing list.

        Requires the account's Google Ads tag to already be firing on the
        site — this creates the list definition, it does not install the tag.
        New visitors start populating the list after creation; it does not
        backfill past traffic.

        Args:
            membership_days: How long a visitor stays on the list after their
                last matching visit, 1-540.
        """
        if not (1 <= membership_days <= 540):
            raise ValueError("membership_days must be between 1 and 540.")

        client = ctx.client.raw
        operation = client.get_type("UserListOperation")
        user_list = operation.create
        user_list.name = name
        if description:
            user_list.description = description
        user_list.membership_life_span = membership_days
        # An empty rule-based user list with no rule_item_groups matches "all
        # visitors" once linked to a remarketing tag — the common case for a
        # general "all site visitors" list. For narrower rules (e.g. "visited
        # /checkout"), edit rule_item_groups after creation in the UI or via
        # a follow-up GAQL-informed mutate; the API surface for arbitrary URL
        # rules is intentionally not wrapped here to avoid a footgun tool
        # that silently creates a list matching nobody.
        user_list.rule_based_user_list.flexible_rule_user_list.SetInParent()

        description_text = (
            f"Create remarketing list '{name}' ({membership_days}-day membership)"
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
            },
            execute=execute,
        )

    @mcp.tool()
    def create_customer_match_list(
        customer_id: str,
        name: str,
        description: str | None = None,
    ) -> dict:
        """Propose creating an empty Customer Match list (contact-based audience).

        Creates the list container only — use upload_customer_match_members
        to add hashed emails/phones afterward. Requires the account to be
        enrolled in Customer Match (subject to Google's policy approval,
        checked at upload time, not at list-creation time).
        """
        client = ctx.client.raw
        operation = client.get_type("UserListOperation")
        user_list = operation.create
        user_list.name = name
        if description:
            user_list.description = description
        user_list.crm_based_user_list.upload_key_type = (
            client.enums.CustomerMatchUploadKeyTypeEnum.CONTACT_INFO
        )

        description_text = f"Create Customer Match list '{name}' (empty, ready for uploads)"

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
        """Propose uploading contacts to a Customer Match list.

        Emails and phone numbers are normalized and SHA-256 hashed locally
        before sending — Google Ads requires hashed PII, raw contact data is
        never transmitted in the clear by this tool.

        Args:
            user_list_resource_name: e.g. "customers/123/userLists/456"
                (from create_customer_match_list or list_user_lists).
            emails: Plain email addresses; lowercased and trimmed before hashing.
            phone_numbers: Phone numbers in E.164 format (e.g. "+5491112345678");
                hashed as-is, so normalize to E.164 before calling.
        """
        if not emails and not phone_numbers:
            raise ValueError("Provide at least one of emails or phone_numbers.")

        client = ctx.client.raw

        operations = []
        for email in emails or []:
            identifier = client.get_type("UserIdentifier")
            identifier.hashed_email = _hash_pii(email.strip().lower())
            operations.append(("email", identifier))
        for phone in phone_numbers or []:
            identifier = client.get_type("UserIdentifier")
            identifier.hashed_phone_number = _hash_pii(phone.strip())
            operations.append(("phone", identifier))

        description = (
            f"Upload {len(emails or [])} email(s) and {len(phone_numbers or [])} phone(s) "
            f"to {user_list_resource_name}"
        )

        def execute():
            job_service = client.get_service("OfflineUserDataJobService")
            # Create the offline user data job.
            new_job = client.get_type("OfflineUserDataJob")
            new_job.type_ = client.enums.OfflineUserDataJobTypeEnum.CUSTOMER_MATCH_USER_LIST
            new_job.customer_match_user_list_metadata.user_list = user_list_resource_name

            create_job_response = job_service.create_offline_user_data_job(
                customer_id=customer_id.replace("-", ""), job=new_job
            )
            job_resource_name = create_job_response.resource_name

            add_ops = []
            for kind, identifier in operations:
                op = client.get_type("OfflineUserDataJobOperation")
                op.create.user_identifiers.append(identifier)
                add_ops.append(op)

            job_service.add_offline_user_data_job_operations(
                resource_name=job_resource_name, operations=add_ops
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


def _hash_pii(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
