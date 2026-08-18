"""Google Ads customer user-access and invitation tools for API v25."""

from __future__ import annotations

from google.protobuf import field_mask_pb2

from ..context import AppContext

_ACCESS_ROLES = {"ADMIN", "STANDARD", "READ_ONLY", "EMAIL_ONLY"}


def register(mcp, ctx: AppContext) -> None:
    @mcp.tool()
    def list_account_users(customer_id: str) -> dict:
        """List users with direct access to a Google Ads customer."""
        query = """
            SELECT
                customer_user_access.user_id,
                customer_user_access.email_address,
                customer_user_access.access_role,
                customer_user_access.access_creation_date_time,
                customer_user_access.inviter_user_email_address,
                customer_user_access.pending_multi_party_auth_review,
                customer_user_access.resource_name
            FROM customer_user_access
            ORDER BY customer_user_access.email_address
        """
        rows = ctx.client.search(customer_id, query)
        return {"users": rows, "count": len(rows)}

    @mcp.tool()
    def list_user_access_invitations(customer_id: str) -> dict:
        """List user-access invitations visible through GAQL for a customer."""
        query = """
            SELECT
                customer_user_access_invitation.invitation_id,
                customer_user_access_invitation.email_address,
                customer_user_access_invitation.access_role,
                customer_user_access_invitation.invitation_status,
                customer_user_access_invitation.creation_date_time,
                customer_user_access_invitation.resource_name
            FROM customer_user_access_invitation
            ORDER BY customer_user_access_invitation.creation_date_time DESC
        """
        rows = ctx.client.search(customer_id, query)
        return {
            "invitations": rows,
            "count": len(rows),
            "note": (
                "Invitations awaiting multi-party authorization review may not be returned "
                "by GoogleAdsService Search/SearchStream."
            ),
        }

    @mcp.tool()
    def invite_account_user(
        customer_id: str,
        email_address: str,
        access_role: str,
    ) -> dict:
        """Propose inviting a user to a Google Ads customer."""
        role = _validate_role(access_role)
        email = email_address.strip()
        if not email or "@" not in email:
            raise ValueError("email_address must be a valid email address.")

        client = ctx.client.raw
        operation = client.get_type("CustomerUserAccessInvitationOperation")
        invitation = operation.create
        invitation.email_address = email
        invitation.access_role = client.enums.AccessRoleEnum[role].value

        def execute():
            return ctx.client.mutate(
                "CustomerUserAccessInvitationService",
                customer_id,
                [operation],
                operations_field="operation",
            )

        return ctx.safety.propose(
            tool_name="invite_account_user",
            customer_id=customer_id,
            description=f"Invite {email} to customer {customer_id} with {role} access",
            payload={"email_address": email, "access_role": role},
            execute=execute,
        )

    @mcp.tool()
    def update_user_access_role(
        customer_id: str,
        user_id: str,
        access_role: str,
    ) -> dict:
        """Propose changing an existing Google Ads user's access role."""
        role = _validate_role(access_role)
        client = ctx.client.raw
        customer = customer_id.replace("-", "")
        operation = client.get_type("CustomerUserAccessOperation")
        operation.update.resource_name = (
            f"customers/{customer}/customerUserAccesses/{int(user_id)}"
        )
        operation.update.access_role = client.enums.AccessRoleEnum[role].value
        operation.update_mask.CopyFrom(field_mask_pb2.FieldMask(paths=["access_role"]))

        def execute():
            return ctx.client.mutate(
                "CustomerUserAccessService",
                customer_id,
                [operation],
                operations_field="operation",
            )

        return ctx.safety.propose(
            tool_name="update_user_access_role",
            customer_id=customer_id,
            description=f"Set Google Ads user {user_id} access role to {role}",
            payload={"user_id": str(user_id), "access_role": role},
            execute=execute,
        )

    @mcp.tool()
    def remove_account_user(customer_id: str, user_id: str) -> dict:
        """Propose permanently removing a user's access to a Google Ads customer."""
        customer = customer_id.replace("-", "")
        operation = ctx.client.raw.get_type("CustomerUserAccessOperation")
        operation.remove = f"customers/{customer}/customerUserAccesses/{int(user_id)}"

        def execute():
            return ctx.client.mutate(
                "CustomerUserAccessService",
                customer_id,
                [operation],
                operations_field="operation",
            )

        return ctx.safety.propose(
            tool_name="remove_account_user",
            customer_id=customer_id,
            description=f"Permanently remove Google Ads user access for user {user_id}",
            payload={"user_id": str(user_id)},
            execute=execute,
        )

    @mcp.tool()
    def revoke_user_access_invitation(customer_id: str, invitation_id: str) -> dict:
        """Propose revoking a pending Google Ads user invitation."""
        customer = customer_id.replace("-", "")
        operation = ctx.client.raw.get_type("CustomerUserAccessInvitationOperation")
        operation.remove = (
            f"customers/{customer}/customerUserAccessInvitations/{int(invitation_id)}"
        )

        def execute():
            return ctx.client.mutate(
                "CustomerUserAccessInvitationService",
                customer_id,
                [operation],
                operations_field="operation",
            )

        return ctx.safety.propose(
            tool_name="revoke_user_access_invitation",
            customer_id=customer_id,
            description=f"Revoke Google Ads user invitation {invitation_id}",
            payload={"invitation_id": str(invitation_id)},
            execute=execute,
        )


def _validate_role(access_role: str) -> str:
    role = access_role.strip().upper()
    if role not in _ACCESS_ROLES:
        raise ValueError(
            "access_role must be one of ADMIN, STANDARD, READ_ONLY, EMAIL_ONLY."
        )
    return role
