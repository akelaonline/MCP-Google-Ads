# Measurement Ops v0.1 — Validation status

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
