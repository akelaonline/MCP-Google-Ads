# Updating a local Google Ads MCP installation

This repository is designed so an existing local server can be updated directly from GitHub without replacing its credentials or local runtime state.

**Current validation target: `0.16.3`. Do not deploy `0.16.0`, `0.16.1`, or `0.16.2` over a working production MCP until `0.16.3` passes the local validation gate.**

## Before updating

Know the directory where the repository is installed. The examples below assume:

```text
/path/to/MCP-Google-Ads
```

Your local `.env` contains Google Ads credentials and is intentionally not part of Git. Do not delete or overwrite it during an update.

If durable pending confirmations are enabled, also preserve:

- `GOOGLE_ADS_MCP_AUDIT_DB` (or the default `~/.google_ads_mcp/audit.db`);
- `GOOGLE_ADS_MCP_PENDING_ENCRYPTION_KEY`, or the generated `<audit-db>.pending.key` file.

The database and encryption key must remain paired or old pending actions cannot be replayed after restart.

## Standard update from GitHub main

Stop/restart the MCP client around the update so the old Python process is not kept alive.

```bash
cd /path/to/MCP-Google-Ads
git status
git fetch origin
git pull --ff-only origin main
source .venv/bin/activate
python -m pip install -e ".[dev]"
```

Reinstalling the package is important after pulling because releases may add/change Python dependencies. The v0.16 series requires `cryptography>=42` for encrypted durable pending replay.

Do **not** run `cp .env.example .env` on an existing installation; that command is only for first-time setup.

## Verify the installed version and exact checkout

```bash
.venv/bin/python -c "import google_ads_mcp; print(google_ads_mcp.__version__, google_ads_mcp.__file__)"
git rev-parse HEAD
git status --short
```

For the current validation target the package version must report:

```text
0.16.3
```

`git status --short` should normally be empty except for intentional local untracked files.

Before replacing a running production server, record the exact commit SHA that passed local validation.

## Required local validation before restarting production

Preferred one-command gate:

```bash
.venv/bin/python scripts/validate_local.py
```

This runs, with the same Python interpreter used by the MCP:

1. the isolated offline smoke test;
2. Ruff over `src`, `tests`, and `scripts`;
3. the complete pytest suite.

It prints the Git SHA, MCP version, Python version, Google Ads client version, FastMCP version, Ruff version, and pytest version. A successful run must end with:

```text
LOCAL VALIDATION GREEN
validated commit: <sha>
validated version: 0.16.3
```

The smoke stage uses a temporary SQLite audit DB, forces read-only mode, validates nested MCC isolation, imports the full tool package, constructs FastMCP and verifies that legacy duplicate definitions do not override their canonical v25 tool owners. It does not send Google Ads requests and does not write to the installation's production audit/pending database.

Equivalent individual commands, useful when diagnosing a failure:

```bash
.venv/bin/python scripts/smoke_test.py
.venv/bin/python -m ruff check src tests scripts
.venv/bin/python -m pytest -q
```

Do not replace the currently running production MCP if the validator exits non-zero.

See [`RELEASE_0.16.3.md`](RELEASE_0.16.3.md) for the Ruff/pytest cleanup and [`VALIDATION_CHECKLIST.md`](VALIDATION_CHECKLIST.md) for the live-account validation sequence.

## Conservative first restart

Only after the local validator is green, the safest first boot of the candidate build is read-only:

```dotenv
GOOGLE_ADS_MCP_READ_ONLY=true
```

Restart the MCP server/client, verify account discovery and reporting, then deliberately attempt a write and confirm that it is rejected by read-only policy.

After the installation is verified, restore the intended mode. The recommended live-account configuration is:

```dotenv
GOOGLE_ADS_MCP_READ_ONLY=false
GOOGLE_ADS_MCP_AUTO_APPROVE=false
GOOGLE_ADS_MCP_AUTO_APPROVE_SPEND=false
GOOGLE_ADS_MCP_AUTO_APPROVE_DESTRUCTIVE=false
GOOGLE_ADS_MCP_AUTO_APPROVE_SENSITIVE=false
```

## If `git pull --ff-only` refuses to update

Do not force-reset before understanding why. Inspect:

```bash
git status
git diff
git log --oneline --decorate -10
```

Local edits to tracked source files should be reviewed or backed up before changing them. Never solve an update conflict by deleting `.env`, the audit DB, or the pending encryption key.

## Rollback

Before changing a production installation, record the current commit:

```bash
git rev-parse HEAD
```

If a code rollback is required, switch back to that known commit and reinstall the package:

```bash
git checkout <known-good-commit>
source .venv/bin/activate
python -m pip install -e .
```

Do not roll back or replace the audit database casually. Code rollback and persistent-state rollback are different operations.
