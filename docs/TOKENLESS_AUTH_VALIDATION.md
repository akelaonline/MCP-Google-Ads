# Tokenless auth — authorized live validation runbook

This procedure certifies real Google Ads API access **without a developer
token** on a test installation. It requires explicit owner authorization and
must run against an **authorized test account** — never a real client account
— on a non-production checkout (e.g. a `dev/` worktree with its own `.env` and
a temporary audit DB).

Do not run it against the production MCP installation. Do not run it against a
real client account under any circumstance.

## Preflight (no Google calls)

1. `python scripts/validate_local.py` is GREEN on the candidate commit.
2. The candidate `.env` contains `GOOGLE_ADS_CLIENT_ID`,
   `GOOGLE_ADS_CLIENT_SECRET` and `GOOGLE_ADS_REFRESH_TOKEN` from the OAuth
   client that belongs to the target Google Cloud project.
   `GOOGLE_ADS_DEVELOPER_TOKEN` is **empty or absent**.
3. An **explicit allowlist** restricts this validation instance to the
   authorized test customer only — no other account may be reachable:

   ```dotenv
   GOOGLE_ADS_MCP_ALLOWED_CUSTOMER_IDS=<authorized-test-customer-id>
   GOOGLE_ADS_MCP_REQUIRE_CUSTOMER_ALLOWLIST=true
   ```

4. In Google Cloud Console, for the project that owns the OAuth client:
   - **APIs & Services → Library → Google Ads API → Enabled**.
   - **Google Ads API → Overview** shows the project's access level:
     - `Test` — 15,000 ops/day, test accounts only.
     - `Explorer` — 2,880 ops/day on production accounts (automated approval).
     - `Basic` / `Standard` — higher-volume production levels.
   - If the target account is a real production account and the level is
     `Test`, stop here: apply for Explorer access first. A missing level is an
     **access problem**, not a developer-token problem — adding a token back
     will not help (the servers ignore it).
5. Run the MCP with `GOOGLE_ADS_MCP_READ_ONLY=true` for this validation.

## Part A — Read-only live checks (this runbook's only scope)

Execute each step and record tool name, result and timestamp:

1. `list_accessible_customers` (or the account-discovery tool) — confirms the
   OAuth identity + Cloud project access level resolve a customer set with **no
   developer token configured**. Verify only the allowlisted test customer is
   visible.
2. `get_campaign_performance` (or equivalent) against the authorized test
   customer — confirms GAQL/search path end to end.
3. `run_gaql_query` with `SELECT customer.id, customer.descriptive_name FROM
   customer LIMIT 5` — confirms raw GAQL path.
4. If an MCC/login customer ID is configured: repeat 1–3 through the manager
   and confirm `GOOGLE_ADS_LOGIN_CUSTOMER_ID` resolution still works tokenless.
5. **Negative write test** (read-only enforcement): attempt one write proposal
   (e.g. `create_campaign_budget` with a small amount on the test customer) and
   confirm the tool call is **rejected** by read-only policy before any Google
   Ads mutation. This proves the kill switch works on the tokenless install —
   nothing should reach Google.

## Expected evidence

- All read calls succeed with `GOOGLE_ADS_DEVELOPER_TOKEN` unset.
- The write proposal is blocked by `GOOGLE_ADS_MCP_READ_ONLY=true`.
- No `DEVELOPER_TOKEN`-related errors; the SDK (>=32) no longer validates it.
- Optional: keep the legacy token set on a second run and confirm identical
  behavior (servers ignore it either way).

## Out of scope — future write validation (separate authorization required)

Any `propose → confirm` execution, pending replay, audit-trail verification of
mutations, or live writes of any kind belong to a **different, separately
authorized** validation pass — with its own test account, approvals and
rollback notes. Do not fold them into this read-only check.

## If it fails

- `PERMISSION_DENIED` / `USER_PERMISSION_DENIED` with correct OAuth → the Cloud
  project lacks Google Ads API enablement or a sufficient access level for that
  account type. Fix in Cloud Console; it is not a code or token issue.
- OAuth errors (`invalid_grant`, `invalid_client`) → credential problem
  unrelated to tokenless auth; re-run the refresh-token flow in `SETUP.md`.
- The negative write test mutates anything → stop immediately and report: the
  read-only gate failed. Do not continue.
- Any error mentioning `developer_token` → report the exact message, SHA and
  `google-ads` lib version; that path should not exist on `google-ads>=32`.
