"""Modern Google Ads product-account linking for API v25."""

from __future__ import annotations

from ..context import AppContext
from ..errors import GoogleAdsMcpError, format_google_ads_exception


def _positive_id(value: str, field_name: str) -> int:
    text = str(value).strip()
    if not text.isdigit() or int(text) <= 0:
        raise ValueError(f"{field_name} must be a positive numeric ID.")
    return int(text)


def _call_google(service, method_name: str, **kwargs):
    from google.ads.googleads.errors import GoogleAdsException

    try:
        return getattr(service, method_name)(**kwargs)
    except GoogleAdsException as ex:
        raise GoogleAdsMcpError(format_google_ads_exception(ex)) from ex


def register(mcp, ctx: AppContext) -> None:
    @mcp.tool()
    def list_product_links(customer_id: str) -> dict:
        """List modern product links such as Merchant Center, Google Ads, and partners."""
        rows = ctx.client.search(
            customer_id,
            """
            SELECT
                product_link.resource_name,
                product_link.product_link_id,
                product_link.type,
                product_link.merchant_center.merchant_center_id,
                product_link.google_ads.customer,
                product_link.data_partner.data_partner_id,
                product_link.advertising_partner.customer,
                product_link.advertising_partner_properties.allowed_domain
            FROM product_link
            ORDER BY product_link.product_link_id DESC
            """,
        )
        return {"product_links": rows, "count": len(rows)}

    @mcp.tool()
    def list_product_link_invitations(
        customer_id: str,
        status: str | None = None,
        product_type: str | None = None,
    ) -> dict:
        """List incoming/outgoing product-link invitations and their status."""
        filters: list[str] = []
        if status:
            clean = status.strip().upper()
            if not clean.replace("_", "").isalnum():
                raise ValueError("status must be a valid invitation-status enum name.")
            filters.append(f"product_link_invitation.status = '{clean}'")
        if product_type:
            clean_type = product_type.strip().upper()
            if not clean_type.replace("_", "").isalnum():
                raise ValueError("product_type must be a valid linked-product enum name.")
            filters.append(f"product_link_invitation.type = '{clean_type}'")
        where = "WHERE " + " AND ".join(filters) if filters else ""
        rows = ctx.client.search(
            customer_id,
            f"""
            SELECT
                product_link_invitation.resource_name,
                product_link_invitation.product_link_invitation_id,
                product_link_invitation.status,
                product_link_invitation.type,
                product_link_invitation.merchant_center.merchant_center_id,
                product_link_invitation.hotel_center.hotel_center_id,
                product_link_invitation.advertising_partner.customer,
                product_link_invitation.advertising_partner_properties.allowed_domain
            FROM product_link_invitation
            {where}
            ORDER BY product_link_invitation.product_link_invitation_id DESC
            """,
        )
        return {"product_link_invitations": rows, "count": len(rows)}

    @mcp.tool()
    def create_merchant_center_link(
        customer_id: str,
        merchant_center_id: str,
        validate_only: bool = False,
    ) -> dict:
        """Propose a direct Merchant Center link when the authenticated user is admin of both.

        Google no longer allows new Merchant Center link *requests* to originate
        from Google Ads. If direct linking is not permitted, initiate the request
        in Merchant Center/Merchant API and accept it here with
        ``accept_product_link_invitation``.
        """
        customer = ctx.client.assert_customer_allowed(customer_id)
        merchant_id = _positive_id(merchant_center_id, "merchant_center_id")
        raw = ctx.client.raw
        link = raw.get_type("ProductLink")
        link.merchant_center.merchant_center_id = merchant_id
        service = ctx.client.service("ProductLinkService")

        def execute():
            response = _call_google(
                service,
                "create_product_link",
                customer_id=customer,
                product_link=link,
            )
            return {"resource_name": getattr(response, "resource_name", None)}

        return ctx.safety.propose(
            tool_name="create_product_link",
            customer_id=customer,
            description=(
                f"Create direct Merchant Center link {merchant_id} for Google Ads "
                f"customer {customer}"
            ),
            payload={
                "type": "MERCHANT_CENTER",
                "merchant_center_id": str(merchant_id),
                "validate_only": bool(validate_only),
            },
            execute=execute if not validate_only else lambda: _validate_product_link(
                ctx, customer, link
            ),
        )

    @mcp.tool()
    def create_google_ads_product_link(
        customer_id: str,
        linked_customer_id: str,
        validate_only: bool = False,
    ) -> dict:
        """Propose a modern Google Ads-to-Google Ads product data-sharing link."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        linked = ctx.client.assert_customer_allowed(linked_customer_id)
        if linked == customer:
            raise ValueError("linked_customer_id must differ from customer_id.")
        raw = ctx.client.raw
        link = raw.get_type("ProductLink")
        link.google_ads.customer = f"customers/{linked}"
        service = ctx.client.service("ProductLinkService")

        def execute():
            response = _call_google(
                service,
                "create_product_link",
                customer_id=customer,
                product_link=link,
            )
            return {"resource_name": getattr(response, "resource_name", None)}

        return ctx.safety.propose(
            tool_name="create_product_link",
            customer_id=customer,
            description=f"Create Google Ads product link from {customer} to {linked}",
            payload={
                "type": "GOOGLE_ADS",
                "linked_customer_id": linked,
                "validate_only": bool(validate_only),
            },
            execute=execute if not validate_only else lambda: _validate_product_link(
                ctx, customer, link
            ),
        )

    @mcp.tool()
    def create_data_partner_link(
        customer_id: str,
        data_partner_id: str,
        validate_only: bool = False,
    ) -> dict:
        """Propose a direct link to an eligible Google Ads Data Partner account."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        partner_id = _positive_id(data_partner_id, "data_partner_id")
        raw = ctx.client.raw
        link = raw.get_type("ProductLink")
        link.data_partner.data_partner_id = partner_id
        service = ctx.client.service("ProductLinkService")

        def execute():
            response = _call_google(
                service,
                "create_product_link",
                customer_id=customer,
                product_link=link,
            )
            return {"resource_name": getattr(response, "resource_name", None)}

        return ctx.safety.propose(
            tool_name="create_product_link",
            customer_id=customer,
            description=f"Create Data Partner link {partner_id} for customer {customer}",
            payload={
                "type": "DATA_PARTNER",
                "data_partner_id": str(partner_id),
                "validate_only": bool(validate_only),
            },
            execute=execute if not validate_only else lambda: _validate_product_link(
                ctx, customer, link
            ),
        )

    @mcp.tool()
    def remove_product_link(
        customer_id: str,
        product_link_resource_name: str,
        validate_only: bool = False,
    ) -> dict:
        """Propose removing an active modern product link."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        resource = ctx.client.assert_resource_name_customer(
            customer,
            product_link_resource_name,
            field_name="product_link_resource_name",
        )
        service = ctx.client.service("ProductLinkService")

        def execute():
            response = _call_google(
                service,
                "remove_product_link",
                customer_id=customer,
                resource_name=resource,
                validate_only=bool(validate_only),
            )
            return {"resource_name": getattr(response, "resource_name", resource)}

        return ctx.safety.propose(
            tool_name="remove_product_link",
            customer_id=customer,
            description=f"Remove active product link {resource}",
            payload={
                "product_link_resource_name": resource,
                "validate_only": bool(validate_only),
            },
            execute=execute,
        )

    @mcp.tool()
    def accept_product_link_invitation(
        customer_id: str,
        invitation_resource_name: str,
    ) -> dict:
        """Propose accepting a PENDING_APPROVAL product-link invitation."""
        return _update_invitation(
            ctx,
            customer_id,
            invitation_resource_name,
            "ACCEPTED",
            "accept_product_link_invitation",
        )

    @mcp.tool()
    def reject_product_link_invitation(
        customer_id: str,
        invitation_resource_name: str,
    ) -> dict:
        """Propose rejecting a PENDING_APPROVAL product-link invitation."""
        return _update_invitation(
            ctx,
            customer_id,
            invitation_resource_name,
            "REJECTED",
            "reject_product_link_invitation",
        )

    @mcp.tool()
    def revoke_product_link_invitation(
        customer_id: str,
        invitation_resource_name: str,
    ) -> dict:
        """Propose revoking/removing an existing outbound product-link invitation."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        resource = ctx.client.assert_resource_name_customer(
            customer,
            invitation_resource_name,
            field_name="invitation_resource_name",
        )
        service = ctx.client.service("ProductLinkInvitationService")

        def execute():
            response = _call_google(
                service,
                "remove_product_link_invitation",
                customer_id=customer,
                resource_name=resource,
            )
            return {"resource_name": getattr(response, "resource_name", resource)}

        return ctx.safety.propose(
            tool_name="revoke_product_link_invitation",
            customer_id=customer,
            description=f"Revoke product-link invitation {resource}",
            payload={"invitation_resource_name": resource},
            execute=execute,
        )


def _update_invitation(
    ctx: AppContext,
    customer_id: str,
    invitation_resource_name: str,
    status_name: str,
    tool_name: str,
) -> dict:
    customer = ctx.client.assert_customer_allowed(customer_id)
    resource = ctx.client.assert_resource_name_customer(
        customer,
        invitation_resource_name,
        field_name="invitation_resource_name",
    )
    raw = ctx.client.raw
    status = getattr(raw.enums.ProductLinkInvitationStatusEnum, status_name)
    service = ctx.client.service("ProductLinkInvitationService")

    def execute():
        response = _call_google(
            service,
            "update_product_link_invitation",
            customer_id=customer,
            resource_name=resource,
            product_link_invitation_status=status,
        )
        return {
            "resource_name": getattr(response, "resource_name", resource),
            "status": status_name,
        }

    return ctx.safety.propose(
        tool_name=tool_name,
        customer_id=customer,
        description=f"Set product-link invitation {resource} to {status_name}",
        payload={
            "invitation_resource_name": resource,
            "status": status_name,
        },
        execute=execute,
    )


def _validate_product_link(ctx: AppContext, customer_id: str, link) -> dict:
    """Best-effort validate-only path for ProductLinkService create.

    CreateProductLink itself has no validate_only request field in the current
    contract. Returning this structured preview keeps the public tool signature
    stable without pretending Google performed server-side validation.
    """
    import proto

    return {
        "validated_locally": True,
        "google_validate_only_supported": False,
        "customer_id": customer_id,
        "product_link": proto.Message.to_dict(link, preserving_proto_field_name=True),
    }
