# 0.18.1 — corrective release candidate (offline-validated)

**Status: candidate. Not published, not deployed, not validated against live
Google services.** Authors: Alejandro José / Akela.

| Area | Change |
|---|---|
| `validate_only` | Now reaches the real request message. Before, the SDK stubs only flatten `customer_id` and the operations, so `validate_only=True` was silently dropped and a dry run became a real write. Services whose request has no `validate_only` (BillingSetup, CustomerUserAccess, CustomerUserAccessInvitation, BatchJob) are **refused before any RPC**. `partial_failure` policy unchanged per service. |
| Merchant API | Products/DataSources on `v1`; ID, field and MCQL fixes. See `docs/MERCHANT_V1_ONBOARDING.md`. |
| Merchant isolation | Separate Merchant scope, fail-closed, covers reads, writes, discovery, replay and Ads-side tools that name a Merchant account. |
| Retired by Google | `create_smart_campaign` (creation retired 2026-09-23) returns an "unsupported" result with zero mutations; `create_campaign` rejects SMART; `set_language_targeting` on Search no longer adds LANGUAGE criteria (Google rejects them) and cleans/refuses explicitly; other channels unchanged. Reads/updates of existing Smart campaigns remain. |
| December 2026 | PMax: proposals state the image-extraction default (OPTED_IN for new campaigns from 2026-12-04) and `create_performance_max_campaign` accepts optional `image_extraction`. Multi-party approvals (week of 2026-12-07): results carry `approval_state` = `PENDING_GOOGLE_AUTHORIZATION` / `COMPLETED`; "executed" only means Google accepted the call. Demand Gen: this server never sets `network_settings.target_content_network`, so nothing to change (guarded by a test). |
| Validator isolation | The offline battery (`validate_local.py`, pytest via `conftest.py`, smoke, lifecycle) runs hermetically: no inherited credentials, dotenv or audit DB. Previously a pytest that builds the real server created the DB named by `GOOGLE_ADS_MCP_AUDIT_DB`. Regressions use decoy config/DB/HOME and assert they stay intact. |
| Lab preflight | `scripts/lab_preflight.py` rewritten: runtime boolean semantics, strict allowlist and valid IDs, resolved/symlink-safe containment, explicit env file, private permissions. See `docs/REAL_VALIDATION_LAB.md`. |
| Install | `constraints-certified.txt` (google-ads 35.1.0, fastmcp 4.2.0 …) and `make install-certified`. FastMCP update check off by default. |
| Docs | v26 wording, v26.1/v26.2 correction in `RELEASE_0.18.0.md`, update/rollback and lab runbooks. |
| Tool catalogue | **463 tools, unchanged** (no tool added or removed; one optional argument added to `create_performance_max_campaign`). |

## Dependency states

* **Recommended**: the certified set in `constraints-certified.txt` (Python 3.13).
* **Candidate**: this release (0.18.1) until live validation passes.
* **Beta**: Merchant Center tools. **Experimental**: anything not listed.

## Needs a future test (not invented, not run)

* Demand Gen: after 2026-12-01 confirm creation without `target_content_network` and the ad-group channel controls on a test account.
* PMax: after 2026-12-04 confirm a new campaign created without `image_extraction` reports `OPTED_IN`.
* MPA: after the week of 2026-12-07 and v26.2 client libraries, confirm the deferred invitation (no resource name until approved) and `STALE_MULTI_PARTY_AUTH_REQUEST`.
