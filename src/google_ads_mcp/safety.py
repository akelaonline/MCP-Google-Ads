"""Human-in-the-loop safety policy for every mutating tool.

Write tools call ``SafetyLayer.propose(...)`` with a callable that performs the
actual Google Ads mutation. Production context passes explicit high-risk policy
flags; the optional ``None`` defaults preserve compatibility for older internal
callers that used ``SafetyLayer(auto_approve=True)`` as an execution harness.
"""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from .audit import AuditLog
from .errors import GoogleAdsMcpError
from .helpers import normalize_customer_id

logger = logging.getLogger(__name__)


class RiskLevel(str, Enum):
    STANDARD = "standard"
    SPEND = "spend"
    DESTRUCTIVE = "destructive"
    SENSITIVE = "sensitive"


_SENSITIVE_TOOLS = {
    # First-party/customer data.
    "upload_customer_match_members",
    "upload_customer_match_members_data_manager",
    "create_data_manager_customer_match_list",
    "update_data_manager_customer_match_list",
    "upload_enhanced_conversion",
    "upload_offline_conversion",
    "retract_conversion",
    "restate_conversion_value",
    "assign_user_list_customer_type",
    # Conversion measurement schema.
    "create_conversion_custom_variable",
    "update_conversion_custom_variable",
    # Local Services customer interaction / lead-quality signals.
    "append_local_services_lead_conversation",
    "provide_local_services_lead_feedback",
    # Account access and hierarchy.
    "accept_manager_link",
    "invite_manager_link",
    "create_customer_client",
    "invite_account_user",
    "update_user_access_role",
    "submit_batch_job",
    # Billing identity.
    "create_billing_setup",
    # External product / creator / analytics connections.
    "create_product_link",
    "accept_product_link_invitation",
    "request_youtube_video_link",
    "accept_youtube_video_link",
    "create_third_party_app_analytics_link",
    "regenerate_third_party_app_analytics_shareable_id",
    # Persistent automated account policy.
    "set_recommendation_subscription",
    # YouTube publishing through the Ads identity.
    "upload_youtube_video",
    "update_youtube_video_upload",
    # One-way PMax brand migration / identity controls.
    "enable_pmax_brand_guidelines",
}

_DESTRUCTIVE_TOOLS = {
    "end_experiment",
    # Audience data/list destruction.
    "delete_data_manager_customer_match_list",
    "remove_customer_match_members_data_manager",
    "remove_all_customer_match_members_data_manager",
    # MCC/access destruction.
    "decline_manager_link",
    "unlink_manager",
    "cancel_manager_link_invitation",
    "move_manager_link",
    "revoke_user_access_invitation",
    # Billing/account-budget destruction.
    "cancel_pending_billing_setup",
    "end_account_budget",
    "remove_future_account_budget",
    "cancel_pending_account_budget_proposal",
    # Product/creator invitation destruction.
    "reject_product_link_invitation",
    "revoke_product_link_invitation",
    "reject_youtube_video_link",
    "revoke_youtube_video_link_request",
}

_SPEND_TOOLS = {
    "create_campaign_budget",
    "update_campaign_budget",
    "set_manual_cpc",
    "set_maximize_clicks",
    "set_maximize_conversions",
    "set_maximize_conversion_value",
    "set_target_cpa",
    "set_target_roas",
    "set_target_impression_share",
    "attach_shared_bidding_strategy",
    "apply_recommendation",
    "schedule_experiment",
    "promote_experiment",
    "graduate_experiment",
    "promote_campaign_draft",
    "set_device_bid_modifier",
    "set_campaign_call_bid_modifier",
    "create_ad_group_device_bid_modifier",
    "update_ad_group_bid_modifier",
    "add_ad_schedule",
    "create_seasonality_adjustment",
    "create_data_exclusion",
    "create_account_budget",
    "update_account_budget",
    "create_smart_campaign",
    # Assets and asset sets can alter serving when attached to live scope.
    "attach_asset_to_customer",
    "set_customer_asset_status",
    "attach_asset_to_ad_group",
    "set_ad_group_asset_status",
    "attach_asset_to_asset_set",
    "attach_asset_set_to_customer",
    "attach_asset_set_to_campaign",
    "attach_asset_set_to_ad_group",
    # Existing audience resources can be referenced by active targeting.
    "update_custom_audience",
    "update_custom_interest",
    "update_audience_metadata",
    # Conversion and lifecycle goals can materially change Smart Bidding behavior.
    "set_customer_conversion_goal_biddable",
    "set_campaign_conversion_goal_biddable",
    "create_custom_conversion_goal",
    "update_custom_conversion_goal",
    "set_conversion_goal_campaign_config",
    "set_lifecycle_goal",
    "attach_lifecycle_goal_to_campaign",
    "create_conversion_value_rule_set",
    "update_conversion_value_rule_set_rules",
}

_SPEND_PAYLOAD_KEYS = {
    "daily_amount",
    "new_daily_amount",
    "daily_budget",
    "cpc_bid",
    "new_cpc_bid",
    "bid_modifier",
    "target_cpc",
    "target_cpa",
    "target_roas",
    "max_cpc_bid_ceiling",
    "spending_limit",
}


@dataclass
class PendingAction:
    action_id: str
    tool_name: str
    customer_id: str
    description: str
    payload: dict[str, Any]
    execute: Callable[[], Any]
    risk_level: RiskLevel = RiskLevel.STANDARD
    created_at: float = field(default_factory=time.time)
    attempts: int = 0


class SafetyLayer:
    def __init__(
        self,
        *,
        auto_approve: bool,
        ttl_minutes: int,
        audit_log: AuditLog,
        auto_approve_spend: bool | None = None,
        auto_approve_destructive: bool | None = None,
        auto_approve_sensitive: bool | None = None,
        allowed_customer_ids: Iterable[str] | None = None,
        require_customer_allowlist: bool = False,
    ):
        self._auto_approve = auto_approve
        self._auto_approve_spend = (
            auto_approve if auto_approve_spend is None else auto_approve_spend
        )
        self._auto_approve_destructive = (
            auto_approve
            if auto_approve_destructive is None
            else auto_approve_destructive
        )
        self._auto_approve_sensitive = (
            auto_approve if auto_approve_sensitive is None else auto_approve_sensitive
        )
        self._ttl_seconds = ttl_minutes * 60
        self._audit = audit_log
        self._pending: dict[str, PendingAction] = {}
        self._allowed_customer_ids = frozenset(
            normalize_customer_id(customer_id)
            for customer_id in (allowed_customer_ids or ())
            if str(customer_id).strip()
        )
        self._require_customer_allowlist = require_customer_allowlist
        if self._require_customer_allowlist and not self._allowed_customer_ids:
            raise GoogleAdsMcpError(
                "GOOGLE_ADS_MCP_REQUIRE_CUSTOMER_ALLOWLIST is enabled but no "
                "GOOGLE_ADS_MCP_ALLOWED_CUSTOMER_IDS were configured."
            )

    def propose(
        self,
        *,
        tool_name: str,
        customer_id: str,
        description: str,
        payload: dict[str, Any],
        execute: Callable[[], Any],
    ) -> dict[str, Any]:
        self._evict_expired()
        normalized_customer_id = self._assert_customer_allowed(customer_id)
        action_id = uuid.uuid4().hex[:12]
        risk_level = classify_risk(tool_name, payload)

        if self._may_auto_approve(risk_level):
            result = self._run(
                action_id,
                tool_name,
                normalized_customer_id,
                description,
                payload,
                execute,
            )
            return {
                "status": "executed",
                "auto_approved": True,
                "risk_level": risk_level.value,
                "action_id": action_id,
                "description": description,
                "result": result,
            }

        self._pending[action_id] = PendingAction(
            action_id=action_id,
            tool_name=tool_name,
            customer_id=normalized_customer_id,
            description=description,
            payload=payload,
            execute=execute,
            risk_level=risk_level,
        )
        return {
            "status": "pending_confirmation",
            "pending_action_id": action_id,
            "risk_level": risk_level.value,
            "confirmation_reason": _confirmation_reason(
                risk_level, self._auto_approve
            ),
            "description": description,
            "expires_in_minutes": self._ttl_seconds // 60,
            "next_step": (
                f"Nothing has been changed yet. Call confirm_pending_action("
                f"action_id='{action_id}') to execute this, or "
                f"cancel_pending_action(action_id='{action_id}') to discard it."
            ),
        }

    def confirm(self, action_id: str) -> dict[str, Any]:
        self._evict_expired()
        action = self._pending.get(action_id)
        if action is None:
            raise GoogleAdsMcpError(
                f"No pending action with id '{action_id}' (it may have expired "
                "or already been confirmed/cancelled)."
            )

        self._assert_customer_allowed(action.customer_id)
        action.attempts += 1
        result = self._run(
            action.action_id,
            action.tool_name,
            action.customer_id,
            action.description,
            action.payload,
            action.execute,
        )
        self._pending.pop(action_id, None)

        return {
            "status": "executed",
            "risk_level": action.risk_level.value,
            "action_id": action.action_id,
            "description": action.description,
            "result": result,
        }

    def cancel(self, action_id: str) -> dict[str, Any]:
        self._evict_expired()
        action = self._pending.pop(action_id, None)
        if action is None:
            raise GoogleAdsMcpError(f"No pending action with id '{action_id}'.")
        return {
            "status": "cancelled",
            "risk_level": action.risk_level.value,
            "action_id": action.action_id,
            "description": action.description,
        }

    def list_pending(self) -> list[dict[str, Any]]:
        self._evict_expired()
        return [
            {
                "pending_action_id": a.action_id,
                "tool_name": a.tool_name,
                "customer_id": a.customer_id,
                "risk_level": a.risk_level.value,
                "description": a.description,
                "age_seconds": round(time.time() - a.created_at),
                "attempts": a.attempts,
            }
            for a in self._pending.values()
        ]

    def _assert_customer_allowed(self, customer_id: str) -> str:
        normalized = normalize_customer_id(customer_id)
        if self._require_customer_allowlist and not self._allowed_customer_ids:
            raise GoogleAdsMcpError("Customer allowlist is required but empty.")
        if self._allowed_customer_ids and normalized not in self._allowed_customer_ids:
            raise GoogleAdsMcpError(
                f"Customer {normalized} is outside GOOGLE_ADS_MCP_ALLOWED_CUSTOMER_IDS. "
                "The operation was blocked before any Google Ads mutation."
            )
        return normalized

    def _may_auto_approve(self, risk_level: RiskLevel) -> bool:
        if not self._auto_approve:
            return False
        if risk_level is RiskLevel.STANDARD:
            return True
        if risk_level is RiskLevel.SPEND:
            return self._auto_approve_spend
        if risk_level is RiskLevel.DESTRUCTIVE:
            return self._auto_approve_destructive
        if risk_level is RiskLevel.SENSITIVE:
            return self._auto_approve_sensitive
        return False

    def _run(
        self,
        action_id: str,
        tool_name: str,
        customer_id: str,
        description: str,
        payload: dict[str, Any],
        execute: Callable[[], Any],
    ) -> Any:
        try:
            result = execute()
            safe_result = _safe_result(result)
            self._audit.record(
                action_id=action_id,
                tool_name=tool_name,
                customer_id=customer_id,
                description=description,
                payload=payload,
                result=safe_result,
                status="success",
            )
            return safe_result
        except Exception as ex:
            self._audit.record(
                action_id=action_id,
                tool_name=tool_name,
                customer_id=customer_id,
                description=description,
                payload=payload,
                result=str(ex),
                status="error",
            )
            raise

    def _evict_expired(self) -> None:
        now = time.time()
        expired = [
            aid
            for aid, action in self._pending.items()
            if now - action.created_at > self._ttl_seconds
        ]
        for aid in expired:
            del self._pending[aid]


def classify_risk(tool_name: str, payload: dict[str, Any]) -> RiskLevel:
    """Conservative central risk classification for mutating MCP tools."""
    normalized_tool = tool_name.strip().lower()
    status = str(payload.get("status", "")).upper()

    # Account-link status changes are identity/integration changes. Terminal states
    # are destructive; activation remains sensitive rather than generic spend-risk.
    if normalized_tool == "set_third_party_app_analytics_link_status":
        if status in {"REMOVED", "REVOKED", "REJECTED"}:
            return RiskLevel.DESTRUCTIVE
        return RiskLevel.SENSITIVE

    if normalized_tool in _SENSITIVE_TOOLS:
        return RiskLevel.SENSITIVE
    if normalized_tool.startswith("remove_") or normalized_tool in _DESTRUCTIVE_TOOLS:
        return RiskLevel.DESTRUCTIVE
    if status == "REMOVED":
        return RiskLevel.DESTRUCTIVE

    if status == "ENABLED" or normalized_tool in _SPEND_TOOLS:
        return RiskLevel.SPEND
    for key in _SPEND_PAYLOAD_KEYS:
        if key in payload and payload.get(key) is not None:
            return RiskLevel.SPEND

    return RiskLevel.STANDARD


def _confirmation_reason(risk_level: RiskLevel, global_auto_approve: bool) -> str:
    if not global_auto_approve:
        return "Global auto-approve is disabled."
    if risk_level is RiskLevel.SPEND:
        return "Spend-changing action requires separate auto-approve opt-in."
    if risk_level is RiskLevel.DESTRUCTIVE:
        return "Destructive action requires separate auto-approve opt-in."
    if risk_level is RiskLevel.SENSITIVE:
        return "Sensitive-data/account-access action requires separate auto-approve opt-in."
    return "Confirmation required by policy."


def _safe_result(result: Any) -> Any:
    """Best-effort conversion of Google Ads mutate responses into JSON data."""
    if result is None:
        return None
    if isinstance(result, (str, int, float, bool, list, dict)):
        return result

    try:
        results = getattr(result, "results", None)
        if results is not None:
            return {
                "resource_names": [
                    resource_name
                    for item in results
                    if (resource_name := getattr(item, "resource_name", None))
                ]
            }

        single_result = getattr(result, "result", None)
        if single_result is not None:
            resource_name = getattr(single_result, "resource_name", None)
            safe_single: dict[str, Any] = {}
            if resource_name:
                safe_single["resource_name"] = resource_name
            review = getattr(single_result, "multi_party_auth_review", None)
            if review:
                safe_single["multi_party_auth_review"] = str(review)
            return safe_single or str(single_result)

        responses = getattr(result, "mutate_operation_responses", None)
        if responses is not None:
            resource_names: list[str] = []
            operation_results: list[dict[str, Any]] = []
            for response in responses:
                response_pb = getattr(response, "_pb", None)
                field_name = (
                    response_pb.WhichOneof("response") if response_pb is not None else None
                )
                if not field_name and response_pb is not None:
                    for oneof_name in ("operation", "result"):
                        try:
                            field_name = response_pb.WhichOneof(oneof_name)
                        except ValueError:
                            continue
                        if field_name:
                            break
                if not field_name:
                    operation_results.append({"type": "unknown"})
                    continue
                nested = getattr(response, field_name, None)
                resource_name = getattr(nested, "resource_name", None)
                item = {"type": field_name}
                if resource_name:
                    item["resource_name"] = resource_name
                    resource_names.append(resource_name)
                operation_results.append(item)
            return {
                "resource_names": resource_names,
                "operations": operation_results,
            }
    except Exception:
        logger.debug("Could not convert result to JSON-safe form", exc_info=True)

    return str(result)
