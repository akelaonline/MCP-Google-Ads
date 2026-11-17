"""Static classification of MCP tools that can reach ``SafetyLayer.propose``.

Used to (a) generate ``src/google_ads_mcp/write_tools.py`` and (b) verify in tests
that the committed manifest has not drifted from the sources.

A public tool is a *write tool* when its body, or any function it calls
(transitively, through same-module helpers and ``from .x import helper`` imports),
contains a call to an attribute named ``propose``. The server's own
``confirm_pending_action`` is always a write tool.
"""

from __future__ import annotations

import ast
from pathlib import Path

PKG = Path(__file__).resolve().parents[1] / "src" / "google_ads_mcp"
ALWAYS_WRITE = frozenset({"confirm_pending_action"})


def _is_tool(fn: ast.AST) -> bool:
    if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
        return False
    for d in fn.decorator_list:
        target = d.func if isinstance(d, ast.Call) else d
        if (
            isinstance(target, ast.Attribute)
            and target.attr == "tool"
            and isinstance(target.value, ast.Name)
            and target.value.id == "mcp"
        ):
            return True
    return False


def _tool_name(fn) -> str:
    for d in fn.decorator_list:
        if isinstance(d, ast.Call):
            for kw in d.keywords:
                if kw.arg == "name" and isinstance(kw.value, ast.Constant):
                    return str(kw.value.value)
    return fn.name


class _Module:
    def __init__(self, path: Path):
        self.path = path
        self.tree = ast.parse(path.read_text(encoding="utf-8"))
        self.functions: dict[str, ast.AST] = {}
        self.imports: dict[str, tuple[Path, str]] = {}
        for node in self.tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self.functions[node.name] = node
            elif isinstance(node, ast.ImportFrom) and node.level >= 1:
                base = path.parent
                for _ in range(node.level - 1):
                    base = base.parent
                target = (
                    base.joinpath(*(node.module.split("."))) if node.module else base
                )
                candidate = target.with_suffix(".py")
                if candidate.exists():
                    for alias in node.names:
                        self.imports[alias.asname or alias.name] = (
                            candidate,
                            alias.name,
                        )


_CACHE: dict[Path, _Module] = {}


def _module(path: Path) -> _Module:
    if path not in _CACHE:
        _CACHE[path] = _Module(path)
    return _CACHE[path]


def _reaches_propose(mod: _Module, node: ast.AST, seen: set) -> bool:
    for sub in ast.walk(node):
        if not isinstance(sub, ast.Call):
            continue
        func = sub.func
        if isinstance(func, ast.Attribute) and func.attr == "propose":
            return True
        if isinstance(func, ast.Name):
            name = func.id
            if name in mod.functions and (mod.path, name) not in seen:
                seen.add((mod.path, name))
                if _reaches_propose(mod, mod.functions[name], seen):
                    return True
            elif name in mod.imports:
                other_path, other_name = mod.imports[name]
                other = _module(other_path)
                if (
                    other_name in other.functions
                    and (other_path, other_name) not in seen
                ):
                    seen.add((other_path, other_name))
                    if _reaches_propose(other, other.functions[other_name], seen):
                        return True
    return False


def classify() -> tuple[set[str], set[str]]:
    """Return ``(write_tools, all_tools)`` computed from the tool sources."""
    write: set[str] = set(ALWAYS_WRITE)
    allt: set[str] = set(ALWAYS_WRITE)
    for path in sorted((PKG / "tools").glob("*.py")) + [PKG / "server.py"]:
        mod = _module(path)
        for node in ast.walk(mod.tree):
            if _is_tool(node):
                name = _tool_name(node)
                allt.add(name)
                if _reaches_propose(mod, node, set()):
                    write.add(name)
    return write, allt


def render(write: set[str]) -> str:
    lines = ",\n".join(f'        "{n}"' for n in sorted(write))
    return (
        '"""Public MCP tools that can reach ``SafetyLayer.propose`` (generated).\n\n'
        "Do not edit by hand: regenerate with ``python scripts/gen_write_tools.py``.\n"
        "``tests/test_read_only_early_reject.py`` fails if this drifts from the sources.\n"
        "Used to reject write tools in READ_ONLY mode before any client is built or\n"
        'any authentication is attempted.\n"""\n\n'
        "from __future__ import annotations\n\n"
        "WRITE_TOOLS: frozenset[str] = frozenset(\n    {\n"
        f"{lines},\n    }}\n)\n"
    )


if __name__ == "__main__":
    import sys

    write, _ = classify()
    target = PKG / "write_tools.py"
    if "--check" in sys.argv:
        raise SystemExit(
            0 if target.read_text(encoding="utf-8") == render(write) else 1
        )
    target.write_text(render(write), encoding="utf-8")
    print(f"{len(write)} write tools -> {target}")
