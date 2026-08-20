"""Direct Customer Match uploads through UserDataService for Google Ads API v25."""

from __future__ import annotations

import hashlib
import re

from google.ads.googleads.errors import GoogleAdsException

from ..context import AppContext
from ..errors import GoogleAdsMcpError, format_google_ads_exception

_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def register(mcp, ctx: AppContext) -> None:
    @mcp.tool()
    def upload_customer_match_user_data_direct(
        customer_id: str,
        user_list_resource_name: str,
        operation: str,
        emails: list[str] | None = None,
        phone_numbers: list[str] | None = None,
    ) -> dict:
        """Propose a direct UserDataService add/remove Customer Match upload.

        PII is normalized and SHA-256 hashed locally before transmission and never
        included in the audit payload.
        """
        customer = ctx.client.assert_customer_allowed(customer_id)
        user_list = _user_list(customer, user_list_resource_name)
        action = operation.strip().upper()
        if action not in {"CREATE", "REMOVE"}:
            raise ValueError("operation must be CREATE or REMOVE.")
        identities = _identities(emails or [], phone_numbers or [])
        if not identities:
            raise ValueError("Provide at least one valid email or phone number.")
        if len(identities) > 100_000:
            raise ValueError("A direct upload is limited to 100,000 user data operations.")

        raw = ctx.client.raw
        operations = []
        for kind, digest in identities:
            user = raw.get_type("UserData")
            identifier = raw.get_type("UserIdentifier")
            if kind == "email":
                identifier.hashed_email = digest
            else:
                identifier.hashed_phone_number = digest
            user.user_identifiers.append(identifier)
            item = raw.get_type("UserDataOperation")
            if action == "CREATE":
                raw.copy_from(item.create, user)
            else:
                raw.copy_from(item.remove, user)
            operations.append(item)

        def execute():
            request = raw.get_type("UploadUserDataRequest")
            request.customer_id = customer
            request.customer_match_user_list_metadata.user_list = user_list
            request.operations.extend(operations)
            try:
                response = raw.get_service("UserDataService").upload_user_data(
                    request=request
                )
            except GoogleAdsException as ex:
                raise GoogleAdsMcpError(format_google_ads_exception(ex)) from ex
            return {
                "upload_date_time": response.upload_date_time,
                "received_operations_count": int(response.received_operations_count),
                "operation": action,
            }

        return ctx.safety.propose(
            tool_name="upload_customer_match_user_data_direct",
            customer_id=customer,
            description=(
                f"Direct {action.lower()} of {len(operations)} Customer Match "
                f"identity record(s) for {user_list}"
            ),
            payload={
                "user_list_resource_name": user_list,
                "operation": action,
                "email_count": sum(1 for kind, _ in identities if kind == "email"),
                "phone_count": sum(1 for kind, _ in identities if kind == "phone"),
            },
            execute=execute,
        )


def _identities(emails: list[str], phone_numbers: list[str]) -> list[tuple[str, str]]:
    result: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()
    for raw in emails:
        value = str(raw).strip().lower()
        if not value:
            continue
        if not _EMAIL.fullmatch(value):
            raise ValueError(f"Invalid email address: {raw!r}.")
        item = ("email", _hash(value))
        if item not in seen:
            seen.add(item)
            result.append(item)
    for raw in phone_numbers:
        value = re.sub(r"[^0-9+]", "", str(raw).strip())
        if not value:
            continue
        if not value.startswith("+") or not 8 <= len(value) <= 16:
            raise ValueError(
                "phone_numbers must be normalized E.164-style values beginning with '+'."
            )
        item = ("phone", _hash(value))
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _user_list(customer_id: str, value: str) -> str:
    resource = value.strip()
    prefix = f"customers/{customer_id}/userLists/"
    if not resource.startswith(prefix) or not resource[len(prefix) :].isdigit():
        raise ValueError(f"user_list_resource_name must match '{prefix}{{user_list_id}}'.")
    return resource
