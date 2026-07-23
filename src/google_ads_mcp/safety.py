"""Human-in-the-loop layer for every mutating tool.

Write tools never call the Google Ads API directly. Instead they call
`SafetyLayer.propose(...)` with a callable that performs the actual mutate.
That returns a preview + `pending_action_id`. The change is only executed
when `confirm_pending_action` is called (or immediately, if
GOOGLE_ADS_MCP_AUTO_APPROVE=true).
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable

from .audit import AuditLog
from .errors import GoogleAdsMcpError


@dataclass
class PendingAction:
    action_id: str
    tool_name: str
    customer_id: str
    description: str
    payload: dict[str, Any]
    execute: Callable[[], Any]
    created_at: float = field(default_factory=time.time)


class SafetyLayer:
    def __init__(self, *, auto_approve: bool, ttl_minutes: int, audit_log: AuditLog):
        self._auto_approve = auto_approve
        self._ttl_seconds = ttl_minutes * 60
        self._audit = audit_log
        self._pending: dict[str, PendingAction] = {}

    # ---- called by write tools -------------------------------------------

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

        if self._auto_approve:
            result = self._run(tool_name, customer_id, description, payload, execute)
            return {
                "status": "executed",
                "auto_approved": True,
                "description": description,
                "result": result,
            }

        action_id = uuid.uuid4().hex[:12]
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

    # ---- exposed as MCP tools by server.py --------------------------------

    def confirm(self, action_id: str) -> dict[str, Any]:
        action = self._pending.pop(action_id, None)
        if action is None:
            raise GoogleAdsMcpError(
                f"No pending action with id '{action_id}' (it may have expired "
                "or already been confirmed/cancelled)."
            )
        result = self._run(
            action.tool_name, action.customer_id, action.description, action.payload, action.execute
        )
        return {"status": "executed", "description": action.description, "result": result}

    def cancel(self, action_id: str) -> dict[str, Any]:
        action = self._pending.pop(action_id, None)
        if action is None:
            raise GoogleAdsMcpError(f"No pending action with id '{action_id}'.")
        return {"status": "cancelled", "description": action.description}

    def list_pending(self) -> list[dict[str, Any]]:
        self._evict_expired()
        return [
            {
                "pending_action_id": a.action_id,
                "tool_name": a.tool_name,
                "customer_id": a.customer_id,
                "description": a.description,
                "age_seconds": round(time.time() - a.created_at),
            }
            for a in self._pending.values()
        ]

    # ---- internals ---------------------------------------------------------

    def _run(self, tool_name, customer_id, description, payload, execute) -> Any:
        try:
            result = execute()
            self._audit.record(
                action_id=uuid.uuid4().hex[:12],
                tool_name=tool_name,
                customer_id=customer_id,
                description=description,
                payload=payload,
                result=_safe_result(result),
                status="success",
            )
            return _safe_result(result)
        except Exception as ex:
            self._audit.record(
                action_id=uuid.uuid4().hex[:12],
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
            for aid, a in self._pending.items()
            if now - a.created_at > self._ttl_seconds
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
            return {"resource_names": [r.resource_name for r in results]}
    except Exception:
        pass
    return str(result)
