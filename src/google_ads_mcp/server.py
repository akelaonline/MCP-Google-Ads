"""Entry point: builds the FastMCP server, registers every tool module,
and starts the requested transport.

    python -m google_ads_mcp.server                    # stdio (default)
    python -m google_ads_mcp.server --transport http --port 8080
"""

from __future__ import annotations

import argparse

from fastmcp import FastMCP

from .context import build_context

MCP_INSTRUCTIONS = """
Google Ads MCP — full read/write account management.

Safety model: every write tool (create_*, update_*, remove_*, set_*, add_*,
upload_*) does NOT touch the account immediately. It returns a preview and a
pending_action_id. Call confirm_pending_action(action_id) to actually execute
it, or cancel_pending_action(action_id) to discard it. Always show the user
the preview before confirming unless they've explicitly asked you to proceed
without asking each time.

For reporting, prefer the pre-built tools (get_campaign_performance, etc.)
and fall back to run_gaql_query for anything custom.
"""


def build_server() -> FastMCP:
    ctx = build_context()
    mcp = FastMCP(name="google-ads-mcp", instructions=MCP_INSTRUCTIONS)

    from .tools import ALL_MODULES

    for module in ALL_MODULES:
        module.register(mcp, ctx)

    _register_safety_tools(mcp, ctx)
    return mcp


def _register_safety_tools(mcp: FastMCP, ctx) -> None:
    @mcp.tool()
    def list_pending_actions() -> dict:
        """List all proposed-but-not-yet-confirmed changes, across every tool."""
        return {"pending_actions": ctx.safety.list_pending()}

    @mcp.tool()
    def confirm_pending_action(action_id: str) -> dict:
        """Execute a previously proposed change against the live Google Ads account."""
        return ctx.safety.confirm(action_id)

    @mcp.tool()
    def cancel_pending_action(action_id: str) -> dict:
        """Discard a previously proposed change without executing it."""
        return ctx.safety.cancel(action_id)

    @mcp.tool()
    def get_recent_audit_log(limit: int = 20) -> dict:
        """Show the most recent confirmed/auto-approved mutations from the audit trail."""
        return {"entries": ctx.audit.recent(limit)}


def main() -> None:
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
        server.run(transport="http", port=port)
    else:
        server.run()


if __name__ == "__main__":
    main()
