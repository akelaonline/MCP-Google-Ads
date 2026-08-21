#!/usr/bin/env python3
"""Offline smoke test for the installed Google Ads MCP package.

This intentionally avoids live Google Ads credentials and network calls. It uses a
temporary SQLite audit DB, forces read-only mode, imports every registered tool
module, builds the FastMCP server, verifies currency helpers, exercises recursive
MCC/customer isolation with protobuf Struct nesting, and verifies canonical public
tool ownership so legacy duplicate implementations cannot win by import order.

Run from the repo root with the virtualenv active:
    .venv/bin/python scripts/smoke_test.py
"""

from __future__ import annotations

import gc
import os
import sys
import tempfile


def _set_temp_runtime(temp_dir: str) -> dict[str, str | None]:
    keys = {
        "GOOGLE_ADS_MCP_AUDIT_DB": os.path.join(temp_dir, "smoke-audit.db"),
        "GOOGLE_ADS_MCP_READ_ONLY": "true",
        "GOOGLE_ADS_MCP_AUTO_APPROVE": "false",
        "GOOGLE_ADS_MCP_AUTO_APPROVE_SPEND": "false",
        "GOOGLE_ADS_MCP_AUTO_APPROVE_DESTRUCTIVE": "false",
        "GOOGLE_ADS_MCP_AUTO_APPROVE_SENSITIVE": "false",
        "GOOGLE_ADS_MCP_REQUIRE_CUSTOMER_ALLOWLIST": "false",
        "GOOGLE_ADS_MCP_ALLOWED_CUSTOMER_IDS": "",
    }
    previous: dict[str, str | None] = {}
    for key, value in keys.items():
        previous[key] = os.environ.get(key)
        os.environ[key] = value
    return previous


def _restore_runtime(previous: dict[str, str | None]) -> None:
    for key, value in previous.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


def _check_currency_helpers() -> None:
    from google_ads_mcp.client import from_micros, micros

    assert micros(25.50) == 25_500_000
    assert from_micros(25_500_000) == 25.5


def _check_recursive_customer_isolation() -> None:
    from google.protobuf import struct_pb2

    from google_ads_mcp.client import _assert_mutation_targets_customer
    from google_ads_mcp.errors import GoogleAdsMcpError

    same = struct_pb2.Struct()
    same.update(
        {
            "create": {
                "campaign": "customers/1234567890/campaigns/1",
                "nested": {
                    "asset": "customers/1234567890/assets/2",
                    "items": ["customers/1234567890/adGroups/3"],
                },
            }
        }
    )
    _assert_mutation_targets_customer("1234567890", [same])

    cross = struct_pb2.Struct()
    cross.update(
        {
            "create": {
                "campaign": "customers/1234567890/campaigns/1",
                "nested": {
                    "asset": "customers/9999999999/assets/2",
                    "items": ["customers/9999999999/adGroups/3"],
                },
            }
        }
    )
    try:
        _assert_mutation_targets_customer("1234567890", [cross])
    except GoogleAdsMcpError:
        return
    raise AssertionError("Cross-customer nested resource was not blocked")


def _check_tool_package_imports() -> int:
    from google_ads_mcp.tools import ALL_MODULES

    if not ALL_MODULES:
        raise AssertionError("ALL_MODULES is empty")
    missing = [module.__name__ for module in ALL_MODULES if not hasattr(module, "register")]
    if missing:
        raise AssertionError(f"Tool modules missing register(): {missing}")
    return len(ALL_MODULES)


def _check_canonical_tool_owners() -> None:
    from google_ads_mcp.invocation import (
        canonical_tool_modules,
        registered_tool_owners,
    )

    owners = registered_tool_owners()
    expected = canonical_tool_modules()
    missing = sorted(name for name in expected if name not in owners)
    wrong = {
        name: {"expected": module, "actual": owners.get(name)}
        for name, module in expected.items()
        if owners.get(name) != module
    }
    if missing:
        raise AssertionError(f"Canonical tools were not registered: {missing}")
    if wrong:
        raise AssertionError(f"Canonical tool owner mismatch: {wrong}")


def _build_server_offline() -> str:
    from google_ads_mcp.server import build_server

    server = build_server()
    _check_canonical_tool_owners()
    rendered = repr(server)
    del server
    gc.collect()
    return rendered


def main() -> int:
    from google_ads_mcp import __version__

    print(f"Google Ads MCP version: {__version__}")

    try:
        print("Checking currency helpers...")
        _check_currency_helpers()
        print("  OK")

        print("Checking recursive MCC/customer isolation...")
        _check_recursive_customer_isolation()
        print("  OK")

        print("Importing registered tool modules...")
        module_count = _check_tool_package_imports()
        print(f"  OK: {module_count} modules")

        with tempfile.TemporaryDirectory(prefix="google-ads-mcp-smoke-") as temp_dir:
            previous = _set_temp_runtime(temp_dir)
            try:
                print("Building FastMCP server in isolated read-only runtime...")
                server_repr = _build_server_offline()
                print(f"  OK: {server_repr}")
                print("  OK: canonical tool owners verified")
            finally:
                _restore_runtime(previous)

    except Exception as exc:  # noqa: BLE001
        print(f"FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1

    print("SMOKE OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
