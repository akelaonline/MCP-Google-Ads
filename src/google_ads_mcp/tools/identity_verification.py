"""Advertiser identity verification workflows for Google Ads API v25."""

from __future__ import annotations

from google.ads.googleads.errors import GoogleAdsException

from ..context import AppContext
from ..errors import GoogleAdsMcpError, format_google_ads_exception

_PROGRAM = "ADVERTISER_IDENTITY_VERIFICATION"


def _enum(value) -> str:
    name = getattr(value, "name", None)
    return str(name) if name else str(value).rsplit(".", 1)[-1]


def register(mcp, ctx: AppContext) -> None:
    @mcp.tool()
    def get_identity_verification(customer_id: str) -> dict:
        """Read advertiser identity-verification requirements and progress."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        raw = ctx.client.raw
        request = raw.get_type("GetIdentityVerificationRequest")
        request.customer_id = customer
        try:
            response = raw.get_service(
                "IdentityVerificationService"
            ).get_identity_verification(request=request)
        except GoogleAdsException as ex:
            raise GoogleAdsMcpError(format_google_ads_exception(ex)) from ex

        items = []
        for item in response.identity_verification:
            requirement = item.identity_verification_requirement
            progress = item.verification_progress
            items.append(
                {
                    "verification_program": _enum(item.verification_program),
                    "requirement": {
                        "verification_start_deadline_time": getattr(
                            requirement, "verification_start_deadline_time", ""
                        ),
                        "verification_completion_deadline_time": getattr(
                            requirement, "verification_completion_deadline_time", ""
                        ),
                    },
                    "progress": {
                        "program_status": _enum(getattr(progress, "program_status", 0)),
                        "invitation_link_expiration_time": getattr(
                            progress, "invitation_link_expiration_time", ""
                        ),
                        "action_url": getattr(progress, "action_url", ""),
                    },
                }
            )
        return {"count": len(items), "identity_verifications": items}

    @mcp.tool()
    def start_advertiser_identity_verification(customer_id: str) -> dict:
        """Propose starting Google's Advertiser Identity Verification program."""
        customer = ctx.client.assert_customer_allowed(customer_id)

        def execute():
            raw = ctx.client.raw
            request = raw.get_type("StartIdentityVerificationRequest")
            request.customer_id = customer
            request.verification_program = getattr(
                raw.enums.IdentityVerificationProgramEnum, _PROGRAM
            )
            try:
                raw.get_service(
                    "IdentityVerificationService"
                ).start_identity_verification(request=request)
            except GoogleAdsException as ex:
                raise GoogleAdsMcpError(format_google_ads_exception(ex)) from ex
            return {
                "verification_program": _PROGRAM,
                "started": True,
                "next_step": (
                    "Call get_identity_verification and follow Google's action_url "
                    "if user action is required."
                ),
            }

        return ctx.safety.propose(
            tool_name="start_advertiser_identity_verification",
            customer_id=customer,
            description=f"Start Advertiser Identity Verification for customer {customer}",
            payload={"verification_program": _PROGRAM},
            execute=execute,
        )
