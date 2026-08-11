"""Centralized logging setup for the MCP server.

Uses a simple, readable format suitable for both stdio (Claude Desktop)
and HTTP transports. Log level is controlled by the GOOGLE_ADS_MCP_LOG_LEVEL
environment variable and defaults to WARNING so the stdio JSON-RPC stream
is not polluted under normal operation.
"""

from __future__ import annotations

import logging
import os
import sys


def setup_logging() -> None:
    """Configure the root logger for the google_ads_mcp package."""
    level_name = os.environ.get("GOOGLE_ADS_MCP_LOG_LEVEL", "WARNING").upper()
    level = getattr(logging, level_name, logging.WARNING)

    handler = logging.StreamHandler(sys.stderr)
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )

    root = logging.getLogger("google_ads_mcp")
    root.setLevel(level)
    root.handlers = []
    root.addHandler(handler)
