"""Public Google Ads API v25 services not tied to the core campaign CRUD surface.

Covers field metadata introspection, Local Services leads, third-party app
analytics links, and Travel asset suggestions. All customer-scoped writes use
the shared safety layer and validate resource ownership before execution.
"""

from __future__ import annotations

import proto
from google.protobuf import field_mask_pb2

from ..context import AppContext
from ..errors import GoogleAdsMcpError, format_google_ads_exception


def _call(service, method_name: str, **kwargs):
    from google.ads.googleads.errors import GoogleAdsException

    try:
        return getattr(service, method_name)(**kwargs)
    except GoogleAdsException as ex:
        raise GoogleAdsMcpError(format_google_ads_exception(ex)) from ex


def _as_dict(message):
    return proto.Message.to_dict(message, preserving_proto_field_name=True)


def register(mcp, ctx: AppContext) -> None:
    # ------------------------------------------------------------------
    # GoogleAdsFieldService
    # ------------------------------------------------------------------
    @mcp.tool()
    def search_google_ads_fields(
        query: str,
        page_size: int = 100,
        page_token: str | None = None,
    ) -> dict:
        """Search API field/resource metadata used to build valid GAQL dynamically."""
        clean_query = str(query).strip()
        if not clean_query:
            raise ValueError("query must not be empty.")
        if not 1 <= page_size <= 1000:
            raise ValueError("page_size must be between 1 and 1000.")

        raw = ctx.client.raw
        request = raw.get_type("SearchGoogleAdsFieldsRequest")
        request.query = clean_query
        request.page_size = page_size
        if page_token:
            request.page_token = str(page_token)
        response = _call(
            ctx.client.service("GoogleAdsFieldService"),
            "search_google_ads_fields",
            request=request,
        )
        return {
            "fields": [_as_dict(item) for item in response.results],
            "count": len(response.results),
            "total_results_count": int(response.total_results_count or 0),
            "next_page_token": response.next_page_token or None,
        }

    @mcp.tool()
    def get_google_ads_field(field_name: str) -> dict:
        """Return metadata for one Google Ads field/resource name."""
        name = str(field_name).strip()
        if not name:
            raise ValueError("field_name must not be empty.")
        resource_name = name if name.startswith("googleAdsFields/") else f"googleAdsFields/{name}"
        response = _call(
            ctx.client.service("GoogleAdsFieldService"),
            "get_google_ads_field",
            resource_name=resource_name,
        )
        return _as_dict(response)

    # ------------------------------------------------------------------
    # LocalServicesLeadService
    # ------------------------------------------------------------------
    @mcp.tool()
    def list_local_services_leads(
        customer_id: str,
        status: str | None = None,
        limit: int = 200,
    ) -> dict:
        """List Local Services Ads leads including charge, feedback, and contact data."""
        if not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000.")
        where = ""
        if status:
            clean = status.strip().upper()
            allowed = {
                "ACTIVE", "BOOKED", "CONSUMER_DECLINED", "DECLINED", "DISABLED",
                "EXPIRED", "NEW", "WIPED_OUT",
            }
            if clean not in allowed:
                raise ValueError(f"status must be one of {sorted(allowed)}.")
            where = f"WHERE local_services_lead.lead_status = '{clean}'"
        rows = ctx.client.search(
            customer_id,
            f"""
            SELECT
                local_services_lead.resource_name,
                local_services_lead.id,
                local_services_lead.creation_date_time,
                local_services_lead.lead_type,
                local_services_lead.lead_status,
                local_services_lead.category_id,
                local_services_lead.service_id,
                local_services_lead.locale,
                local_services_lead.lead_charged,
                local_services_lead.lead_feedback_submitted,
                local_services_lead.contact_details,
                local_services_lead.credit_details.credit_state,
                local_services_lead.credit_details.credit_state_last_update_date_time,
                local_services_lead.note.description,
                local_services_lead.note.edit_date_time
            FROM local_services_lead
            {where}
            ORDER BY local_services_lead.creation_date_time DESC
            LIMIT {limit}
            """,
        )
        return {"local_services_leads": rows, "count": len(rows)}

    @mcp.tool()
    def list_local_services_lead_conversations(
        customer_id: str,
        local_services_lead_resource_name: str,
        limit: int = 500,
    ) -> dict:
        """List message/call/booking conversations attached to one Local Services lead."""
        if not 1 <= limit <= 1000:
            raise ValueError("limit must be between 1 and 1000.")
        customer = ctx.client.assert_customer_allowed(customer_id)
        lead = ctx.client.assert_resource_name_customer(
            customer,
            local_services_lead_resource_name,
            field_name="local_services_lead_resource_name",
        )
        escaped = lead.replace("\\", "\\\\").replace("'", "\\'")
        rows = ctx.client.search(
            customer,
            f"""
            SELECT
                local_services_lead_conversation.resource_name,
                local_services_lead_conversation.id,
                local_services_lead_conversation.lead,
                local_services_lead_conversation.event_date_time,
                local_services_lead_conversation.conversation_channel,
                local_services_lead_conversation.participant_type,
                local_services_lead_conversation.message_details.text,
                local_services_lead_conversation.message_details.attachment_urls,
                local_services_lead_conversation.phone_call_details.call_duration_millis,
                local_services_lead_conversation.phone_call_details.call_recording_url
            FROM local_services_lead_conversation
            WHERE local_services_lead_conversation.lead = '{escaped}'
            ORDER BY local_services_lead_conversation.event_date_time ASC
            LIMIT {limit}
            """,
        )
        return {"conversations": rows, "count": len(rows), "lead": lead}

    @mcp.tool()
    def append_local_services_lead_conversation(
        customer_id: str,
        local_services_lead_resource_name: str,
        text: str,
    ) -> dict:
        """Propose appending an advertiser text conversation to a Local Services lead."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        lead = ctx.client.assert_resource_name_customer(
            customer,
            local_services_lead_resource_name,
            field_name="local_services_lead_resource_name",
        )
        clean_text = str(text).strip()
        if not clean_text:
            raise ValueError("text must not be empty.")

        raw = ctx.client.raw
        request = raw.get_type("AppendLeadConversationRequest")
        request.customer_id = customer
        conversation = raw.get_type("Conversation")
        conversation.local_services_lead = lead
        conversation.text = clean_text
        request.conversations.append(conversation)

        def execute():
            response = _call(
                ctx.client.service("LocalServicesLeadService"),
                "append_lead_conversation",
                request=request,
            )
            return _as_dict(response)

        return ctx.safety.propose(
            tool_name="append_local_services_lead_conversation",
            customer_id=customer,
            description=f"Append advertiser conversation to Local Services lead {lead}",
            payload={"local_services_lead_resource_name": lead, "text_length": len(clean_text)},
            execute=execute,
        )

    @mcp.tool()
    def provide_local_services_lead_feedback(
        customer_id: str,
        local_services_lead_resource_name: str,
        survey_answer: str,
        reason: str | None = None,
        other_reason_comment: str | None = None,
    ) -> dict:
        """Propose submitting Local Services lead quality feedback.

        survey_answer accepts VERY_SATISFIED, SATISFIED, NEUTRAL, DISSATISFIED,
        or VERY_DISSATISFIED. Satisfied/dissatisfied reason enums can be supplied
        with ``reason``; neutral feedback does not require a detail message.
        """
        customer = ctx.client.assert_customer_allowed(customer_id)
        lead = ctx.client.assert_resource_name_customer(
            customer,
            local_services_lead_resource_name,
            field_name="local_services_lead_resource_name",
        )
        answer = survey_answer.strip().upper()
        allowed_answers = {
            "VERY_SATISFIED", "SATISFIED", "NEUTRAL", "DISSATISFIED", "VERY_DISSATISFIED"
        }
        if answer not in allowed_answers:
            raise ValueError(f"survey_answer must be one of {sorted(allowed_answers)}.")

        raw = ctx.client.raw
        request = raw.get_type("ProvideLeadFeedbackRequest")
        request.resource_name = lead
        request.survey_answer = getattr(
            raw.enums.LocalServicesLeadSurveyAnswerEnum, answer
        )

        reason_name = str(reason).strip().upper() if reason else None
        if answer in {"SATISFIED", "VERY_SATISFIED"} and reason_name:
            request.survey_satisfied.survey_satisfied_reason = getattr(
                raw.enums.LocalServicesLeadSurveySatisfiedReasonEnum,
                reason_name,
            )
            if other_reason_comment:
                request.survey_satisfied.other_reason_comment = other_reason_comment.strip()
        elif answer in {"DISSATISFIED", "VERY_DISSATISFIED"} and reason_name:
            request.survey_dissatisfied.survey_dissatisfied_reason = getattr(
                raw.enums.LocalServicesLeadSurveyDissatisfiedReasonEnum,
                reason_name,
            )
            if other_reason_comment:
                request.survey_dissatisfied.other_reason_comment = other_reason_comment.strip()

        def execute():
            response = _call(
                ctx.client.service("LocalServicesLeadService"),
                "provide_lead_feedback",
                request=request,
            )
            return _as_dict(response)

        return ctx.safety.propose(
            tool_name="provide_local_services_lead_feedback",
            customer_id=customer,
            description=f"Submit {answer} feedback for Local Services lead {lead}",
            payload={
                "local_services_lead_resource_name": lead,
                "survey_answer": answer,
                "reason": reason_name,
                "has_comment": bool(other_reason_comment),
            },
            execute=execute,
        )

    # ------------------------------------------------------------------
    # AccountLinkService / ThirdPartyAppAnalyticsLinkService
    # ------------------------------------------------------------------
    @mcp.tool()
    def list_third_party_app_analytics_links(customer_id: str) -> dict:
        """List third-party app analytics account links and shareable link IDs."""
        rows = ctx.client.search(
            customer_id,
            """
            SELECT
                account_link.resource_name,
                account_link.account_link_id,
                account_link.status,
                account_link.type,
                account_link.third_party_app_analytics.app_analytics_provider_id,
                account_link.third_party_app_analytics.app_id,
                account_link.third_party_app_analytics.app_vendor,
                third_party_app_analytics_link.resource_name,
                third_party_app_analytics_link.shareable_link_id
            FROM third_party_app_analytics_link
            ORDER BY account_link.account_link_id DESC
            """,
        )
        return {"third_party_app_analytics_links": rows, "count": len(rows)}

    @mcp.tool()
    def create_third_party_app_analytics_link(
        customer_id: str,
        app_analytics_provider_id: str,
        app_id: str,
        app_vendor: str,
    ) -> dict:
        """Propose creating a third-party mobile-app analytics account link."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        provider = str(app_analytics_provider_id).strip()
        if not provider.isdigit() or int(provider) <= 0:
            raise ValueError("app_analytics_provider_id must be a positive integer.")
        clean_app_id = str(app_id).strip()
        if not clean_app_id:
            raise ValueError("app_id must not be empty.")
        vendor = app_vendor.strip().upper()
        if vendor not in {"APPLE_APP_STORE", "GOOGLE_APP_STORE"}:
            raise ValueError("app_vendor must be APPLE_APP_STORE or GOOGLE_APP_STORE.")

        raw = ctx.client.raw
        link = raw.get_type("AccountLink")
        link.third_party_app_analytics.app_analytics_provider_id = int(provider)
        link.third_party_app_analytics.app_id = clean_app_id
        link.third_party_app_analytics.app_vendor = getattr(raw.enums.MobileAppVendorEnum, vendor)

        def execute():
            response = _call(
                ctx.client.service("AccountLinkService"),
                "create_account_link",
                customer_id=customer,
                account_link=link,
            )
            return {"resource_name": getattr(response, "resource_name", None)}

        return ctx.safety.propose(
            tool_name="create_third_party_app_analytics_link",
            customer_id=customer,
            description=f"Create {vendor} third-party app analytics link for {clean_app_id}",
            payload={
                "app_analytics_provider_id": provider,
                "app_id": clean_app_id,
                "app_vendor": vendor,
            },
            execute=execute,
        )

    @mcp.tool()
    def set_third_party_app_analytics_link_status(
        customer_id: str,
        account_link_resource_name: str,
        status: str,
    ) -> dict:
        """Propose updating a third-party app analytics account-link status."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        resource = ctx.client.assert_resource_name_customer(
            customer,
            account_link_resource_name,
            field_name="account_link_resource_name",
        )
        clean_status = status.strip().upper()
        allowed = {"ENABLED", "REJECTED", "REMOVED", "REVOKED"}
        if clean_status not in allowed:
            raise ValueError(f"status must be one of {sorted(allowed)}.")

        raw = ctx.client.raw
        operation = raw.get_type("AccountLinkOperation")
        if clean_status == "REMOVED":
            operation.remove = resource
        else:
            operation.update.resource_name = resource
            operation.update.status = getattr(raw.enums.AccountLinkStatusEnum, clean_status)
            operation.update_mask.CopyFrom(field_mask_pb2.FieldMask(paths=["status"]))

        def execute():
            response = _call(
                ctx.client.service("AccountLinkService"),
                "mutate_account_link",
                customer_id=customer,
                operation=operation,
            )
            return _as_dict(response)

        return ctx.safety.propose(
            tool_name="set_third_party_app_analytics_link_status",
            customer_id=customer,
            description=f"Set app analytics account link {resource} -> {clean_status}",
            payload={"account_link_resource_name": resource, "status": clean_status},
            execute=execute,
        )

    @mcp.tool()
    def regenerate_third_party_app_analytics_shareable_id(
        customer_id: str,
        third_party_app_analytics_link_resource_name: str,
    ) -> dict:
        """Propose regenerating the shareable ID used by a third-party analytics provider."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        resource = ctx.client.assert_resource_name_customer(
            customer,
            third_party_app_analytics_link_resource_name,
            field_name="third_party_app_analytics_link_resource_name",
        )

        def execute():
            _call(
                ctx.client.service("ThirdPartyAppAnalyticsLinkService"),
                "regenerate_shareable_link_id",
                resource_name=resource,
            )
            return {
                "resource_name": resource,
                "next_step": "Call list_third_party_app_analytics_links to read the new shareable_link_id.",
            }

        return ctx.safety.propose(
            tool_name="regenerate_third_party_app_analytics_shareable_id",
            customer_id=customer,
            description=f"Regenerate shareable ID for app analytics link {resource}",
            payload={"third_party_app_analytics_link_resource_name": resource},
            execute=execute,
        )

    # ------------------------------------------------------------------
    # TravelAssetSuggestionService
    # ------------------------------------------------------------------
    @mcp.tool()
    def suggest_travel_assets(
        customer_id: str,
        language_option: str,
        place_ids: list[str] | None = None,
    ) -> dict:
        """Retrieve best-effort hotel/travel asset suggestions for Google Maps Place IDs."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        language = str(language_option).strip()
        if not language:
            raise ValueError("language_option must be a BCP-47 language such as en-US.")
        places = [str(value).strip() for value in (place_ids or []) if str(value).strip()]
        if len(places) > 100:
            raise ValueError("place_ids supports at most 100 hotels per MCP call.")

        raw = ctx.client.raw
        request = raw.get_type("SuggestTravelAssetsRequest")
        request.customer_id = customer
        request.language_option = language
        request.place_ids.extend(places)
        response = _call(
            ctx.client.service("TravelAssetSuggestionService"),
            "suggest_travel_assets",
            request=request,
        )
        result = _as_dict(response)
        result["customer_id"] = customer
        result["language_option"] = language
        result["requested_place_ids"] = places
        return result
