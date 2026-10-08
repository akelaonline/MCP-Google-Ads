# Measurement Ops v0.1 — Validation status

## Most recent independent offline gate: 49c5fbd (GREEN, 2026-10-07)

Reported by the independent developer from a clean isolated Linux/aarch64 worktree
at commit `49c5fbd03b692ba30d95d0ff2216172b25dce7d9`:

| Check | Result |
| --- | --- |
| Python | 3.12.14 |
| Ruff | 0.8.6, PASS |
| pytest | **118 passed, 0 failed** |
| Measurement ID isolation regressions | 4/4 passed |
| Package imports | PASS, v0.1.0 |
| MCP tools | 38 registered |
| WordPress PHP syntax | PASS, PHP 8.1.2 |
| GTM mutation gates | preview, writes and publish: false |
| Real GTM/GA4 API E2E | **NOT RUN: no dedicated read-only OAuth tokens** |
| Browser network-isolation sandbox | Not certified |

**Important qualification:** the gate passed with a writable isolated HOME. An
initial gate attempt uncovered import-time creation of the real user's SQLite
registry in `~/.mkt-measurement-ops` during pytest collection. That is a genuine
test isolation bug, not an OAuth or Google API error. The E2E was not executed.

## New fix: hermetic test runner + lazy registry (CURRENT HEAD RETEST REQUIRED)

After the 49c5fbd GREEN, code changed again:

- `server.py` now constructs a `LazySiteRegistry`, not `SiteRegistry.from_env()` at
  module import. SQLite is opened only on the first site registry operation.
- `tests/conftest.py` sets a throwaway SQLite DB **before** pytest imports
  test modules, and restores the prior environment on teardown.
- `scripts/validate_local.py` isolates HOME and MEASUREMENT_OPS_DB for **all**
  subprocesses, not only the module import step. Provider OAuth variables are
  withheld from the offline gate and all GTM mutation gates are forced false.
- `tests/test_import_isolation.py` checks the default HOME is not written by
  importing the MCP server and the lazy registry creates DB only on first use.

**The latest PR HEAD has NOT YET passed the full offline validation.**
Re-run `python scripts/validate_local.py` on the latest branch SHA, including
PHP lint. Don't report 118/118 as the test result for the new code.

The 2026-10-07 E2E issue #15 remains **BLOCKED** because the test environment
lacks dedicated GTM and GA4 read-only credentials, an authorized test site and
certified browser-network isolation. Do not use Google Ads OAuth tokens as a
substitute, and do not paste secrets into GitHub or chat.

---

## Offline test gate: GREEN on a pinned historical SHA

External developer report, executed in an **isolated Linux aarch64 VM worktree** on
commit `5555a1e43bbfaef941e866152a325bbabbfae904`.

| Gate | Reported result |
| --- | --- |
| Git tree | Worktree clean and files verified against pinned commit |
| Python | 3.12.14 in isolated `/tmp` venv |
| `compileall` | PASS |
| Ruff | 0.8.6, all checks passed |
| pytest | **114 passed, 0 failed** |
| Workflow regression | 9/9 |
| Package/server imports | PASS, `mkt_measurement_ops` v0.1.0 |
| MCP tools | 38 registered |
| WordPress PHP syntax | PASS, PHP 8.1.2 |
| GTM PREVIEW / WRITES / PUBLISH | All false |
| Production changes | None |

The report is provided by the external developer; raw local command logs are
not attached here and the authoring environment has not independently executed
the full suite. PHP was installed with verified Ubuntu package signatures
and package SHA256s in the Linux VM. The result is an **offline test result**,
not an end-to-end tracking certification.

## Important: this branch has newer code

After that validated SHA, a PR review found a cross-customer measurement risk:
the installer could accept a caller-supplied GA4 Measurement ID without ensuring
it matched the job site's registered GA4 property.

The branch now requires a registered GA4 property and verifies that every
Measurement ID override equals the actual web stream for the registered domain.
Regression tests in `tests/test_measurement_id_isolation.py` cover matching ID,
cross-customer rejection, missing property, and empty override.

**The prior 114/114 result must not be represented as covering this new HEAD.**
A fresh run of `python scripts/validate_local.py` on the current PR head is required.

## Commands: re-test current PR head

Use a clean, separate worktree of `origin/feature/measurement-ops-v0.1` and
Python 3.11+. Do not modify the production Ads checkout.

```bash
cd suite/measurement_ops
python -m pip install -e ".[dev,web]"
python -m playwright install chromium
export GTM_ENABLE_PREVIEW=false
export GTM_ENABLE_WRITES=false
export GTM_ENABLE_PUBLISH=false
git rev-parse HEAD
python scripts/validate_local.py
```

PHP must be available: the validator intentionally refuses to print GREEN if
WordPress bridge lint is skipped. The suite's `ruff==0.8.6` pin is mandatory.

## Still not covered by offline GREEN

- Official GTM API v2 authenticated discovery, pagination and account access.
- OAuth refresh-token scope adequacy for readonly / preview / writes / publish.
- GA4 Admin stream-domain matching and Data API realtime in a real account.
- WordPress plugin behavior on an actual WordPress 6.9+ install with Abilities API.
- Astro build / preview / deployment in an actual project.
- Event attribution, real consent, true success-only form tracking, duplication QA.
- Browser-auditor restricted-network isolation / DNS rebinding resistance.
- Publish concurrency, reconciliation and rollback against real GTM.
- Cross-account mutations and end-to-end release lifecycle.

Keep PR #14 as draft until the real pilots pass. **No GTM publish, production
site deploy or Ads mutations** are authorized by the offline test result.
