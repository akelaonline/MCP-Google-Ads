# Updating a local Google Ads MCP installation

This repository is designed so an existing local server can be updated directly from GitHub without replacing its credentials or local runtime state.

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
python -m pip install -e .
```

`pip install -e .` is important after pulling because releases may add or change Python dependencies. For 0.16.0, `cryptography>=42` is required for encrypted durable pending replay.

Do **not** run `cp .env.example .env` on an existing installation; that command is only for first-time setup.

## Verify the installed version

```bash
.venv/bin/python -c "import google_ads_mcp; print(google_ads_mcp.__version__, google_ads_mcp.__file__)"
```

For the current release this should report:

```text
0.16.0
```

Check the Git commit actually installed:

```bash
git rev-parse HEAD
git status --short
```

`git status --short` should normally be empty except for intentional local files that are not tracked.

## Conservative first restart

For an existing production installation, the safest first boot after an upgrade is read-only:

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

## Local validation

If the machine has normal network/package access, install development dependencies and run:

```bash
source .venv/bin/activate
pip install -e ".[dev]"
python scripts/smoke_test.py
ruff check src tests scripts
pytest -q
```

See [`VALIDATION_CHECKLIST.md`](VALIDATION_CHECKLIST.md) for the live-account validation sequence.

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
