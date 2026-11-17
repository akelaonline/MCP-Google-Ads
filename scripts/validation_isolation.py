"""Hermetic environment for the offline validation battery.

The server reads configuration from the process environment *and* from a dotenv
file at import time (``google_ads_mcp.config``), and several tests build the real
server, which opens the audit DB and creates its ``.pending.key``. Run naively,
the battery would therefore touch whatever DB / credentials the operator's shell
points at. This module builds one environment that is used for every step
(smoke, Ruff, pytest, lifecycle) and by ``tests/conftest.py``:

* every Google / Cloud credential-bearing variable is dropped;
* ``HOME`` (and XDG dirs) point at a throw-away directory;
* ``GOOGLE_ADS_MCP_ENV_FILE`` points at an empty file inside it, so neither an
  operator-selected dotenv nor ``<cwd>/.env`` is ever loaded;
* ``GOOGLE_ADS_MCP_AUDIT_DB`` points at a temporary DB (key lives next to it).

Pure stdlib; it must be importable *before* ``google_ads_mcp``.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Mapping
from pathlib import Path

# Anything starting with these can carry credentials, a config file or a project.
SCRUBBED_PREFIXES = (
    "GOOGLE_",
    "GCLOUD_",
    "CLOUDSDK_",
    "GCP_",
    "FASTMCP_",
    "MCP_",
)
SCRUBBED_EXACT = frozenset(
    {
        "DEVELOPER_TOKEN",
        "LOGIN_CUSTOMER_ID",
        "CLIENT_ID",
        "CLIENT_SECRET",
        "REFRESH_TOKEN",
    }
)


def isolated_environment(
    base: Mapping[str, str], workdir: str | os.PathLike[str]
) -> dict[str, str]:
    """Return a copy of ``base`` that cannot reach real credentials or DBs."""
    work = Path(workdir).resolve()
    home = work / "home"
    home.mkdir(parents=True, exist_ok=True)
    state = work / "state"
    state.mkdir(parents=True, exist_ok=True)
    empty_env = work / "empty.env"
    empty_env.write_text("")

    env = {
        key: value
        for key, value in base.items()
        if not key.upper().startswith(SCRUBBED_PREFIXES)
        and key.upper() not in SCRUBBED_EXACT
    }
    env.update(
        {
            "HOME": str(home),
            "USERPROFILE": str(home),
            "XDG_CONFIG_HOME": str(home / ".config"),
            "XDG_DATA_HOME": str(home / ".local" / "share"),
            "XDG_CACHE_HOME": str(home / ".cache"),
            "GOOGLE_ADS_MCP_ENV_FILE": str(empty_env),
            "GOOGLE_ADS_MCP_AUDIT_DB": str(state / "audit.db"),
            "FASTMCP_CHECK_FOR_UPDATES": "off",
        }
    )
    return env


def apply_to_process(workdir: str | os.PathLike[str] | None = None) -> Path:
    """Replace ``os.environ`` in place with the isolated environment.

    Must run before ``google_ads_mcp`` is imported (its dotenv load is at import).
    Returns the working directory used.
    """
    work = (
        Path(workdir)
        if workdir
        else Path(tempfile.mkdtemp(prefix="gads-mcp-validation-"))
    )
    new_env = isolated_environment(dict(os.environ), work)
    os.environ.clear()
    os.environ.update(new_env)
    return work
