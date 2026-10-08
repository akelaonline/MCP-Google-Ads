# Measurement Ops — local GTM + GA4 OAuth (read-only)

This is the one-time setup for the **authenticated read-only** Issue #15.
It does not enable GTM preview, writes, publish, Google Ads mutations or website deployment.

## 1. In Google Cloud Console

1. Create/select a Google Cloud project controlled by MKT, intended for testing.
2. Enable **Tag Manager API**, **Google Analytics Admin API**, and
   **Google Analytics Data API**.
3. Configure Google Auth Platform branding/audience/consent. If the app is
   External/Testing, add the Google account that will consent to the test users.
4. Create **two Desktop app OAuth clients**, one for GTM and one for GA4, to
   keep their grants and refresh tokens separate. Download each client JSON
   to a private location on the **local Mac** outside any Git repository.
5. The consenting Google account must independently have viewer access to an
   explicitly authorized GTM container and GA4 property. Cloud project IAM
   permissions do not automatically grant GTM/GA4 property access.

Scopes:
- GTM: `https://www.googleapis.com/auth/tagmanager.readonly`
- GA4 Admin + Data: `https://www.googleapis.com/auth/analytics.readonly`

Both are exactly read-only. No need for Ads credentials.

**Google OAuth Testing caveat:** an External/Testing consent configuration may
issue refresh tokens that expire after 7 days. This is fine for the POC but not
for unattended production usage. Review verification/publishing policy before
a permanent agency deployment.

## 2. Run from the Mac with its own browser

This helper uses Google's Desktop app loopback browser authorization. It will
not work transparently from an isolated Linux/cloud VM whose localhost is not
the Mac's browser localhost. Run on the actual desktop with its own loopback
port. A local Python 3.11+ environment is required.

```bash
cd MCP-Google-Ads/suite/measurement_ops
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[oauth]"

python scripts/authorize_readonly.py \
  --provider gtm \
  --client-secrets "/absolute/private/path/gtm-desktop-client.json"

python scripts/authorize_readonly.py \
  --provider ga4 \
  --client-secrets "/absolute/private/path/ga4-desktop-client.json"
```

Google displays **two separate** consent requests. Review the requested scope
and explicitly approve each. Do not paste access tokens, refresh tokens,
authorization codes or client secrets into chat, GitHub or Slack.

To deliberately rotate a grant, repeat with `--replace`.

## 3. Where the grants are stored

```text
~/.mkt-measurement-ops/oauth/
    gtm-readonly.json
    ga4-readonly.json
```

The OAuth subdirectory requires mode `0700`; grant files use mode `0600`
and atomic replacement. Loading rejects symbolic links, excessive POSIX
permissions, missing refresh credentials and mismatched/privileged scopes.

If using a custom secret store or external volume instead, set
`GTM_GOOGLE_CREDENTIALS_FILE` and `GA4_GOOGLE_CREDENTIALS_FILE`
to the **absolute** private file paths. The legacy six OAuth variables are
still supported for compatible deployments, but are not recommended for
interactive setup. The same refresh token must not be shared between GTM
and GA4.

Only an authorized user can grant/revoke access. To revoke the OAuth grant,
use Google Account's third-party connections/security settings.

## 4. Run read-only E2E (Issue #15)

Before invoking the MCP:
```bash
export GTM_ENABLE_PREVIEW=false
export GTM_ENABLE_WRITES=false
export GTM_ENABLE_PUBLISH=false
```

Run the server from the authorized local user environment:
```bash
mkt-measurement-ops
```

From the MCP client use these tools **in order**:

1. `measurement_capabilities`. `gtm_readonly_configured` and
   `ga4_readonly_configured` should be true; that is only local configuration,
   **not proof of Google API connectivity**. Mutation gates remain false.
2. `gtm_list_accounts`.
3. `gtm_list_containers` for the approved test account.
4. `gtm_list_workspaces`, then `gtm_audit_workspace` for the selected test container.
5. `register_site` with test-only domain/GA4 property/container metadata.
6. `ga4_resolve_site_web_stream`. Confirm the exact domain + measurement ID.
7. `ga4_realtime_events` in read-only mode.
8. Web auditing only in a network-restricted browser environment and for an
   explicitly approved public URL. Do not click or submit anything.
9. Confirm all mutation gates still false and zero site/Google changes.

Record sanitized logs and exact repo HEAD. Close Issue #15 only if the live
API calls truly pass; keep PR #14 draft until later staged WP/Astro pilots pass.

## Troubleshooting

- `invalid_grant`: revoked/expired refresh token or mismatched OAuth client.
- `access_denied`: user did not consent, isn't added as test user, or lacks
  GTM/GA4 permissions.
- `403`: API disabled, insufficient permission or quota; check which.
- `redirect_uri_mismatch`: wrong OAuth client type or desktop callback setup.
- `OAuth credential scopes do not match`: use a dedicated Desktop OAuth
  client for each provider and consent only its expected read-only scope.
- `chmod 600`: grant file permission is too broad; adjust access locally.
- A browser redirect to a different machine's localhost will not work; run the
  Desktop OAuth helper on the machine hosting that loopback listener.

Never solve these errors by enabling GTM writes or publish.
