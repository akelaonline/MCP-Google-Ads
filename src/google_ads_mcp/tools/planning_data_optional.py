"""Reach Planner, UserDataService, incentives, MPA, and allowlisted insight RPCs.

The allowlisted services are fully wired at the MCP layer. Availability remains
a Google-side account entitlement: callers without access receive Google's
NotAllowlisted/Authorization error rather than a fake local success.
"""

from __future__ import annotations

import proto
from google.protobuf import json_format

from ..client import _customer_id_from_resource_name, _customer_scoped_resource_names
from ..context import AppContext
from ..errors import GoogleAdsMcpError, format_google_ads_exception


def _call(ctx: AppContext, service_name: str, method_name: str, request):
    from google.ads.googleads.errors import GoogleAdsException

    try:
        return getattr(ctx.client.service(service_name), method_name)(request=request)
    except GoogleAdsException as ex:
        raise GoogleAdsMcpError(format_google_ads_exception(ex)) from ex


def _proto_call(
    ctx: AppContext,
    *,
    service_name: str,
    method_name: str,
    request_type: str,
    request_payload: dict | None = None,
    customer_id: str | None = None,
) -> dict:
    """Parse a documented protobuf-JSON request and return a plain response dict."""
    payload = dict(request_payload or {})
    customer = None
    if customer_id is not None:
        customer = ctx.client.assert_customer_allowed(customer_id)
        payload.pop("customer_id", None)
        payload.pop("customerId", None)
    request = ctx.client.raw.get_type(request_type)
    try:
        json_format.ParseDict(payload, request._pb, ignore_unknown_fields=False)
    except Exception as ex:
        raise ValueError(f"Invalid {request_type} payload: {ex}") from ex
    if customer is not None and hasattr(request, "customer_id"):
        request.customer_id = customer
    if customer is not None:
        for resource in _customer_scoped_resource_names(request):
            owner = _customer_id_from_resource_name(resource)
            if owner is not None and owner != customer:
                raise GoogleAdsMcpError(
                    f"Cross-customer request blocked: {resource} belongs to {owner}, "
                    f"but the requested customer is {customer}."
                )
    response = _call(ctx, service_name, method_name, request)
    return proto.Message.to_dict(response, preserving_proto_field_name=True)


def register(mcp, ctx: AppContext) -> None:
    # ------------------------------------------------------------------
    # ReachPlanService — public, read-only
    # ------------------------------------------------------------------
    @mcp.tool()
    def generate_reach_plan_conversion_rates(customer_id: str, request: dict) -> dict:
        """Call ReachPlanService.GenerateConversionRates with protobuf-JSON request fields."""
        return _proto_call(
            ctx,
            service_name="ReachPlanService",
            method_name="generate_conversion_rates",
            request_type="GenerateConversionRatesRequest",
            request_payload=request,
            customer_id=customer_id,
        )

    @mcp.tool()
    def generate_reach_forecast(customer_id: str, request: dict) -> dict:
        """Generate a YouTube reach forecast with the complete v25 request schema."""
        return _proto_call(
            ctx,
            service_name="ReachPlanService",
            method_name="generate_reach_forecast",
            request_type="GenerateReachForecastRequest",
            request_payload=request,
            customer_id=customer_id,
        )

    @mcp.tool()
    def list_reach_plan_plannable_locations(request: dict | None = None) -> dict:
        """List locations available to Reach Planner."""
        return _proto_call(
            ctx,
            service_name="ReachPlanService",
            method_name="list_plannable_locations",
            request_type="ListPlannableLocationsRequest",
            request_payload=request,
        )

    @mcp.tool()
    def list_reach_plan_plannable_products(request: dict) -> dict:
        """List YouTube products/formats available for a plannable location."""
        return _proto_call(
            ctx,
            service_name="ReachPlanService",
            method_name="list_plannable_products",
            request_type="ListPlannableProductsRequest",
            request_payload=request,
        )

    @mcp.tool()
    def list_reach_plan_plannable_user_interests(customer_id: str, request: dict) -> dict:
        """List user interests eligible for Reach Planner."""
        return _proto_call(
            ctx,
            service_name="ReachPlanService",
            method_name="list_plannable_user_interests",
            request_type="ListPlannableUserInterestsRequest",
            request_payload=request,
            customer_id=customer_id,
        )

    @mcp.tool()
    def list_reach_plan_plannable_user_lists(customer_id: str, request: dict) -> dict:
        """List Customer Match/user lists and their Reach Planner eligibility."""
        return _proto_call(
            ctx,
            service_name="ReachPlanService",
            method_name="list_plannable_user_lists",
            request_type="ListPlannableUserListsRequest",
            request_payload=request,
            customer_id=customer_id,
        )

    # ------------------------------------------------------------------
    # UserDataService — sensitive, synchronous small-batch Customer Match
    # ------------------------------------------------------------------
    @mcp.tool()
    def upload_user_data_small_batch(
        customer_id: str,
        user_list_resource_name: str,
        operations: list[dict],
        consent: dict | None = None,
    ) -> dict:
        """Propose a small synchronous UserDataService Customer Match upload.

        ``operations`` uses UserDataOperation protobuf-JSON (`create` or `remove`).
        Identifiers such as email/phone MUST already be normalized SHA-256 values
        in `hashed_email` / `hashed_phone_number`; this tool never accepts plaintext
        email/phone fields and never writes identifiers to the audit log.

        Google limits UserDataService to 10 operations and 100 identifiers/request;
        each UserData may contain at most 20 identifiers. Use Data Manager or
        OfflineUserDataJob for larger uploads.
        """
        customer = ctx.client.assert_customer_allowed(customer_id)
        user_list = ctx.client.assert_resource_name_customer(
            customer, user_list_resource_name, field_name="user_list_resource_name"
        )
        if not 1 <= len(operations) <= 10:
            raise ValueError("UserDataService requires 1-10 operations per request.")
        raw = ctx.client.raw
        request = raw.get_type("UploadUserDataRequest")
        request.customer_id = customer
        request.customer_match_user_list_metadata.user_list = user_list
        if consent:
            try:
                json_format.ParseDict(
                    consent,
                    request.customer_match_user_list_metadata.consent._pb,
                    ignore_unknown_fields=False,
                )
            except Exception as ex:
                raise ValueError(f"Invalid consent payload: {ex}") from ex
        identifier_count = 0
        create_count = 0
        remove_count = 0
        for item in operations:
            serialized = str(item).lower()
            if any(key in serialized for key in ("'email':", '"email":', "'phone_number':", '"phone_number":')):
                raise ValueError(
                    "Plaintext email/phone fields are not accepted. Use hashed_email / "
                    "hashed_phone_number after Google normalization and SHA-256 hashing."
                )
            operation = raw.get_type("UserDataOperation")
            try:
                json_format.ParseDict(item, operation._pb, ignore_unknown_fields=False)
            except Exception as ex:
                raise ValueError(f"Invalid UserDataOperation payload: {ex}") from ex
            selected = operation._pb.WhichOneof("operation")
            if selected not in {"create", "remove"}:
                raise ValueError("Each UserDataOperation must contain create or remove.")
            user_data = getattr(operation, selected)
            count = len(user_data.user_identifiers)
            if not 1 <= count <= 20:
                raise ValueError("Each UserData create/remove must contain 1-20 user_identifiers.")
            identifier_count += count
            if selected == "create":
                create_count += 1
            else:
                remove_count += 1
            request.operations.append(operation)
        if identifier_count > 100:
            raise ValueError("UserDataService allows at most 100 user_identifiers per request.")

        def execute():
            response = _call(ctx, "UserDataService", "upload_user_data", request)
            return proto.Message.to_dict(response, preserving_proto_field_name=True)

        return ctx.safety.propose(
            tool_name="upload_user_data_small_batch",
            customer_id=customer,
            description=(
                f"Upload {len(operations)} UserData operation(s) / {identifier_count} "
                f"identifier(s) to {user_list}"
            ),
            payload={
                "user_list_resource_name": user_list,
                "operation_count": len(operations),
                "create_operation_count": create_count,
                "remove_operation_count": remove_count,
                "identifier_count": identifier_count,
                "consent_supplied": bool(consent),
            },
            execute=execute,
        )

    # ------------------------------------------------------------------
    # IncentiveService — allowlisted
    # ------------------------------------------------------------------
    @mcp.tool()
    def fetch_google_ads_incentives(
        language_code: str = "en",
        incentive_type: str = "ACQUISITION",
    ) -> dict:
        """Fetch available Google Ads incentives (Google allowlist required)."""
        raw = ctx.client.raw
        request = raw.get_type("FetchIncentiveRequest")
        request.language_code = str(language_code).strip().lower()
        if incentive_type:
            request.incentive_type = getattr(
                raw.enums.IncentiveTypeEnum, str(incentive_type).strip().upper()
            )
        response = _call(ctx, "IncentiveService", "fetch_incentive", request)
        return proto.Message.to_dict(response, preserving_proto_field_name=True)

    @mcp.tool()
    def apply_google_ads_incentive(
        customer_id: str,
        selected_incentive_id: int,
        country_code: str,
    ) -> dict:
        """Propose applying an allowlisted Google Ads incentive to a customer."""
        customer = ctx.client.assert_customer_allowed(customer_id)
        incentive_id = int(selected_incentive_id)
        country = str(country_code).strip().upper()
        if incentive_id <= 0 or len(country) != 2:
            raise ValueError("selected_incentive_id must be positive and country_code two letters.")
        raw = ctx.client.raw
        request = raw.get_type("ApplyIncentiveRequest")
        request.customer_id = customer
        request.selected_incentive_id = incentive_id
        request.country_code = country

        def execute():
            response = _call(ctx, "IncentiveService", "apply_incentive", request)
            return proto.Message.to_dict(response, preserving_proto_field_name=True)

        return ctx.safety.propose(
            tool_name="apply_google_ads_incentive",
            customer_id=customer,
            description=f"Apply Google Ads incentive {incentive_id} to customer {customer}",
            payload={"selected_incentive_id": incentive_id, "country_code": country},
            execute=execute,
        )

    # ------------------------------------------------------------------
    # MultiPartyAuthReviewService — beta
    # ------------------------------------------------------------------
    @mcp.tool()
    def resolve_multi_party_auth_review(
        customer_id: str,
        multi_party_auth_review_resource_name: str,
        new_status: str,
    ) -> dict:
        """Propose resolving one Multi-Party Authorization review (beta).

        new_status must be APPROVED, REJECTED, or REVOKED.
        """
        customer = ctx.client.assert_customer_allowed(customer_id)
        resource = ctx.client.assert_resource_name_customer(
            customer,
            multi_party_auth_review_resource_name,
            field_name="multi_party_auth_review_resource_name",
        )
        status = str(new_status).strip().upper()
        if status not in {"APPROVED", "REJECTED", "REVOKED"}:
            raise ValueError("new_status must be APPROVED, REJECTED, or REVOKED.")
        raw = ctx.client.raw
        operation = raw.get_type("ResolveMultiPartyAuthReviewOperation")
        operation.multi_party_auth_review = resource
        operation.new_status = getattr(raw.enums.MultiPartyAuthReviewStatusEnum, status)
        request = raw.get_type("ResolveMultiPartyAuthReviewRequest")
        if hasattr(request, "customer_id"):
            request.customer_id = customer
        request.operations.append(operation)
        if hasattr(request, "partial_failure"):
            request.partial_failure = False

        def execute():
            response = _call(
                ctx,
                "MultiPartyAuthReviewService",
                "resolve_multi_party_auth_review",
                request,
            )
            return proto.Message.to_dict(response, preserving_proto_field_name=True)

        return ctx.safety.propose(
            tool_name="resolve_multi_party_auth_review",
            customer_id=customer,
            description=f"Resolve MPA review {resource} -> {status}",
            payload={"multi_party_auth_review_resource_name": resource, "status": status},
            execute=execute,
        )

    # ------------------------------------------------------------------
    # Allowlisted read-only insight services. Request dictionaries use the exact
    # documented v25 protobuf JSON fields, preserving complete method coverage.
    # ------------------------------------------------------------------
    @mcp.tool()
    def generate_audience_composition_insights(customer_id: str, request: dict) -> dict:
        return _proto_call(ctx, service_name="AudienceInsightsService", method_name="generate_audience_composition_insights", request_type="GenerateAudienceCompositionInsightsRequest", request_payload=request, customer_id=customer_id)

    @mcp.tool()
    def generate_audience_definition(customer_id: str, request: dict) -> dict:
        return _proto_call(ctx, service_name="AudienceInsightsService", method_name="generate_audience_definition", request_type="GenerateAudienceDefinitionRequest", request_payload=request, customer_id=customer_id)

    @mcp.tool()
    def generate_audience_overlap_insights(customer_id: str, request: dict) -> dict:
        return _proto_call(ctx, service_name="AudienceInsightsService", method_name="generate_audience_overlap_insights", request_type="GenerateAudienceOverlapInsightsRequest", request_payload=request, customer_id=customer_id)

    @mcp.tool()
    def generate_insights_finder_report(customer_id: str, request: dict) -> dict:
        return _proto_call(ctx, service_name="AudienceInsightsService", method_name="generate_insights_finder_report", request_type="GenerateInsightsFinderReportRequest", request_payload=request, customer_id=customer_id)

    @mcp.tool()
    def generate_suggested_targeting_insights(customer_id: str, request: dict) -> dict:
        return _proto_call(ctx, service_name="AudienceInsightsService", method_name="generate_suggested_targeting_insights", request_type="GenerateSuggestedTargetingInsightsRequest", request_payload=request, customer_id=customer_id)

    @mcp.tool()
    def generate_targeting_suggestion_metrics(customer_id: str, request: dict) -> dict:
        return _proto_call(ctx, service_name="AudienceInsightsService", method_name="generate_targeting_suggestion_metrics", request_type="GenerateTargetingSuggestionMetricsRequest", request_payload=request, customer_id=customer_id)

    @mcp.tool()
    def list_audience_insights_attributes(customer_id: str, request: dict) -> dict:
        return _proto_call(ctx, service_name="AudienceInsightsService", method_name="list_audience_insights_attributes", request_type="ListAudienceInsightsAttributesRequest", request_payload=request, customer_id=customer_id)

    @mcp.tool()
    def list_insights_eligible_dates(customer_id: str, request: dict | None = None) -> dict:
        return _proto_call(ctx, service_name="AudienceInsightsService", method_name="list_insights_eligible_dates", request_type="ListInsightsEligibleDatesRequest", request_payload=request, customer_id=customer_id)

    @mcp.tool()
    def generate_benchmarks_metrics(customer_id: str, request: dict) -> dict:
        return _proto_call(ctx, service_name="BenchmarksService", method_name="generate_benchmarks_metrics", request_type="GenerateBenchmarksMetricsRequest", request_payload=request, customer_id=customer_id)

    @mcp.tool()
    def list_benchmarks_available_dates(customer_id: str, request: dict | None = None) -> dict:
        return _proto_call(ctx, service_name="BenchmarksService", method_name="list_benchmarks_available_dates", request_type="ListBenchmarksAvailableDatesRequest", request_payload=request, customer_id=customer_id)

    @mcp.tool()
    def list_benchmarks_locations(customer_id: str, request: dict | None = None) -> dict:
        return _proto_call(ctx, service_name="BenchmarksService", method_name="list_benchmarks_locations", request_type="ListBenchmarksLocationsRequest", request_payload=request, customer_id=customer_id)

    @mcp.tool()
    def list_benchmarks_products(customer_id: str, request: dict | None = None) -> dict:
        return _proto_call(ctx, service_name="BenchmarksService", method_name="list_benchmarks_products", request_type="ListBenchmarksProductsRequest", request_payload=request, customer_id=customer_id)

    @mcp.tool()
    def list_benchmarks_sources(customer_id: str, request: dict | None = None) -> dict:
        return _proto_call(ctx, service_name="BenchmarksService", method_name="list_benchmarks_sources", request_type="ListBenchmarksSourcesRequest", request_payload=request, customer_id=customer_id)

    @mcp.tool()
    def generate_creator_insights(customer_id: str, request: dict) -> dict:
        return _proto_call(ctx, service_name="ContentCreatorInsightsService", method_name="generate_creator_insights", request_type="GenerateCreatorInsightsRequest", request_payload=request, customer_id=customer_id)

    @mcp.tool()
    def generate_trending_creator_insights(customer_id: str, request: dict) -> dict:
        return _proto_call(ctx, service_name="ContentCreatorInsightsService", method_name="generate_trending_insights", request_type="GenerateTrendingInsightsRequest", request_payload=request, customer_id=customer_id)
