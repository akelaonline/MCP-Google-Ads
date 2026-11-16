#!/usr/bin/env python3
"""Offline preflight for the real validation lab. Prints PASS/FAIL, never values.

Usage: python scripts/lab_preflight.py [lab_dir]   (default ~/.google_ads_mcp_lab)
"""

from __future__ import annotations

import sys
from pathlib import Path

REQUIRED = ["GOOGLE_ADS_MCP_ALLOWED_CUSTOMER_IDS"]
EXPECTED_TRUE = {"GOOGLE_ADS_MCP_READ_ONLY": "true"}
EXPECTED_FALSE = [
    "GOOGLE_ADS_MCP_AUTO_APPROVE",
    "GOOGLE_ADS_MCP_AUTO_APPROVE_SPEND",
    "GOOGLE_ADS_MCP_AUTO_APPROVE_DESTRUCTIVE",
    "GOOGLE_ADS_MCP_AUTO_APPROVE_SENSITIVE",
]


def _parse(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            values[key.strip()] = value.strip()
    return values


def main() -> int:
    lab = (
        Path(sys.argv[1]).expanduser()
        if len(sys.argv) > 1
        else Path.home() / ".google_ads_mcp_lab"
    )
    results: list[tuple[str, bool]] = [("lab directory exists", lab.is_dir())]
    env_file = lab / ".env"
    results.append((".env present in lab", env_file.is_file()))
    if env_file.is_file():
        env = _parse(env_file)
        for key in REQUIRED:
            results.append((f"{key} set", bool(env.get(key))))
        for key, want in EXPECTED_TRUE.items():
            results.append((f"{key}={want}", env.get(key, "").lower() == want))
        for key in EXPECTED_FALSE:
            results.append(
                (f"{key} is not true", env.get(key, "false").lower() != "true")
            )
        db = env.get("GOOGLE_ADS_MCP_AUDIT_DB", "")
        results.append(
            (
                "audit DB is inside the lab",
                bool(db) and str(lab) in str(Path(db).expanduser()),
            )
        )
    repo = Path(__file__).resolve().parents[1]
    results.append(
        ("repo has no .env tracked/present with secrets", not (repo / ".env").exists())
    )
    for name, ok in results:
        print(("PASS" if ok else "FAIL"), name)
    return 0 if all(ok for _, ok in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
