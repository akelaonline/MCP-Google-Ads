#!/usr/bin/env python3
"""Offline preflight for the real validation lab. Prints PASS/FAIL, never values.

Usage:
    python scripts/lab_preflight.py [--lab-dir DIR] [--env-file FILE]

Defaults: lab dir ``~/.google_ads_mcp_lab`` and env file ``<lab>/lab.env``
(the file the lab runbook uses; pass ``--env-file`` for any other name).

It reads the env file with python-dotenv (the parser the server uses), applies the
server's own boolean semantics, and only ever prints variable names and verdicts.
It makes no network call, does not import ``google_ads_mcp`` (whose import would
load a dotenv file) and never reads the production installation.

Exit code 0 only when every check passes.
"""

from __future__ import annotations

import argparse
import os
import stat
import sys
from pathlib import Path

from dotenv import dotenv_values

# Same semantics as google_ads_mcp.config._bool: unset -> default, else
# strip().lower() in {1,true,yes,on}. Anything else (including "") is False.
_TRUE = frozenset({"1", "true", "yes", "on"})

GUARDED = (
    "GOOGLE_ADS_MCP_READ_ONLY",
    "GOOGLE_ADS_MCP_AUTO_APPROVE",
    "GOOGLE_ADS_MCP_AUTO_APPROVE_SPEND",
    "GOOGLE_ADS_MCP_AUTO_APPROVE_DESTRUCTIVE",
    "GOOGLE_ADS_MCP_AUTO_APPROVE_SENSITIVE",
    "GOOGLE_ADS_MCP_REQUIRE_CUSTOMER_ALLOWLIST",
    "GOOGLE_ADS_MCP_ALLOWED_CUSTOMER_IDS",
    "GOOGLE_ADS_MCP_ALLOWED_MANAGER_IDS",
    "GOOGLE_ADS_MCP_EXCLUDED_CUSTOMER_IDS",
    "GOOGLE_ADS_LOGIN_CUSTOMER_ID",
    "GOOGLE_ADS_MCP_ALLOWED_MERCHANT_IDS",
    "GOOGLE_ADS_MCP_REQUIRE_MERCHANT_ALLOWLIST",
    "GOOGLE_ADS_MCP_AUDIT_DB",
    "GOOGLE_ADS_MCP_TRANSPORT",
    "GOOGLE_ADS_MCP_ENV_FILE",
)


def runtime_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in _TRUE


def _split_ids(raw: str | None) -> list[str]:
    return [item.strip() for item in (raw or "").split(",") if item.strip()]


def _valid_customer_id(item: str) -> bool:
    digits = item.replace("-", "").strip()
    return digits.isdigit() and len(digits) == 10


def _valid_merchant_id(item: str) -> bool:
    return item.isdigit() and int(item) > 0


def _has_symlink_component(path: Path) -> bool:
    """True if any existing component of the (absolute) path is a symlink."""
    current = Path(path.anchor)
    for part in path.parts[1:]:
        current = current / part
        if current.is_symlink():
            return True
    return False


def _inside(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.resolve())
    except ValueError:
        return False
    return True


def _private(path: Path) -> bool:
    mode = path.stat().st_mode
    return (mode & (stat.S_IRWXG | stat.S_IRWXO)) == 0


def _owned_by_me(path: Path) -> bool:
    geteuid = getattr(os, "geteuid", None)
    return True if geteuid is None else path.stat().st_uid == geteuid()


class Report:
    def __init__(self) -> None:
        self.rows: list[tuple[bool, str]] = []

    def check(self, ok: bool, label: str) -> bool:
        self.rows.append((bool(ok), label))
        return bool(ok)

    def print(self) -> None:
        for ok, label in self.rows:
            print(("PASS" if ok else "FAIL"), label)

    @property
    def ok(self) -> bool:
        return all(ok for ok, _ in self.rows)


def _check_path_safety(report: Report, label: str, path: Path, lab: Path) -> None:
    """Containment of a lab artifact: resolved, real membership, no symlinks."""
    report.check(path.is_absolute(), f"{label}: absolute path")
    report.check(not _has_symlink_component(path), f"{label}: no symlink in its path")
    report.check(_inside(path, lab), f"{label}: really inside the lab directory")


def run(
    lab_dir: Path,
    env_file: Path | None,
    environ: dict[str, str],
    repo: Path | None = None,
) -> Report:
    """``repo`` is the checkout to inspect (default: the one containing this script)."""
    report = Report()
    lab = Path(os.path.abspath(os.path.expanduser(str(lab_dir))))
    env_path = (
        Path(os.path.abspath(os.path.expanduser(str(env_file))))
        if env_file is not None
        else lab / "lab.env"
    )
    repo = Path(repo).resolve() if repo else Path(__file__).resolve().parents[1]
    production = Path(os.path.expanduser("~/.google_ads_mcp"))

    # --- lab directory -------------------------------------------------------
    lab_ok = report.check(lab.is_dir(), "lab directory exists")
    if lab_ok:
        report.check(
            not _has_symlink_component(lab), "lab directory: no symlink in its path"
        )
        report.check(_private(lab), "lab directory: private (no group/other access)")
        report.check(_owned_by_me(lab), "lab directory: owned by the current user")
    report.check(
        lab.resolve() != production.resolve()
        and not _inside(lab, production)
        and not _inside(production, lab),
        "lab is separate from the production data directory",
    )
    report.check(
        not _inside(lab, repo) and not _inside(env_path, repo),
        "lab and env file are outside the repository checkout",
    )
    report.check(not (repo / ".env").exists(), "repository has no .env with secrets")

    # --- env file ------------------------------------------------------------
    file_ok = report.check(
        env_path.is_file() and not env_path.is_symlink(), "env file is a regular file"
    )
    values: dict[str, str | None] = {}
    if file_ok:
        _check_path_safety(report, "env file", env_path, lab)
        report.check(
            _private(env_path), "env file: private permissions (no group/other access)"
        )
        report.check(_owned_by_me(env_path), "env file: owned by the current user")
        values = dict(dotenv_values(env_path, interpolate=False))
    if not file_ok or not lab_ok:
        return report

    def get(name: str) -> str | None:
        return values.get(name)

    # Process environment wins over the dotenv file at runtime (load_dotenv does not
    # override), so a differing shell value would silently change the lab config.
    conflicts = []
    for name in GUARDED:
        if name not in environ:
            continue
        if name == "GOOGLE_ADS_MCP_ENV_FILE":
            same = Path(os.path.abspath(os.path.expanduser(environ[name]))) == env_path
            if not same:
                conflicts.append(name)
        elif environ[name] != (get(name) or ""):
            conflicts.append(name)
    suffix = f" (differs: {', '.join(conflicts)})" if conflicts else ""
    report.check(
        not conflicts, "process environment does not override lab settings" + suffix
    )

    # --- safety flags (same semantics as the runtime) -------------------------
    report.check(
        runtime_bool(get("GOOGLE_ADS_MCP_READ_ONLY")),
        "GOOGLE_ADS_MCP_READ_ONLY is true",
    )
    for name in (
        "GOOGLE_ADS_MCP_AUTO_APPROVE",
        "GOOGLE_ADS_MCP_AUTO_APPROVE_SPEND",
        "GOOGLE_ADS_MCP_AUTO_APPROVE_DESTRUCTIVE",
        "GOOGLE_ADS_MCP_AUTO_APPROVE_SENSITIVE",
    ):
        report.check(not runtime_bool(get(name)), f"{name} is off")
    transport = (get("GOOGLE_ADS_MCP_TRANSPORT") or "stdio").strip().lower()
    report.check(transport == "stdio", "GOOGLE_ADS_MCP_TRANSPORT is stdio")

    # --- strict allowlists ---------------------------------------------------
    customers = _split_ids(get("GOOGLE_ADS_MCP_ALLOWED_CUSTOMER_IDS"))
    managers = _split_ids(get("GOOGLE_ADS_MCP_ALLOWED_MANAGER_IDS"))
    excluded = _split_ids(get("GOOGLE_ADS_MCP_EXCLUDED_CUSTOMER_IDS"))
    report.check(
        bool(customers) or bool(managers),
        "allowlist source present: GOOGLE_ADS_MCP_ALLOWED_CUSTOMER_IDS or "
        "GOOGLE_ADS_MCP_ALLOWED_MANAGER_IDS is not empty",
    )
    report.check(
        all(_valid_customer_id(item) for item in customers + managers + excluded),
        "every allowed/manager/excluded customer ID is 10 digits (dashes allowed)",
    )
    if managers:
        login = "".join(ch for ch in (get("GOOGLE_ADS_LOGIN_CUSTOMER_ID") or "") if ch.isdigit())
        normalized = {"".join(ch for ch in m if ch.isdigit()) for m in managers}
        report.check(
            login in normalized if login else len(normalized) == 1,
            "login customer ID is one of the manager IDs (or the single manager)",
        )
    report.check(
        runtime_bool(get("GOOGLE_ADS_MCP_REQUIRE_CUSTOMER_ALLOWLIST")),
        "GOOGLE_ADS_MCP_REQUIRE_CUSTOMER_ALLOWLIST is true (strict allowlist)",
    )
    merchants = _split_ids(get("GOOGLE_ADS_MCP_ALLOWED_MERCHANT_IDS"))
    report.check(
        all(_valid_merchant_id(item) for item in merchants),
        "every allowed Merchant ID is a positive number",
    )
    if runtime_bool(get("GOOGLE_ADS_MCP_REQUIRE_MERCHANT_ALLOWLIST")):
        report.check(bool(merchants), "Merchant allowlist required and not empty")
    # No Merchant list while an Ads allowlist exists = Merchant refused (fail closed):
    # acceptable for an Ads-only lab, so it is a note, not a failure.
    print(
        "NOTE Merchant tools:",
        "scoped" if merchants else "disabled (no Merchant allowlist)",
    )

    # --- audit DB and key: real containment ---------------------------------
    raw_db = get("GOOGLE_ADS_MCP_AUDIT_DB")
    if not raw_db or not raw_db.strip():
        report.check(
            False, "GOOGLE_ADS_MCP_AUDIT_DB is set (an absolute path inside the lab)"
        )
    else:
        db = Path(os.path.abspath(os.path.expanduser(raw_db.strip())))
        # The runtime rewrites relative paths into ~/.google_ads_mcp, i.e. production.
        report.check(
            Path(os.path.expanduser(raw_db.strip())).is_absolute(),
            "audit DB path is absolute (relative paths are redirected to production)",
        )
        for label, path in (
            ("audit DB", db),
            ("pending key", Path(str(db) + ".pending.key")),
        ):
            _check_path_safety(report, label, path, lab)
            if path.exists():
                report.check(
                    path.is_file() and not path.is_symlink(), f"{label}: regular file"
                )
                report.check(_private(path), f"{label}: private permissions")
        report.check(db.parent.is_dir(), "audit DB directory exists")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--lab-dir", default="~/.google_ads_mcp_lab")
    parser.add_argument("--env-file", default=None, help="default: <lab-dir>/lab.env")
    parser.add_argument(
        "--repo-root",
        default=None,
        help="checkout to inspect for a stray .env (default: this script's checkout)",
    )
    args = parser.parse_args(argv)
    lab = Path(args.lab_dir)
    env_file = (
        Path(args.env_file)
        if args.env_file
        else Path(os.path.expanduser(str(lab))) / "lab.env"
    )
    repo = Path(args.repo_root) if args.repo_root else None
    report = run(lab, env_file, dict(os.environ), repo)
    report.print()
    print("PREFLIGHT", "PASSED" if report.ok else "FAILED")
    return 0 if report.ok else 1


if __name__ == "__main__":
    sys.exit(main())
