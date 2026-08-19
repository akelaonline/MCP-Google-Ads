"""Google Data Manager API tools for modern Customer Match workflows."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Any

from ..context import AppContext
from ..data_manager_client import (
    DataManagerClient,
    data_manager_user_list_resource,
    google_ads_account_resource,
)

_CONSENT_VALUES = {
    "CONSENT_STATUS_UNSPECIFIED",
    "CONSENT_GRANTED",
    "CONSENT_DENIED",
}


def _login_account_resource(ctx: AppContext, login_customer_id: str | None) -> str | None:
    value = login_customer_id or getattr(ctx.settings, "login_customer_id", None)
    if not value:
        return None
    normalized = str(value).replace("-", "").strip()
    if not normalized.isdigit():
        raise ValueError("login_customer_id must be numeric with optional dashes.")
    return google_ads_account_resource(normalized)


def _customer(ctx: AppContext, customer_id: str) -> str:
    return ctx.client.assert_customer_allowed(customer_id)


def _audience_id(value: str) -> str:
    text = str(value).strip()
    if not text.isdigit():
        raise ValueError("user_list_id must be the numeric Data Manager/Google Ads audience ID.")
    return text


def _consent(value: str, field_name: str) -> str:
    normalized = str(value).strip().upper()
    if normalized not in _CONSENT_VALUES:
        allowed = ", ".join(sorted(_CONSENT_VALUES))
        raise ValueError(f"{field_name} must be one of: {allowed}.")
    return normalized


def _normalize_email(value: str) -> str:
    email = "".join(str(value).split()).lower()
    if not email or email.count("@") != 1:
        raise ValueError(f"Invalid email address: {value!r}")
    local, domain = email.split("@", 1)
    if not local or not domain:
        raise ValueError(f"Invalid email address: {value!r}")
    if domain in {"gmail.com", "googlemail.com"}:
        local = local.split("+", 1)[0].replace(".", "")
    return f"{local}@{domain}"


def _normalize_phone(value: str) -> str:
    raw = str(value).strip()
    if not raw:
        raise ValueError("Phone number must not be empty.")
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


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _members(emails: list[str] | None, phone_numbers: list[str] | None) -> list[dict[str, Any]]:
    members: list[dict[str, Any]] = []
    for value in emails or []:
        normalized = _normalize_email(value)
        members.append(
            {
                "compositeData": {
                    "userData": {
                        "userIdentifiers": [{"emailAddress": _hash(normalized)}]
                    }
                }
            }
        )
    for value in phone_numbers or []:
        normalized = _normalize_phone(value)
        members.append(
            {
                "compositeData": {
                    "userData": {
                        "userIdentifiers": [{"phoneNumber": _hash(normalized)}]
                    }
                }
            }
        )
    if not members:
        raise ValueError("Provide at least one non-empty email or phone number.")
    if len(members) > 10_000:
        raise ValueError("Data Manager API accepts at most 10,000 audience members per request.")
    return members


def _destination(
    ctx: AppContext,
    customer_id: str,
    user_list_id: str,
    login_customer_id: str | None,
) -> dict[str, Any]:
    destination: dict[str, Any] = {
        "operatingAccount": {
            "accountType": "GOOGLE_ADS",
            "accountId": customer_id,
        },
        "productDestinationId": user_list_id,
    }
    login = login_customer_id or getattr(ctx.settings, "login_customer_id", None)
    if login:
        normalized_login = str(login).replace("-", "").strip()
        if not normalized_login.isdigit():
            raise ValueError("login_customer_id must be numeric with optional dashes.")
        destination["loginAccount"] = {
            "accountType": "GOOGLE_ADS",
            "accountId": normalized_login,
        }
    return destination


def register(mcp, ctx: AppContext) -> None:
    dm = DataManagerClient(ctx.settings)

    @mcp.tool()
    def get_data_manager_configuration() -> dict:
        """Check whether optional Google Data Manager API support is configured."""
        return {
            "configured": dm.configured,
            "project_id_configured": bool(ctx.settings.data_manager_project_id),
            "refresh_token_configured": bool(ctx.settings.data_manager_refresh_token),
            "uses_login_customer_id": bool(ctx.settings.login_customer_id),
        }

    @mcp.tool()
    def list_data_manager_customer_match_lists(
        customer_id: str,
        page_size: int = 100,
        page_token: str | None = None,
        filter_expression: str | None = None,
        login_customer_id: str | None = None,
    ) -> dict:
        """List Customer Match-compatible UserLists through Data Manager API."""
        customer = _customer(ctx, customer_id)
        if page_size < 1 or page_size > 1000:
            raise ValueError("page_size must be between 1 and 1000.")
        parent = google_ads_account_resource(customer)
        response = dm.request(
            "GET",
            f"{parent}/userLists",
            query={
                "pageSize": page_size,
                "pageToken": page_token,
                "filter": filter_expression,
            },
            login_account=_login_account_resource(ctx, login_customer_id),
        )
        lists = response.get("userLists", [])
        return {
            "user_lists": lists,
            "count": len(lists),
            "next_page_token": response.get("nextPageToken"),
        }

    @mcp.tool()
    def get_data_manager_customer_match_list(
        customer_id: str,
        user_list_id: str,
        login_customer_id: str | None = None,
    ) -> dict:
        """Retrieve one Data Manager UserList by numeric audience ID."""
        customer = _customer(ctx, customer_id)
        audience = _audience_id(user_list_id)
        name = data_manager_user_list_resource(customer, audience)
        return dm.request(
            "GET",
            name,
            login_account=_login_account_resource(ctx, login_customer_id),
        )

    @mcp.tool()
    def create_data_manager_customer_match_list(
        customer_id: str,
        display_name: str,
        description: str | None = None,
        membership_days: int = 30,
        integration_code: str | None = None,
        login_customer_id: str | None = None,
        validate_only: bool = False,
    ) -> dict:
        """Propose creating a contact-info Customer Match list via Data Manager API."""
        customer = _customer(ctx, customer_id)
        if not display_name.strip():
            raise ValueError("display_name must not be empty.")
        if not (1 <= membership_days <= 540):
            raise ValueError("membership_days must be between 1 and 540.")
        parent = google_ads_account_resource(customer)
        body: dict[str, Any] = {
            "displayName": display_name.strip(),
            "description": description or "Customer Match audience created by google-ads-mcp",
            "ingestedUserListInfo": {
                "contactIdInfo": {"dataSourceType": "DATA_SOURCE_TYPE_FIRST_PARTY"},
                "uploadKeyTypes": ["CONTACT_ID"],
            },
            "membershipDuration": f"{membership_days * 86400}s",
        }
        if integration_code:
            body["integrationCode"] = integration_code.strip()
        login_header = _login_account_resource(ctx, login_customer_id)

        def execute():
            return dm.request(
                "POST",
                f"{parent}/userLists",
                body=body,
                query={"validateOnly": str(bool(validate_only)).lower()},
                login_account=login_header,
            )

        return ctx.safety.propose(
            tool_name="create_data_manager_customer_match_list",
            customer_id=customer,
            description=f"Create Data Manager Customer Match list '{display_name.strip()}'",
            payload={
                "display_name": display_name.strip(),
                "membership_days": membership_days,
                "integration_code": integration_code,
                "validate_only": validate_only,
            },
            execute=execute,
        )

    @mcp.tool()
    def update_data_manager_customer_match_list(
        customer_id: str,
        user_list_id: str,
        display_name: str | None = None,
        description: str | None = None,
        membership_days: int | None = None,
        login_customer_id: str | None = None,
        validate_only: bool = False,
    ) -> dict:
        """Propose updating mutable Data Manager Customer Match list fields."""
        customer = _customer(ctx, customer_id)
        audience = _audience_id(user_list_id)
        if display_name is None and description is None and membership_days is None:
            raise ValueError("Provide at least one field to update.")
        body: dict[str, Any] = {
            "name": data_manager_user_list_resource(customer, audience)
        }
        mask: list[str] = []
        if display_name is not None:
            if not display_name.strip():
                raise ValueError("display_name must not be empty.")
            body["displayName"] = display_name.strip()
            mask.append("displayName")
        if description is not None:
            body["description"] = description
            mask.append("description")
        if membership_days is not None:
            if not (1 <= membership_days <= 540):
                raise ValueError("membership_days must be between 1 and 540.")
            body["membershipDuration"] = f"{membership_days * 86400}s"
            mask.append("membershipDuration")
        resource_name = body["name"]
        login_header = _login_account_resource(ctx, login_customer_id)

        def execute():
            return dm.request(
                "PATCH",
                resource_name,
                body=body,
                query={
                    "updateMask": ",".join(mask),
                    "validateOnly": str(bool(validate_only)).lower(),
                },
                login_account=login_header,
            )

        return ctx.safety.propose(
            tool_name="update_data_manager_customer_match_list",
            customer_id=customer,
            description=f"Update Data Manager Customer Match list {audience}",
            payload={
                "user_list_id": audience,
                "fields": mask,
                "validate_only": validate_only,
            },
            execute=execute,
        )

    @mcp.tool()
    def delete_data_manager_customer_match_list(
        customer_id: str,
        user_list_id: str,
        login_customer_id: str | None = None,
        validate_only: bool = False,
    ) -> dict:
        """Propose deleting a Data Manager Customer Match list."""
        customer = _customer(ctx, customer_id)
        audience = _audience_id(user_list_id)
        resource_name = data_manager_user_list_resource(customer, audience)
        login_header = _login_account_resource(ctx, login_customer_id)

        def execute():
            dm.request(
                "DELETE",
                resource_name,
                query={"validateOnly": str(bool(validate_only)).lower()},
                login_account=login_header,
            )
            return {"deleted": resource_name, "validate_only": validate_only}

        return ctx.safety.propose(
            tool_name="delete_data_manager_customer_match_list",
            customer_id=customer,
            description=f"Delete Data Manager Customer Match list {audience}",
            payload={"user_list_id": audience, "validate_only": validate_only},
            execute=execute,
        )

    @mcp.tool()
    def upload_customer_match_members_data_manager(
        customer_id: str,
        user_list_id: str,
        emails: list[str] | None = None,
        phone_numbers: list[str] | None = None,
        ad_user_data_consent: str = "CONSENT_STATUS_UNSPECIFIED",
        ad_personalization_consent: str = "CONSENT_STATUS_UNSPECIFIED",
        customer_match_terms_accepted: bool = False,
        login_customer_id: str | None = None,
        validate_only: bool = False,
    ) -> dict:
        """Propose adding Customer Match members through Data Manager API.

        PII is normalized and SHA-256 hashed locally and is never placed in the
        audit payload. ``customer_match_terms_accepted`` must be explicitly true.
        """
        customer = _customer(ctx, customer_id)
        audience = _audience_id(user_list_id)
        if not customer_match_terms_accepted:
            raise ValueError(
                "customer_match_terms_accepted must be true after the advertiser has "
                "accepted Google's Customer Match terms."
            )
        audience_members = _members(emails, phone_numbers)
        body = {
            "destinations": [
                _destination(ctx, customer, audience, login_customer_id)
            ],
            "audienceMembers": audience_members,
            "consent": {
                "adUserData": _consent(ad_user_data_consent, "ad_user_data_consent"),
                "adPersonalization": _consent(
                    ad_personalization_consent, "ad_personalization_consent"
                ),
            },
            "encoding": "HEX",
            "termsOfService": {"customerMatchTermsOfServiceStatus": "ACCEPTED"},
            "validateOnly": bool(validate_only),
        }

        def execute():
            return dm.request("POST", "audienceMembers:ingest", body=body)

        return ctx.safety.propose(
            tool_name="upload_customer_match_members_data_manager",
            customer_id=customer,
            description=(
                f"Upload {len(audience_members)} Customer Match member(s) to audience "
                f"{audience} through Data Manager API"
            ),
            payload={
                "user_list_id": audience,
                "member_count": len(audience_members),
                "email_count": len(emails or []),
                "phone_count": len(phone_numbers or []),
                "ad_user_data_consent": body["consent"]["adUserData"],
                "ad_personalization_consent": body["consent"]["adPersonalization"],
                "validate_only": validate_only,
            },
            execute=execute,
        )

    @mcp.tool()
    def remove_customer_match_members_data_manager(
        customer_id: str,
        user_list_id: str,
        emails: list[str] | None = None,
        phone_numbers: list[str] | None = None,
        login_customer_id: str | None = None,
        validate_only: bool = False,
    ) -> dict:
        """Propose removing specific Customer Match members through Data Manager API."""
        customer = _customer(ctx, customer_id)
        audience = _audience_id(user_list_id)
        audience_members = _members(emails, phone_numbers)
        body = {
            "destinations": [
                _destination(ctx, customer, audience, login_customer_id)
            ],
            "audienceMembers": audience_members,
            "encoding": "HEX",
            "validateOnly": bool(validate_only),
        }

        def execute():
            return dm.request("POST", "audienceMembers:remove", body=body)

        return ctx.safety.propose(
            tool_name="remove_customer_match_members_data_manager",
            customer_id=customer,
            description=(
                f"Remove {len(audience_members)} Customer Match member(s) from audience "
                f"{audience} through Data Manager API"
            ),
            payload={
                "user_list_id": audience,
                "member_count": len(audience_members),
                "email_count": len(emails or []),
                "phone_count": len(phone_numbers or []),
                "validate_only": validate_only,
            },
            execute=execute,
        )

    @mcp.tool()
    def remove_all_customer_match_members_data_manager(
        customer_id: str,
        user_list_id: str,
        login_customer_id: str | None = None,
        remove_as_of_time: str | None = None,
        validate_only: bool = False,
    ) -> dict:
        """Propose removing all members from one Customer Match audience."""
        customer = _customer(ctx, customer_id)
        audience = _audience_id(user_list_id)
        if remove_as_of_time:
            try:
                parsed = datetime.fromisoformat(remove_as_of_time.replace("Z", "+00:00"))
            except ValueError as ex:
                raise ValueError("remove_as_of_time must be RFC 3339.") from ex
            if parsed.tzinfo is None:
                raise ValueError("remove_as_of_time must include a timezone offset or Z.")
            if parsed.astimezone(timezone.utc) > datetime.now(timezone.utc):
                raise ValueError("remove_as_of_time must not be in the future.")
        body: dict[str, Any] = {
            "destinations": [
                _destination(ctx, customer, audience, login_customer_id)
            ],
            "validateOnly": bool(validate_only),
        }
        if remove_as_of_time:
            body["removeAsOfTime"] = remove_as_of_time

        def execute():
            return dm.request("POST", "audienceMembers:removeAll", body=body)

        return ctx.safety.propose(
            tool_name="remove_all_customer_match_members_data_manager",
            customer_id=customer,
            description=(
                f"Remove ALL Customer Match members from audience {audience} through "
                "Data Manager API"
            ),
            payload={
                "user_list_id": audience,
                "remove_as_of_time": remove_as_of_time,
                "validate_only": validate_only,
            },
            execute=execute,
        )

    @mcp.tool()
    def get_data_manager_request_status(request_id: str) -> dict:
        """Retrieve processing diagnostics for a Data Manager ingestion/removal request."""
        value = str(request_id).strip()
        if not value:
            raise ValueError("request_id must not be empty.")
        return dm.request(
            "GET",
            "requestStatus:retrieve",
            query={"requestId": value},
        )
