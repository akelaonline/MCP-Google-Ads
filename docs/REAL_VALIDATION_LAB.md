# Real validation lab (preparation only)

Nothing in this document was executed. Real results are kept apart from offline
ones and are only reported as PASSED when actually run.

## Isolation rules

* Lab home: `~/.google_ads_mcp_lab/` with its own `.env`, audit DB and key.
  Never reuse the production `.env`, DB, `.pending.key` or credentials.
* `GOOGLE_ADS_MCP_READ_ONLY=true`, auto-approvals OFF, explicit allowlists
  (`GOOGLE_ADS_MCP_ALLOWED_CUSTOMER_IDS`, `GOOGLE_ADS_MCP_ALLOWED_MERCHANT_IDS`).
* Authenticated calls need specific written authorization from the owner.
  A read-only approval does **not** authorize write tests.
* Tokenless runbook: `docs/TOKENLESS_AUTH_VALIDATION.md`.

## Preflight (no secrets, no network)

`python scripts/lab_preflight.py` checks the lab layout, that secrets are not in
the repo, that read-only/allowlists are set and that the lab paths are distinct
from production. It prints only names and PASS/FAIL, never values.

## Status per capability

| Capability | Status | Blocker |
|---|---|---|
| Google Ads read-only | NOT RUN | Needs authorized test account + OAuth in the lab |
| Google Ads writes / validate_only against API | NOT RUN | Needs explicit write authorization on a test account |
| Merchant API v1 read-only | NOT RUN | Needs developer registration of the Cloud project (owner) + Merchant allowlist |
| Merchant writes | NOT RUN | Same + explicit write authorization |
| GTM / GA4 | NOT RUN | Out of scope for this release |
