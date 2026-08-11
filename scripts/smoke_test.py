#!/usr/bin/env python3
"""Smoke test: import the server and every tool module without live credentials.

Run from the repo root with the virtualenv active:
    .venv/bin/python scripts/smoke_test.py

Exits with 0 if the MCP server builds and every module registers cleanly.
"""

from __future__ import annotations

import sys


def _build_server():
    from google_ads_mcp.server import build_server

    return build_server()


def _check_modules():
    from google_ads_mcp.tools import ALL_MODULES
    from google_ads_mcp.context import AppContext
    from google_ads_mcp.safety import SafetyLayer

    class _FakeClient:
        @property
        def raw(self):
            return self

        def get_service(self, name: str):
            return self

        def get_type(self, name: str):
            return self

        @property
        def enums(self):
            return self

    class _FakeMcp:
        def tool(self):
            def decorator(fn):
                return fn

            return decorator

    class _FakeAuditLog:
        def record(self, *args, **kwargs):
            pass

    ctx = AppContext(
        settings=None,
        client=_FakeClient(),
        safety=SafetyLayer(auto_approve=False, ttl_minutes=30, audit_log=_FakeAuditLog()),
        audit=_FakeAuditLog(),
    )
    mcp = _FakeMcp()

    failures = []
    for module in ALL_MODULES:
        try:
            module.register(mcp, ctx)
        except Exception as exc:  # noqa: BLE001
            failures.append(f"{module.__name__}: {exc}")

    return failures


def main() -> int:
    print("Building MCP server...")
    server = _build_server()
    print(f"  OK: {server}")

    print("Checking tool module registration...")
    failures = _check_modules()
    if failures:
        print("  FAILED:")
        for failure in failures:
            print(f"    - {failure}")
        return 1

    print("  OK: all tool modules registered cleanly.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
