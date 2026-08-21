#!/usr/bin/env python3
"""Run the local non-E2E validation gate for Google Ads MCP.

This script is intentionally local/manual: the repository does not use GitHub
Actions. It runs the isolated smoke test, Ruff, and pytest with the current
Python interpreter, then prints the installed MCP version and Git commit.

Usage:
    .venv/bin/python scripts/validate_local.py
"""

from __future__ import annotations

import importlib.metadata
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _run(label: str, command: list[str]) -> None:
    print(f"\n== {label} ==")
    print("$", " ".join(command))
    completed = subprocess.run(command, cwd=ROOT, check=False)
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)


def _git_head() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=ROOT,
        check=False,
        text=True,
        capture_output=True,
    )
    return completed.stdout.strip() if completed.returncode == 0 else "unknown"


def _package_version(name: str) -> str:
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "not-installed"


def main() -> int:
    import google_ads_mcp

    print("Google Ads MCP local validation")
    print(f"repo: {ROOT}")
    print(f"git: {_git_head()}")
    print(f"mcp: {google_ads_mcp.__version__}")
    print(f"python: {sys.version.split()[0]}")
    print(f"google-ads: {_package_version('google-ads')}")
    print(f"fastmcp: {_package_version('fastmcp')}")
    print(f"ruff: {_package_version('ruff')}")
    print(f"pytest: {_package_version('pytest')}")

    missing = [
        name
        for name in ("google-ads", "fastmcp", "ruff", "pytest")
        if _package_version(name) == "not-installed"
    ]
    if missing:
        print(
            "\nMissing validation/runtime dependencies: " + ", ".join(missing),
            file=sys.stderr,
        )
        print(
            f"Install them first with: {sys.executable} -m pip install -e '.[dev]'",
            file=sys.stderr,
        )
        return 2

    _run("isolated smoke", [sys.executable, "scripts/smoke_test.py"])
    _run("ruff", [sys.executable, "-m", "ruff", "check", "src", "tests", "scripts"])
    _run("pytest", [sys.executable, "-m", "pytest", "-q"])

    print("\nLOCAL VALIDATION GREEN")
    print(f"validated commit: {_git_head()}")
    print(f"validated version: {google_ads_mcp.__version__}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
