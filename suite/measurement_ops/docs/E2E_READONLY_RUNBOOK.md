# Measurement Ops — first authenticated read-only E2E

Target: a **disposable or explicitly authorized test** GTM/GA4 setup and one
WordPress or Astro URL. This is a read-only integration test, **not a rollout**.

## Preconditions

1. The current PR HEAD passes `python scripts/validate_local.py` in a clean
   isolated environment, including PHP lint.
2. Credentials belong to an account explicitly authorized for this test. Do not
   copy or print refresh tokens, client secrets or service-account JSON files.
3. The Google APIs and OAuth consent are configured for the exact requested
   readonly scopes. A Google Ads refresh token is **not automatically** valid for
   Tag Manager or Analytics; use separately consented credentials.
   Preferred bootstrap: **[desktop OAuth setup](OAUTH_READONLY_SETUP.md)**.
   Two private OAuth JSON files can replace the legacy six environment secrets.
   The loopback flow runs on the actual Mac with a local browser, not the cloud VM.
4. The server remains local stdio; do not expose HTTP without authentication.
5. The browser auditor must run in a restricted-network sandbox; its URL checks
   alone are not complete SSRF protection.

## Environment: deny all mutations

```bash
export GTM_ENABLE_PREVIEW=false
export GTM_ENABLE_WRITES=false
export GTM_ENABLE_PUBLISH=false
```

For GTM, create a readonly refresh token with
`https://www.googleapis.com/auth/tagmanager.readonly` and populate:

`GTM_GOOGLE_CLIENT_ID`, `GTM_GOOGLE_CLIENT_SECRET`,
`GTM_GOOGLE_REFRESH_TOKEN`.

For GA4, create a readonly refresh token with
`https://www.googleapis.com/auth/analytics.readonly` and populate:

`GA4_GOOGLE_CLIENT_ID`, `GA4_GOOGLE_CLIENT_SECRET`,
`GA4_GOOGLE_REFRESH_TOKEN`.

Alternatively, prefer the local browser helper in
`docs/OAUTH_READONLY_SETUP.md`. It writes provider-specific read-only JSON files
with private filesystem permissions and loads them automatically:

- `~/.mkt-measurement-ops/oauth/gtm-readonly.json`
- `~/.mkt-measurement-ops/oauth/ga4-readonly.json`

Load legacy env grants through a secure secret mechanism if used; never commit
`.env` and never paste token material into a chat.

## Read-only acceptance sequence

1. Start the `mkt-measurement-ops` MCP command in an isolated Claude client
   profile. Inspect `measurement_capabilities`: all mutation gates false.
2. `gtm_list_accounts` -> confirm only expected accessible accounts.
3. `gtm_list_containers(account_id)` -> record correct account/container
   identity and `GTM-XXXX` public ID.
4. `gtm_list_workspaces(account_id, container_id)`.
5. `gtm_audit_workspace(account_id, container_id, workspace_id)` -> verify
   tags/triggers/variables/status and live version against GTM UI.
6. Register a **test** site with the real host and intended provider IDs.
   `register_site` writes only to the **local SQLite registry**, not Google.
7. `ga4_resolve_site_web_stream(site_key)` -> Measurement ID must match the
   expected website and intended GA4 property; wrong-domain stream is blocked.
8. `audit_site_url(url)` and `audit_and_plan_site(site_key)` in an isolated
   browser environment -> compare discovered GTM/GA4 and form candidates with
   the actual site. Do not submit forms or click buttons in this phase.
9. `ga4_realtime_events(property_id)` -> verify readonly Data API access.
   Aggregate counts alone are **not** evidence of a test conversion.
10. Re-call `measurement_capabilities` and ensure all mutation gates remain
    false. Confirm no new GTM versions, workspaces, tags or live changes.

## Acceptance and blockers

- All methods complete without credential-scope, resource-path or API contract
  exceptions, and account/property identities are correct.
- Wrong customer/property identities cannot silently link or install tags.
- No Google or website mutations occur.
- Record only sanitized account IDs, timestamps, errors, tool names, and the
  PR HEAD in the report; never capture tokens, PII or secrets.

If authenticated discovery fails, correct OAuth/API access and rerun read-only.
Do **not** flip `GTM_ENABLE_WRITES` or `GTM_ENABLE_PUBLISH` to work around
a read-only error.

## Only after read-only passes

Separate, explicitly approved non-production pilots for:
- GTM workspace create / typed install / quick preview / compiler checks.
- WordPress Bridge installation in staging and real successful-form callbacks.
- Astro branch/build/preview/deployment and duplicate-tag prevention.
- Consent behavior; site-side browser network evidence; GA4 verification.
- A specific, approved GTM version publish and rollback/reconciliation.

Never merge the PR to the production Ads MCP merely because authenticated
read-only tests succeed.
