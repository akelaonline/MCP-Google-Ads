"""Static guardrail: public MCP tools must not execute writes before SafetyLayer.

The runtime read-only kill switch lives at ``ctx.safety.propose`` / ``confirm``.
That guarantee only holds if every mutating public tool keeps the live Google/API
call inside its deferred ``execute`` closure. This test scans tool modules for
write-looking RPCs in the outer body of ``@mcp.tool()`` functions and also tracks
module-level helpers that contain such RPCs.

It deliberately does not inspect nested functions or lambdas: those are the
closures passed to the safety layer and are where live mutation is expected to
live.
"""

from __future__ import annotations

import ast
from pathlib import Path

TOOLS = Path(__file__).parents[1] / "src" / "google_ads_mcp" / "tools"

_WRITE_PREFIXES = (
    "mutate_",
    "create_",
    "update_",
    "remove_",
    "delete_",
    "upload_",
    "apply_",
    "start_",
    "accept_",
    "decline_",
    "reject_",
    "revoke_",
    "promote_",
    "graduate_",
    "end_",
    "schedule_",
    "append_",
    "provide_",
    "set_",
    "run_",
)
_WRITE_EXACT = {"mutate", "mutate_atomic"}
_HTTP_WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def _is_mcp_tool(function: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    for decorator in function.decorator_list:
        target = decorator.func if isinstance(decorator, ast.Call) else decorator
        if (
            isinstance(target, ast.Attribute)
            and target.attr == "tool"
            and isinstance(target.value, ast.Name)
            and target.value.id == "mcp"
        ):
            return True
    return False


def _call_name(call: ast.Call) -> str | None:
    if isinstance(call.func, ast.Name):
        return call.func.id
    return None


def _write_call_reason(call: ast.Call) -> str | None:
    if not isinstance(call.func, ast.Attribute):
        return None

    attr = call.func.attr
    if attr in _WRITE_EXACT or attr.startswith(_WRITE_PREFIXES):
        return f"direct write-looking call .{attr}(...)"

    # Data Manager and similar REST wrappers use request(method, ...).
    if attr == "request" and call.args:
        method = call.args[0]
        if (
            isinstance(method, ast.Constant)
            and isinstance(method.value, str)
            and method.value.upper() in _HTTP_WRITE_METHODS
        ):
            return f"direct HTTP {method.value.upper()} request"

    return None


class _OuterBodyCalls(ast.NodeVisitor):
    """Visit one function body without descending into deferred closures."""

    def __init__(self, root):
        self.root = root
        self.calls: list[ast.Call] = []

    def visit_FunctionDef(self, node):
        if node is self.root:
            for statement in node.body:
                self.visit(statement)
        # Nested def = deferred closure/helper local to this function; skip it.

    def visit_AsyncFunctionDef(self, node):
        if node is self.root:
            for statement in node.body:
                self.visit(statement)

    def visit_Lambda(self, node):
        # A lambda may be supplied as execute=...; treat it as deferred.
        return

    def visit_Call(self, node):
        self.calls.append(node)
        self.generic_visit(node)


def _outer_calls(function: ast.FunctionDef | ast.AsyncFunctionDef) -> list[ast.Call]:
    visitor = _OuterBodyCalls(function)
    visitor.visit(function)
    return visitor.calls


def _module_helpers(tree: ast.Module):
    return {
        node.name: node
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }


def _dangerous_helpers(tree: ast.Module) -> set[str]:
    helpers = _module_helpers(tree)
    dangerous = {
        name
        for name, function in helpers.items()
        if any(_write_call_reason(call) for call in _outer_calls(function))
    }

    # Propagate helper -> helper calls so a thin wrapper around a writer is also
    # considered dangerous when invoked before the safety proposal.
    changed = True
    while changed:
        changed = False
        for name, function in helpers.items():
            if name in dangerous:
                continue
            called_names = {
                called
                for call in _outer_calls(function)
                if (called := _call_name(call)) is not None
            }
            if called_names & dangerous:
                dangerous.add(name)
                changed = True
    return dangerous


def test_mcp_tools_do_not_write_before_safety_proposal():
    violations: list[str] = []

    for path in sorted(TOOLS.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        dangerous_helpers = _dangerous_helpers(tree)

        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not _is_mcp_tool(node):
                continue

            for call in _outer_calls(node):
                reason = _write_call_reason(call)
                if reason:
                    violations.append(
                        f"{path.name}:{call.lineno} {node.name}: {reason}"
                    )
                    continue

                helper = _call_name(call)
                if helper and helper in dangerous_helpers:
                    violations.append(
                        f"{path.name}:{call.lineno} {node.name}: calls write helper "
                        f"{helper}(...) before the deferred safety closure"
                    )

    assert not violations, (
        "A public MCP tool can reach a live write before SafetyLayer.propose(). "
        "Move the RPC/helper call inside the execute closure supplied to "
        "ctx.safety.propose(...):\n" + "\n".join(violations)
    )
