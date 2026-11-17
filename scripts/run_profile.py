#!/usr/bin/env python3
"""Launch one private stdio profile, isolating additional Claude processes.

POSIX (macOS/Linux). This launcher does not grant Google permissions or execute
campaign changes. Additional processes keep separate durable DB/key directories;
pending actions must be confirmed through the connection that proposed them.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env", required=True, type=Path)
    parser.add_argument("--mode", choices=("readonly", "editor"), required=True)
    parser.add_argument(
        "--check", action="store_true", help="Validate locally without Google calls"
    )
    args = parser.parse_args()
    if os.name != "posix":
        raise SystemExit("This launcher requires macOS/Linux.")
    import fcntl

    from cryptography.fernet import Fernet
    from dotenv import dotenv_values

    os.umask(0o077)
    env_path = args.env.expanduser().absolute()
    root = env_path.parent
    if any(path.is_symlink() for path in (env_path, *env_path.parents)):
        raise SystemExit("Profile paths must not contain symbolic links.")
    if (
        not env_path.is_file()
        or env_path.stat().st_mode & 0o077
        or root.stat().st_mode & 0o077
    ):
        raise SystemExit("Use a private profile directory (0700) and env file (0600).")
    if env_path.stat().st_uid != os.getuid() or root.stat().st_uid != os.getuid():
        raise SystemExit("The current user must own the profile.")
    values = dotenv_values(env_path, interpolate=False)
    for name in list(os.environ):
        if name.startswith(("GOOGLE_ADS_", "GOOGLE_MERCHANT_CENTER_")):
            os.environ.pop(name, None)
    os.environ.update({k: str(v) for k, v in values.items() if v is not None})
    os.environ["GOOGLE_ADS_MCP_ENV_FILE"] = str(env_path)
    os.chdir(root)
    from google_ads_mcp.config import load_settings

    try:
        settings = load_settings()
        Fernet(str(values.get("GOOGLE_ADS_MCP_PENDING_ENCRYPTION_KEY", "")).encode())
    except (ValueError, TypeError):
        raise SystemExit(
            "Invalid profile settings or pending encryption key."
        ) from None
    if "GOOGLE_ADS_MCP_READ_ONLY" not in values or settings.read_only != (
        args.mode == "readonly"
    ):
        raise SystemExit("READ_ONLY does not match the requested mode.")
    if (
        settings.auto_approve
        or settings.auto_approve_spend
        or settings.auto_approve_destructive
        or settings.auto_approve_sensitive
    ):
        raise SystemExit("All four auto-approval settings must be off.")
    if not settings.require_customer_allowlist or not (
        settings.allowed_manager_ids or settings.allowed_customer_ids
    ):
        raise SystemExit("A strict customer/manager allowlist is required.")
    if (
        settings.transport != "stdio"
        or Path(settings.audit_db_path) != root / "audit.db"
    ):
        raise SystemExit("Use stdio and an absolute audit.db path inside this profile.")
    if str(values.get("GOOGLE_ADS_MCP_ALLOW_INSECURE_HTTP", "")).lower() != "false":
        raise SystemExit("Insecure HTTP must be disabled explicitly.")
    if args.check:
        print("Profile validated locally; no Google API calls were made.")
        return

    lock_path = root / "server.lock"
    if lock_path.is_symlink():
        raise SystemExit("The process lock must not be a symbolic link.")
    lock = lock_path.open("a+")
    lock_path.chmod(0o600)
    try:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        from tempfile import mkdtemp

        instances = root / "instances"
        if instances.is_symlink():
            raise SystemExit("The instances directory must not be a symbolic link.")
        instances.mkdir(mode=0o700, exist_ok=True)
        instances.chmod(0o700)
        instance = Path(mkdtemp(prefix="instance-", dir=instances))
        key = Fernet.generate_key()
        with os.fdopen(
            os.open(
                instance / "pending.key", os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600
            ),
            "wb",
        ) as stream:
            stream.write(key)
        os.environ["GOOGLE_ADS_MCP_AUDIT_DB"] = str(instance / "audit.db")
        os.environ["GOOGLE_ADS_MCP_PENDING_ENCRYPTION_KEY"] = key.decode()
        print(
            "Additional MCP process: using an isolated pending DB and key.",
            file=sys.stderr,
        )

    # Retain the lock until server_main returns; argparse for the server must
    # not consume the profile launcher's arguments.
    sys.argv = [sys.argv[0]]
    from google_ads_mcp.server import main as server_main

    server_main()


if __name__ == "__main__":
    main()
