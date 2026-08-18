"""Human-in-the-loop layer for every mutating tool.

Write tools never call the Google Ads API directly. Instead they call
``SafetyLayer.propose(...)`` with a callable that performs the actual mutate.
The change is executed only when ``confirm_pending_action`` is called, unless
auto-approve has explicitly been enabled.
"""

from __future__ import annotations

import logging
import time
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from .audit import AuditLog
from .errors import GoogleAdsMcpError

logger = logging.getLogger(__name__)


@dataclass
class PendingAction:
    action_id: str
    tool_name: str
    customer_id: str
    description: str
    payload: dict[str, Any]
    execute: Callable[[], Any]
    created_at: float = field(default_factory=time.time)
    attempts: int = 0


class SafetyLayer:
    def __init__(self, *, auto_approve: bool, ttl_minutes: int, audit_log: AuditLog):
        self._auto_approve = auto_approve
        self._ttl_seconds = ttl_minutes * 60
        self._audit = audit_log
        self._pending: dict[str, PendingAction] = {}

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
        action_id = uuid.uuid4().hex[:12]

        if self._auto_approve:
            result = self._run(
                action_id, tool_name, customer_id, description, payload, execute
            )
            return {
                "status": "executed",
                "auto_approved": True,
                "action_id": action_id,
                "description": description,
                "result": result,
            }

        self._pending[action_id] = PendingAction(
            action_id=action_id,
            tool_name=tool_name,
            customer_id=customer_id,
            description=description,
            payload=payload,
            execute=execute,
        )
        return {
            "status": "pending_confirmation",
            "pending_action_id": action_id,
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

        action.attempts += 1
        try:
            result = self._run(
                action.action_id,
                action.tool_name,
                action.customer_id,
                action.description,
                action.payload,
                action.execute,
            )
        except Exception:
            # Keep the action pending so transient Google/network failures can be
            # retried with the same audit/action id instead of silently losing it.
            raise
        else:
            self._pending.pop(action_id, None)

        return {
            "status": "executed",
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
                "description": a.description,
                "age_seconds": round(time.time() - a.created_at),
                "attempts": a.attempts,
            }
            for a in self._pending.values()
        ]

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


def _safe_result(result: Any) -> Any:
    """Best-effort conversion of a Google Ads API response into JSON-able data."""
    if result is None:
        return None
    if isinstance(result, (str, int, float, bool, list, dict)):
        return result
    try:
        results = getattr(result, "results", None)
        if results is not None:
            resource_names = []
            for item in results:
                resource_name = getattr(item, "resource_name", None)
                if resource_name:
                    resource_names.append(resource_name)
                    continue
                # GoogleAdsService.Mutate wraps resource-specific results.
                for field_name in (
                    "campaign_result",
                    "campaign_budget_result",
                    "ad_group_result",
                    "ad_group_ad_result",
                    "ad_result",
                    "asset_result",
                    "campaign_asset_result",
                    "ad_group_asset_result",
                    "asset_group_result",
                    "asset_group_asset_result",
                ):
                    nested = getattr(item, field_name, None)
                    nested_name = getattr(nested, "resource_name", None) if nested else None
                    if nested_name:
                        resource_names.append(nested_name)
                        break
            return {"resource_names": resource_names}
    except Exception:
        logger.debug("Could not convert result to JSON-safe form", exc_info=True)
    return str(result)
