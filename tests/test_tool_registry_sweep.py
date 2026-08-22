"""End-to-end tool-registry sweep against the real assembled server.

Regression guard for silent duplicate-tool registration: builds the real
FastMCP server exactly like production (all ~55 modules, tracking installed),
then verifies that every canonical tool is owned by its declared module and
that no tool name is defined by an undeclared module anywhere in the tree.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from google_ads_mcp.invocation import (
    _TOOL_OWNERS,
    _candidate_should_register,
    canonical_tool_modules,
    legacy_tool_modules,
    registered_tool_owners,
)
from google_ads_mcp.server import build_server

_SRC = Path(__file__).resolve().parents[1] / "src" / "google_ads_mcp" / "tools"

_TOOL_DEF = re.compile(r"^\s*@mcp\.tool\(\)\s*\n\s*def ([a-zA-Z_][a-zA-Z0-9_]*)\(")


def _module_tool_definitions() -> dict[str, list[str]]:
    definitions: dict[str, list[str]] = {}
    for path in _SRC.glob("*.py"):
        source = path.read_text()
        for match in _TOOL_DEF.finditer(source):
            definitions.setdefault(match.group(1), []).append(
                f"google_ads_mcp.tools.{path.stem}"
            )
    return definitions


def test_real_server_registers_every_canonical_tool_with_its_owner():
    build_server()
    owners = registered_tool_owners()
    for tool_name, canonical_module in canonical_tool_modules().items():
        assert owners.get(tool_name) == canonical_module, (
            f"{tool_name} must be owned by {canonical_module}, got "
            f"{owners.get(tool_name)}"
        )


def test_no_undeclared_duplicate_tool_names_anywhere_in_the_tree():
    build_server()
    canonical = canonical_tool_modules()
    legacy = legacy_tool_modules()
    unexpected: list[str] = []
    for tool_name, modules in _module_tool_definitions().items():
        unique = set(modules)
        if len(unique) <= 1:
            continue
        canonical_module = canonical.get(tool_name)
        if canonical_module is None:
            unexpected.append(f"{tool_name} defined by {sorted(unique)} without owner")
            continue
        allowed = {canonical_module} | set(legacy.get(tool_name, frozenset()))
        undeclared = unique - allowed
        if undeclared:
            unexpected.append(
                f"{tool_name}: undeclared modules {sorted(undeclared)} "
                f"(canonical={canonical_module}, allowed legacy={sorted(allowed - {canonical_module})})"
            )
    assert unexpected == [], "undeclared duplicate tool definitions:\n" + "\n".join(
        unexpected
    )


def test_undeclared_duplicate_raises_runtime_error():
    build_server()

    def fake_function() -> dict:  # pragma: no cover - never registered
        return {}

    fake_function.__module__ = "google_ads_mcp.tools.undeclared_module"
    with pytest.raises(RuntimeError, match="Unexpected duplicate MCP tool"):
        _candidate_should_register("create_conversion_value_rule", fake_function)


def test_declared_legacy_is_skipped_silently():
    build_server()

    def legacy_function() -> dict:  # pragma: no cover - never registered
        return {}

    legacy_function.__module__ = "google_ads_mcp.tools.remaining_core_services"
    assert _candidate_should_register("create_conversion_value_rule", legacy_function) is False
    assert _TOOL_OWNERS.get("create_conversion_value_rule") == (
        "google_ads_mcp.tools.conversions"
    )
