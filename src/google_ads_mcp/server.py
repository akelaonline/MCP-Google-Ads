"""Entry point: build the FastMCP server and start the requested transport."""

from __future__ import annotations

import argparse
import os
import threading

from fastmcp import FastMCP

from .context import build_context
from .invocation import install_tool_tracking
from .logging_config import setup_logging

MCP_INSTRUCTIONS = """
Google Ads MCP — full read/write account management.

Safety model: every write tool does NOT touch the account immediately. It
returns a preview and a pending_action_id. Call confirm_pending_action(action_id)
to execute it, or cancel_pending_action(action_id) to discard it. Always show
the user the preview before confirming unless they've explicitly asked you to
proceed without asking each time.

Pending confirmations are persisted in SQLite. The original MCP arguments are
encrypted at rest, so a pending action can still be confirmed after a normal
server/process restart using the same pending_action_id.

For reporting, prefer the pre-built tools (get_campaign_performance, etc.) and
fall back to run_gaql_query for anything custom.
"""

# FastMCP may dispatch synchronous tool calls concurrently. Confirm and cancel
# are state transitions over the same pending-action collection, so serialize
# them within one server process. This prevents two simultaneous confirms from
# executing the same mutation before the first call removes the pending action,
# and prevents cancel racing an in-flight confirmation.
_PENDING_ACTION_CONTROL_LOCK = threading.RLock()


def build_server() -> FastMCP:
    ctx = build_context()
    mcp = FastMCP(name="google-ads-mcp", instructions=MCP_INSTRUCTIONS)

    # Must be installed before any @mcp.tool() registrations. This preserves each
    # function's public signature while capturing original validated arguments for
    # restart-safe pending-action replay.
    install_tool_tracking(mcp)

    from .tools import ALL_MODULES

    for module in ALL_MODULES:
        module.register(mcp, ctx)

    _register_safety_tools(mcp, ctx)
    return mcp


def _register_safety_tools(mcp: FastMCP, ctx) -> None:
    @mcp.tool()
    def list_pending_actions() -> dict:
        """List all proposed-but-not-yet-confirmed changes, across every tool."""
        with _PENDING_ACTION_CONTROL_LOCK:
            return {"pending_actions": ctx.safety.list_pending()}

    @mcp.tool()
    def confirm_pending_action(action_id: str) -> dict:
        """Execute one pending action exactly once within this server process."""
        with _PENDING_ACTION_CONTROL_LOCK:
            return ctx.safety.confirm(action_id)

    @mcp.tool()
    def cancel_pending_action(action_id: str) -> dict:
        """Discard a pending action without racing an in-flight confirmation."""
        with _PENDING_ACTION_CONTROL_LOCK:
            return ctx.safety.cancel(action_id)

    @mcp.tool()
    def get_recent_audit_log(limit: int = 20) -> dict:
        """Show recent confirmed/auto-approved mutation attempts and payloads."""
        return {"entries": ctx.audit.recent(limit)}

    @mcp.tool()
    def get_audit_action(action_id: str) -> dict:
        """Show every audit attempt recorded for one action id."""
        return {"action_id": action_id, "entries": ctx.audit.by_action_id(action_id)}


def main() -> None:
    setup_logging()
    parser = argparse.ArgumentParser(description="Google Ads MCP server")
    parser.add_argument("--transport", choices=["stdio", "http"], default=None)
    parser.add_argument("--port", type=int, default=None)
    args = parser.parse_args()

    server = build_server()

    from .config import load_settings

    settings = load_settings()
    transport = args.transport or settings.transport
    port = args.port or settings.http_port

    if transport == "http":
        allow_insecure_http = os.environ.get(
            "GOOGLE_ADS_MCP_ALLOW_INSECURE_HTTP", "false"
        ).strip().lower() in {"1", "true", "yes", "on"}
        if not allow_insecure_http:
            raise SystemExit(
                "HTTP transport is disabled by default because this server exposes "
                "write and confirmation tools but has no built-in remote authentication. "
                "Use stdio, or explicitly set GOOGLE_ADS_MCP_ALLOW_INSECURE_HTTP=true "
                "only behind your own authenticated/restricted proxy."
            )
        server.run(transport="http", port=port)
    else:
        server.run()


if __name__ == "__main__":
    main()
