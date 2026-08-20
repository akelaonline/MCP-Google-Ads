"""Read-only safety proxy for deployments that must never mutate Google Ads."""

from __future__ import annotations

from typing import Any

from .errors import GoogleAdsMcpError


class ReadOnlySafetyProxy:
    """Block proposal/confirmation while preserving read-side safety inspection.

    This wraps the normal SafetyLayer rather than duplicating its policy. Turning
    read-only mode on also blocks confirmation of pending actions created before a
    restart/config change. Cancellation and pending/audit inspection remain
    available so operators can clean up safely.
    """

    def __init__(self, delegate: Any):
        self._delegate = delegate

    def propose(self, **kwargs):
        tool_name = str(kwargs.get("tool_name") or "mutation")
        raise GoogleAdsMcpError(
            f"Google Ads MCP is running in read-only mode; write tool {tool_name!r} "
            "was blocked before any Google Ads mutation. Set "
            "GOOGLE_ADS_MCP_READ_ONLY=false only on an instance that is allowed to write."
        )

    def confirm(self, action_id: str):
        raise GoogleAdsMcpError(
            f"Google Ads MCP is running in read-only mode; pending action "
            f"{action_id!r} cannot be confirmed. You may inspect or cancel it."
        )

    def cancel(self, action_id: str):
        return self._delegate.cancel(action_id)

    def list_pending(self):
        return self._delegate.list_pending()

    def __getattr__(self, name: str):
        return getattr(self._delegate, name)
