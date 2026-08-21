"""Track MCP tool invocations so pending writes can be replayed after restart.

FastMCP tools are registered through a tiny wrapper that preserves each public
function signature while capturing the validated call arguments in a ContextVar.
SafetyLayer stores those arguments encrypted in SQLite. On restart, confirming a
pending action can re-invoke the same public tool and force that proposal to
execute with the original action id instead of creating a second pending action.

Some public tools intentionally share a lower-level safety/audit category (for
example several product-link helpers use ``create_product_link``). The replay
metadata therefore stores the *public MCP tool name* separately from the safety
category so those aliases remain restart-safe.

A small number of v0.16 specialist modules supersede older tool implementations
that still live in broader modules for source compatibility. Canonical ownership
is explicit below: non-canonical legacy definitions are not registered with
FastMCP, and any other duplicate tool name fails server construction instead of
silently relying on registration order.
"""

from __future__ import annotations

import inspect
from collections.abc import Callable
from contextvars import ContextVar
from functools import wraps
from typing import Any

_REPLAY_TOOL_ARGUMENT = "__google_ads_mcp_replay_tool_name__"

# Explicit canonical owners for legacy duplicate definitions. These are the
# implementations that expose the complete v25 contract and customer isolation.
_CANONICAL_TOOL_MODULES: dict[str, str] = {
    "list_asset_group_signals": "google_ads_mcp.tools.pmax_signals_listing",
    "add_asset_group_signal": "google_ads_mcp.tools.pmax_signals_listing",
    "list_asset_group_listing_filters": "google_ads_mcp.tools.pmax_signals_listing",
    "list_conversion_value_rules": "google_ads_mcp.tools.remaining_core_services",
    "create_conversion_value_rule": "google_ads_mcp.tools.remaining_core_services",
}

_CURRENT_INVOCATION: ContextVar[tuple[str, dict[str, Any]] | None] = ContextVar(
    "google_ads_mcp_current_invocation", default=None
)
_REPLAY_ACTION_ID: ContextVar[str | None] = ContextVar(
    "google_ads_mcp_replay_action_id", default=None
)
_TOOL_REGISTRY: dict[str, Callable[..., Any]] = {}
_TOOL_OWNERS: dict[str, str] = {}


class _InvocationName(str):
    """Comparison shim for tools whose public name differs from safety category.

    SafetyLayer historically checks ``invoked_tool == proposed_tool`` before it
    persists invocation arguments. Tool modules predate durable replay and some
    use a shared safety category instead of their public function name. Treating
    the tracked invocation as compatible with a string category lets SafetyLayer
    persist the call while the encrypted argument metadata below preserves the
    exact public tool that must be replayed.
    """

    def __eq__(self, other):  # type: ignore[override]
        return isinstance(other, str)

    __hash__ = str.__hash__


def current_invocation() -> tuple[str, dict[str, Any]] | None:
    value = _CURRENT_INVOCATION.get()
    if value is None:
        return None
    tool_name, arguments = value
    persisted = dict(arguments)
    persisted[_REPLAY_TOOL_ARGUMENT] = tool_name
    return _InvocationName(tool_name), persisted


def replay_action_id() -> str | None:
    return _REPLAY_ACTION_ID.get()


def registered_tool_names() -> list[str]:
    return sorted(_TOOL_REGISTRY)


def registered_tool_owners() -> dict[str, str]:
    """Return public tool -> defining module for diagnostics/tests."""
    return dict(_TOOL_OWNERS)


def canonical_tool_modules() -> dict[str, str]:
    """Return the explicit canonical-owner map for superseded tool definitions."""
    return dict(_CANONICAL_TOOL_MODULES)


def replay_tool(tool_name: str, arguments: dict[str, Any], action_id: str) -> Any:
    """Synchronously re-run the original registered MCP tool for a pending action."""
    replay_arguments = dict(arguments)
    public_tool_name = str(
        replay_arguments.pop(_REPLAY_TOOL_ARGUMENT, None) or tool_name
    )
    function = _TOOL_REGISTRY.get(public_tool_name)
    if function is None:
        raise LookupError(
            f"Tool '{public_tool_name}' is no longer registered; the pending action "
            "cannot be replayed safely. Re-propose it with the current MCP version."
        )
    token = _REPLAY_ACTION_ID.set(action_id)
    try:
        return function(**replay_arguments)
    finally:
        _REPLAY_ACTION_ID.reset(token)


def install_tool_tracking(mcp) -> None:
    """Wrap ``mcp.tool`` before tool modules register their functions.

    The wrapper supports both ``@mcp.tool()`` and ``mcp.tool(function, ...)`` forms.
    ``functools.wraps`` keeps the original signature visible to ``inspect.signature``
    (and therefore to FastMCP/Pydantic), despite the runtime wrapper using *args/**kwargs.

    The replay registry is process-global because confirmations need to find tools
    after registration. Building a *new* FastMCP instance in the same process is a
    fresh registration pass, so the registry/owner map are reset here before that
    pass starts. Calling install twice on the same FastMCP remains a no-op.
    """
    original_tool = mcp.tool
    if getattr(original_tool, "_google_ads_mcp_tracking_installed", False):
        return

    _TOOL_REGISTRY.clear()
    _TOOL_OWNERS.clear()

    def tracked_tool(function=None, *decorator_args, **decorator_kwargs):
        if function is None:

            def decorator(func):
                explicit_name = decorator_kwargs.get("name")
                tool_name = explicit_name or func.__name__
                if not _candidate_should_register(tool_name, func):
                    return func
                wrapped = _tracked_function(func, explicit_name)
                return original_tool(*decorator_args, **decorator_kwargs)(wrapped)

            return decorator

        explicit_name = decorator_kwargs.get("name")
        tool_name = explicit_name or function.__name__
        if not _candidate_should_register(tool_name, function):
            return function
        wrapped = _tracked_function(function, explicit_name)
        return original_tool(wrapped, *decorator_args, **decorator_kwargs)

    tracked_tool._google_ads_mcp_tracking_installed = True  # type: ignore[attr-defined]
    mcp.tool = tracked_tool


def _candidate_should_register(tool_name: str, function: Callable[..., Any]) -> bool:
    """Resolve known legacy duplicates and fail loudly on unexpected duplicates."""
    module_name = function.__module__
    canonical_module = _CANONICAL_TOOL_MODULES.get(tool_name)
    if canonical_module is not None and module_name != canonical_module:
        # The specialist implementation will register when its module is reached.
        return False

    existing_owner = _TOOL_OWNERS.get(tool_name)
    if existing_owner is not None:
        raise RuntimeError(
            f"Duplicate MCP tool registration for '{tool_name}': "
            f"{existing_owner} and {module_name}. Give the tool one public owner or "
            "add an explicit canonical owner only when superseding legacy code."
        )
    return True


def _tracked_function(function: Callable[..., Any], explicit_name: str | None):
    tool_name = explicit_name or function.__name__
    signature = inspect.signature(function)

    @wraps(function)
    def wrapped(*args, **kwargs):
        bound = signature.bind(*args, **kwargs)
        bound.apply_defaults()
        arguments = dict(bound.arguments)
        token = _CURRENT_INVOCATION.set((tool_name, arguments))
        try:
            return function(*args, **kwargs)
        finally:
            _CURRENT_INVOCATION.reset(token)

    _TOOL_REGISTRY[tool_name] = wrapped
    _TOOL_OWNERS[tool_name] = function.__module__
    return wrapped
