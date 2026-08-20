"""Track MCP tool invocations so pending writes can be replayed after restart.

FastMCP tools are registered through a tiny wrapper that preserves each public
function signature while capturing the validated call arguments in a ContextVar.
SafetyLayer stores those arguments encrypted in SQLite. On restart, confirming a
pending action can re-invoke the same tool and force that proposal to execute with
the original action id instead of creating a second pending action.
"""

from __future__ import annotations

import inspect
from contextvars import ContextVar
from functools import wraps
from typing import Any, Callable

_CURRENT_INVOCATION: ContextVar[tuple[str, dict[str, Any]] | None] = ContextVar(
    "google_ads_mcp_current_invocation", default=None
)
_REPLAY_ACTION_ID: ContextVar[str | None] = ContextVar(
    "google_ads_mcp_replay_action_id", default=None
)
_TOOL_REGISTRY: dict[str, Callable[..., Any]] = {}


def current_invocation() -> tuple[str, dict[str, Any]] | None:
    value = _CURRENT_INVOCATION.get()
    if value is None:
        return None
    tool_name, arguments = value
    return tool_name, dict(arguments)


def replay_action_id() -> str | None:
    return _REPLAY_ACTION_ID.get()


def registered_tool_names() -> list[str]:
    return sorted(_TOOL_REGISTRY)


def replay_tool(tool_name: str, arguments: dict[str, Any], action_id: str) -> Any:
    """Synchronously re-run a registered tool under one pending action id."""
    function = _TOOL_REGISTRY.get(tool_name)
    if function is None:
        raise LookupError(
            f"Tool '{tool_name}' is no longer registered; the pending action cannot "
            "be replayed safely. Re-propose it with the current MCP version."
        )
    token = _REPLAY_ACTION_ID.set(action_id)
    try:
        return function(**arguments)
    finally:
        _REPLAY_ACTION_ID.reset(token)


def install_tool_tracking(mcp) -> None:
    """Wrap ``mcp.tool`` before tool modules register their functions.

    The wrapper supports both ``@mcp.tool()`` and ``mcp.tool(function, ...)`` forms.
    ``functools.wraps`` keeps the original signature visible to ``inspect.signature``
    (and therefore to FastMCP/Pydantic), despite the runtime wrapper using *args/**kwargs.
    """
    original_tool = mcp.tool
    if getattr(original_tool, "_google_ads_mcp_tracking_installed", False):
        return

    def tracked_tool(function=None, *decorator_args, **decorator_kwargs):
        if function is None:
            def decorator(func):
                wrapped = _tracked_function(func, decorator_kwargs.get("name"))
                return original_tool(*decorator_args, **decorator_kwargs)(wrapped)
            return decorator

        wrapped = _tracked_function(function, decorator_kwargs.get("name"))
        return original_tool(wrapped, *decorator_args, **decorator_kwargs)

    tracked_tool._google_ads_mcp_tracking_installed = True  # type: ignore[attr-defined]
    mcp.tool = tracked_tool


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

    # Replays call this wrapper directly so the SafetyLayer sees the original
    # invocation arguments again. Later registrations with the same tool name are
    # rejected by FastMCP; keeping the newest here matches that behavior.
    _TOOL_REGISTRY[tool_name] = wrapped
    return wrapped
