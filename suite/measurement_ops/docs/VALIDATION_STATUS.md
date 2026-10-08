# Measurement Ops v0.1 — Validation status

## Current status (2026-10-07)

- PR #14: **draft**. No changes to the production Google Ads MCP or `main`.
- Issue #15: authenticated read-only GTM/GA4 E2E **blocked** because dedicated
  OAuth tokens, explicitly authorized test site/property/container, and a
  certified restricted-network browser sandbox are not yet available.
- **Offline validation GREEN only for the historical HEADs below.**
  Hermeticity fixes after `49c5fbd` require a new validation run on current HEAD.

## Independently reported offline results

| Item | Earlier tested SHA | Latest verified historical SHA |
| --- | --- | --- |
| Commit | `5555a1e43bbfaef941e866152a325bbabbfae904` | `49c5fbd03b692ba30d95d0ff2216172b25dce7d9` |
| Environment | Isolated Linux aarch64 VM | Isolated Linux aarch64 VM |
| Python | 3.12.14 | 3.12.14 |
| Ruff | 0.8.6 PASS | 0.8.6 PASS |
| pytest | 114 passed | **118 passed** |
| GA4 Measurement ID isolation tests | Not yet added | **4/4 PASS** |
| MCP import/tools | PASS; 38 tools | PASS; 38 tools |
| WordPress PHP lint | PHP 8.1.2 PASS | PHP 8.1.2 PASS |
| GTM preview/writes/publish | false / false / false | false / false / false |

These are *external developer reports*, not independent executions by the
PR authoring environment. Original full raw logs were not committed.

### Hidden prerequisite revealed during the latest test

The first `49c5fbd` gate attempt failed with `Errno 28` because importing
`server.py` during pytest collection immediately called
`SiteRegistry.from_env()`, creating/opening the real user's
`~/.mkt-measurement-ops/measurement_ops.db` while the user's HOME was full.

A rerun with writable `HOME=/tmp/mops-home` passed all 118 tests. This
established the offline pass **and** exposed that test collection was not
hermetic. It did not test Google APIs.

## Subsequent hermeticity changes: MUST RETEST

- `server.registry` now holds a `LazySiteRegistry`. Importing the MCP server
  no longer creates or opens the default user's SQLite database.
- `tests/conftest.py` selects a disposable SQLite database before test module
  collection, and restores the prior environment on pytest shutdown.
- `scripts/validate_local.py` uses an isolated temporary HOME, cache and DB
  for **compileall, Ruff, pytest, module imports and PHP lint**, rather than
  only isolating its final import step. Google API credentials are withheld
  from those processes; GTM preview/writes/publish gates are forced false.
- `tests/test_import_isolation.py` provides regressions for import side
  effects and delayed registry initialization.

**Do not label the changed branch GREEN until the complete script is rerun
against the newest commit.** A full end-to-end release is even further away.

## New read-only OAuth onboarding (current HEAD also untested)

After the hermeticity changes, Measurement Ops gained:

- `src/mkt_measurement_ops/credentials.py`: segregated GTM/GA4 read-only
  OAuth grants in owner-only files, strict scope validation, no token logging.
- `scripts/authorize_readonly.py`: per-provider Desktop OAuth browser
  consent flow on the actual local Mac; **cannot run transparently in the
  isolated remote VM**.
- `scripts/smoke_readonly.py --confirm-readonly`: opt-in, real Google API
  calls limited to GTM accounts.list and GA4 accountSummaries.list; only
  sanitized counts are printed.
- Tests of read-only scopes, private file modes, separate credentials, and
  explicit network-call intent.
- Providers load the per-provider private files, with a legacy env fallback.

**No OAuth grants have been created, no Google API smoke executed, and no
customer resources modified.** Run the full offline validation on this newest
HEAD before initiating a real read-only connection. See
`docs/OAUTH_READONLY_SETUP.md` and Issue #15 for the approved workflow.

## Required latest-head validation

Use a separate, clean worktree and isolated virtual environment. Do not change
the production Ads checkout.

```bash
git fetch origin
git switch --detach origin/feature/measurement-ops-v0.1
cd suite/measurement_ops
python -m pip install -e ".[dev,web]"
python -m playwright install chromium
git rev-parse HEAD
python scripts/validate_local.py
```

Before any destructive checkout/reset, verify the worktree is clean.
The validator requires `ruff==0.8.6` and a working `php -l`. Only
`MEASUREMENT OPS LOCAL VALIDATION GREEN` plus exit code 0 on the current
HEAD counts as a complete offline gate. Tests must not create or touch the
normal `~/.mkt-measurement-ops` database. No secrets go into logs.

## Authenticated E2E blocker (Issue #15)

The developer checked read-only local capabilities with Google mutation flags
false. `gtm_list_accounts` failed closed with the missing configuration error
**before attempting a network call**. With no GTM/GA4 OAuth tokens, no API
result exists: account IDs, containers, streams, permissions and events are
**unknown**, not failed or verified.

E2E requires dedicated OAuth grants for `tagmanager.readonly` and
`analytics.readonly`; an explicitly approved GTM container, GA4 property
and test hostname; and restricted-network sandboxing for the browser auditor.
The Google Ads OAuth token does not substitute for these grants.

Use `docs/E2E_READONLY_RUNBOOK.md` only after latest-head offline GREEN.
No publish, customer-site deploy or Ads mutation is authorized.

## Beyond read-only E2E

Still unverified: real GTM API contracts and scopes; real GA4 Admin/Data
permissions; WordPress 6.9+ bridge/Abilities API behavior; Astro build/deploy;
true successful-form conversion tracking; consent and deduplication;
browser SSRF defense under restricted-network conditions; publish
reconciliation/concurrency and rollback. These are separate release gates.

**Keep PR #14 draft until staged WordPress and Astro pilots succeed.**
