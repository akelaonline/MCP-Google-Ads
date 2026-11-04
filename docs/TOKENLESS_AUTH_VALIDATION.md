# Tokenless auth — authorized live validation runbook

This procedure certifies real Google Ads API access **without a developer
token** on a test installation. It requires explicit owner authorization and
must run against an authorized test account — never a client account — on a
non-production checkout (e.g. a `dev/` worktree with its own `.env` and a
temporary audit DB).

Do not run it against the production MCP installation.

## Preflight (no Google calls)

1. `python scripts/validate_local.py` is GREEN on the candidate commit.
2. The candidate `.env` contains `GOOGLE_ADS_CLIENT_ID`,
   `GOOGLE_ADS_CLIENT_SECRET` and `GOOGLE_ADS_REFRESH_TOKEN` from the OAuth
   client that belongs to the target Google Cloud project.
   `GOOGLE_ADS_DEVELOPER_TOKEN` is **empty or absent**.
3. In Google Cloud Console, for the project that owns the OAuth client:
   - **APIs & Services → Library → Google Ads API → Enabled**.
   - **Google Ads API → Overview** shows the project's access level:
     - `Test` — 15,000 ops/day, test accounts only.
     - `Explorer` — 2,880 ops/day on production accounts (automated approval).
     - `Basic` / `Standard` — higher-volume production levels.
   - If the target account is a real production account and the level is
     `Test`, stop here: apply for Explorer access first. A missing level is an
     **access problem**, not a developer-token problem — adding a token back
     will not help (the servers ignore it).
4. Run the MCP with `GOOGLE_ADS_MCP_READ_ONLY=true` for this validation.

## Read-only live checks

Execute each step and record tool name, arguments (customer IDs masked in the
report), result and timestamp:

1. `list_accessible_customers` (or the account-discovery tool) — confirms the
   OAuth identity + Cloud project access level resolve a customer set with **no
   developer token configured**.
2. `get_campaign_performance` (or equivalent) against the authorized test
   customer — confirms GAQL/search path end to end.
3. `run_gaql_query` with `SELECT customer.id, customer.descriptive_name FROM
   customer LIMIT 5` — confirms raw GAQL path.
4. If an MCC/login customer ID is configured: repeat 1–3 through the manager
   and confirm `GOOGLE_ADS_LOGIN_CUSTOMER_ID` resolution still works tokenless.
5. `propose` a harmless write (e.g. a paused budget) and **cancel** it —
   confirms the pending-action/audit path. Do not confirm any mutation during
   this validation unless separately authorized.
6. `get_recent_audit_log` — confirms the calls were recorded.

## Expected evidence

- All read calls succeed with `GOOGLE_ADS_DEVELOPER_TOKEN` unset.
- No `DEVELOPER_TOKEN`-related errors; the SDK (>=32) no longer validates it.
- Optional: keep the legacy token set on a second run and confirm identical
  behavior (servers ignore it either way).

## If it fails

- `PERMISSION_DENIED` / `USER_PERMISSION_DENIED` with correct OAuth → the Cloud
  project lacks Google Ads API enablement or a sufficient access level for that
  account type. Fix in Cloud Console; it is not a code or token issue.
- OAuth errors (`invalid_grant`, `invalid_client`) → credential problem
  unrelated to tokenless auth; re-run the refresh-token flow in `SETUP.md`.
- Any error mentioning `developer_token` → report the exact message, SHA and
  `google-ads` lib version; that path should not exist on `google-ads>=32`.
