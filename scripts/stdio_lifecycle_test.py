#!/usr/bin/env python3
"""Real stdio lifecycle check: spawn the server, initialize, list tools, shut down.

The smoke test only builds the server object, so it cannot notice start-up
failures (for example FastMCP's update check failing behind a proxy). This script
starts ``python -m google_ads_mcp.server`` as a child process over stdio, performs
the MCP handshake with the FastMCP client and verifies the tool catalogue.

It is offline: read-only mode, a temporary audit DB, and no Google credentials.

Usage:
    .venv/bin/python scripts/stdio_lifecycle_test.py
"""

from __future__ import annotations

import asyncio
import os
import sys
import tempfile

REQUIRED_TOOLS = {
    "confirm_pending_action",
    "cancel_pending_action",
    "list_pending_actions",
    "run_gaql_query",
    "get_merchant_center_configuration",
}
MIN_TOOLS = 400


async def _run(env: dict[str, str]) -> int:
    from fastmcp import Client
    from fastmcp.client.transports import StdioTransport

    transport = StdioTransport(
        command=sys.executable, args=["-m", "google_ads_mcp.server"], env=env
    )
    async with Client(transport) as client:
        tools = await client.list_tools()
    names = [tool.name for tool in tools]
    unique = set(names)
    assert len(names) == len(unique), "tools/list returned duplicate tool names"
    missing = REQUIRED_TOOLS - unique
    assert not missing, f"missing required tools: {sorted(missing)}"
    assert len(unique) >= MIN_TOOLS, f"only {len(unique)} tools listed"
    print(f"stdio lifecycle OK: {len(unique)} unique tools listed")
    return 0


def main() -> int:
    with tempfile.TemporaryDirectory() as temp_dir:
        env = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith("GOOGLE_ADS_")
            and not key.startswith("GOOGLE_MERCHANT_")
        }
        env.update(
            {
                "GOOGLE_ADS_MCP_AUDIT_DB": os.path.join(temp_dir, "lifecycle-audit.db"),
                "GOOGLE_ADS_MCP_READ_ONLY": "true",
                "GOOGLE_ADS_MCP_ENV_FILE": os.path.join(temp_dir, "absent.env"),
            }
        )
        return asyncio.run(asyncio.wait_for(_run(env), timeout=120))


if __name__ == "__main__":
    raise SystemExit(main())
