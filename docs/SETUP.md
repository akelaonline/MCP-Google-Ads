# Setup

This guide configures Google Ads MCP **0.16.0** for Google Ads API v25.

## Requirements

- Python 3.11+
- Google Ads Developer Token
- Google Cloud OAuth 2.0 Desktop client
- OAuth refresh token with the `adwords` scope
- Optional MCC login customer ID when operating child accounts through a manager

Some Google services additionally require Google allowlisting/product eligibility.
See `V25_SERVICE_COVERAGE.md`.

## 1. Install

```bash
git clone https://github.com/akelaonline/MCP-Google-Ads.git
cd MCP-Google-Ads
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e .
cp .env.example .env
```

Verify:

```bash
.venv/bin/python -c "import google_ads_mcp; print('OK', google_ads_mcp.__version__, google_ads_mcp.__file__)"
```

Expected version for this release:

```text
0.16.0
```

## 2. Google Ads credentials

Add to `.env`:

```dotenv
GOOGLE_ADS_DEVELOPER_TOKEN=
GOOGLE_ADS_CLIENT_ID=
GOOGLE_ADS_CLIENT_SECRET=
GOOGLE_ADS_REFRESH_TOKEN=
GOOGLE_ADS_LOGIN_CUSTOMER_ID=
```

`GOOGLE_ADS_LOGIN_CUSTOMER_ID` is normally the MCC customer ID when the OAuth
identity reaches client accounts through a manager.

Customer IDs may be copied in dashed display form; the MCP normalizes them before
Google Ads API requests.

## 3. Generate a refresh token

```bash
pip install -e ".[auth]"
python -m google_ads_mcp.auth --generate-refresh-token
```

Complete the browser flow and place the returned token in:

```dotenv
GOOGLE_ADS_REFRESH_TOKEN=...
```

Treat the refresh token, OAuth secret and developer token as secrets. Never commit
`.env`.

## 4. Production customer isolation

A manager credential can usually access more accounts than one MCP instance should
control. Restrict the deployment explicitly:

```dotenv
GOOGLE_ADS_MCP_ALLOWED_CUSTOMER_IDS=123-456-7890,987-654-3210
GOOGLE_ADS_MCP_REQUIRE_CUSTOMER_ALLOWLIST=true
```

When configured:

- customer-scoped reads outside the list are blocked;
- writes outside the list are blocked;
- account discovery is filtered;
- MCC `customer_client` / `customer_client_link` rows are filtered to allowed child accounts;
- nested resource references in mutations are inspected for cross-customer mixing.

If the MCP needs to query an MCC hierarchy, include the manager customer itself in
the allowlist as well.

### Raw GAQL against MCC hierarchy resources

`run_gaql_query()` uses the same central isolation path. In an allowlisted
deployment, raw `customer_client` queries must select `customer_client.id`, and
raw `customer_client_link` queries must select `customer_client_link.client_customer`.
Those fields are needed to prove which child customer owns each returned row. If
they are omitted, the query fails closed rather than returning unfilterable
cross-client metadata.

### MCC link operations

A real manager/client invite necessarily references two accounts. 0.16 permits
that specific link creation only when the second customer also passes the
deployment allowlist. This does not weaken normal campaign/ad/asset isolation.

## 5. Choose a write mode

### A. Reporting-only / emergency freeze

For an MCP instance that must never mutate Google Ads:

```dotenv
GOOGLE_ADS_MCP_READ_ONLY=true
```

Reads, reports and GAQL remain available. New write proposals are blocked, and
`confirm_pending_action()` is also blocked — including for pending actions created
before a restart/config change. Existing pending actions may still be listed or
cancelled.

This is the strongest operational kill switch and is useful for:

- reporting-only agents;
- audits;
- staged rollouts;
- emergency freeze during an incident;
- read-only credentials/workflows shared with more users.

### B. Normal production writes with human confirmation — recommended

```dotenv
GOOGLE_ADS_MCP_READ_ONLY=false
GOOGLE_ADS_MCP_AUTO_APPROVE=false
GOOGLE_ADS_MCP_AUTO_APPROVE_SPEND=false
GOOGLE_ADS_MCP_AUTO_APPROVE_DESTRUCTIVE=false
GOOGLE_ADS_MCP_AUTO_APPROVE_SENSITIVE=false
GOOGLE_ADS_MCP_PENDING_TTL_MINUTES=30
```

Writes return a preview and `pending_action_id`; call
`confirm_pending_action(action_id)` to execute.

### C. Controlled unattended automation

If global auto-approve is deliberately enabled, only `standard` writes may execute
automatically by default. Spend/destructive/sensitive classes remain separately
gated unless explicitly opted in.

```dotenv
GOOGLE_ADS_MCP_AUTO_APPROVE=true
GOOGLE_ADS_MCP_AUTO_APPROVE_SPEND=false
GOOGLE_ADS_MCP_AUTO_APPROVE_DESTRUCTIVE=false
GOOGLE_ADS_MCP_AUTO_APPROVE_SENSITIVE=false
```

0.16 classifies delivery-changing actions conservatively. Adding enabled keywords,
changing match types/negatives, location/language/placement targeting,
audience/topic attachment and conversion-biddability changes are `spend` risk,
not ordinary `standard` writes.

## 6. Audit DB and durable pending actions

Default audit database:

```text
~/.google_ads_mcp/audit.db
```

Override it with:

```dotenv
GOOGLE_ADS_MCP_AUDIT_DB=/persistent/path/google-ads-mcp.db
```

0.16 stores pending proposals in SQLite so they can survive process restart. The
original MCP arguments required for replay are encrypted.

### One process per audit/pending DB

The server serializes pending list/confirm/cancel operations inside one running
process. The SQLite pending table is **not** a distributed claim/lease system.
Do not point multiple simultaneously running MCP processes/workers at the same
`audit.db`; give each process its own DB unless you add an external single-writer
or distributed claim mechanism.

### Recommended key for containers/servers

Generate once:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Set:

```dotenv
GOOGLE_ADS_MCP_PENDING_ENCRYPTION_KEY=<generated-key>
```

Keep that value stable across restarts.

### Automatic local key

If the environment variable is omitted, the MCP creates:

```text
<audit-db>.pending.key
```

Persist **both** files:

```text
/path/audit.db
/path/audit.db.pending.key
```

If the DB survives but the encryption key does not, old pending actions cannot be
replayed. Confirmation fails closed; it does not execute an unverified mutation.

## 7. Claude Desktop / Claude Code

Use the virtualenv Python by absolute path:

```json
{
  "mcpServers": {
    "google-ads": {
      "command": "/absolute/path/to/MCP-Google-Ads/.venv/bin/python",
      "args": ["-m", "google_ads_mcp.server"],
      "env": {
        "GOOGLE_ADS_MCP_ENV_FILE": "/absolute/path/to/MCP-Google-Ads/.env"
      }
    }
  }
}
```

Restart the MCP client after configuration changes.

Initial checks:

```text
List my accessible Google Ads customer IDs.
```

```text
Show campaign performance for customer 123-456-7890 for the last 7 days.
```

If write mode is enabled, verify the safety path:

```text
Propose pausing campaign 123. Do not confirm it.
```

Confirm `pending_confirmation` is returned before testing a live confirmation.

If read-only mode is enabled, the same mutation request should instead return a
read-only policy error without creating a pending action.

## 8. HTTP transport

Recommended:

```dotenv
GOOGLE_ADS_MCP_TRANSPORT=stdio
GOOGLE_ADS_MCP_ALLOW_INSECURE_HTTP=false
```

HTTP startup is blocked by default because the server exposes read, write and
confirmation tools and does not ship a remote identity provider.

Only behind your own authenticated/restricted proxy:

```dotenv
GOOGLE_ADS_MCP_TRANSPORT=http
GOOGLE_ADS_MCP_HTTP_PORT=8080
GOOGLE_ADS_MCP_ALLOW_INSECURE_HTTP=true
```

`ALLOW_INSECURE_HTTP=true` does not add authentication.

## 9. Upgrade an existing install to 0.16.0

Before upgrading a production container, verify that the audit DB and pending key
are persisted.

Then:

```bash
cd MCP-Google-Ads
git pull origin main
source .venv/bin/activate
pip install -e .
```

0.16 adds `cryptography>=42` as a runtime dependency.

For a conservative first restart after upgrade, you can start with:

```dotenv
GOOGLE_ADS_MCP_READ_ONLY=true
```

verify reports/account scope, then switch to normal confirmation mode only after
you are satisfied with the deployment.

## 10. Local validation before production

```bash
source .venv/bin/activate
pip install -e ".[dev]"
python scripts/smoke_test.py
ruff check src tests scripts
pytest -q
```

For an E2E live test, use a dedicated Google Ads test/customer account, restrict
`GOOGLE_ADS_MCP_ALLOWED_CUSTOMER_IDS`, and keep all high-risk auto-approve flags
false.

Recommended sequence:

1. start read-only and verify account discovery/reporting;
2. verify an attempted mutation is blocked in read-only mode;
3. switch to confirmation mode and propose a harmless write, then cancel;
4. propose a harmless write, then confirm;
5. propose a write, restart the MCP, then confirm the same pending ID;
6. when using an MCC, deliberately query hierarchy rows outside the allowlist and verify they are filtered;
7. deliberately try a campaign resource from another allowed customer and verify it is blocked;
8. separately test the legitimate manager/client-link flow if your deployment uses it.

## Troubleshooting

### `ModuleNotFoundError: google_ads_mcp`

The MCP host is usually launching the wrong Python. Check:

```bash
/absolute/path/to/.venv/bin/python -c "import google_ads_mcp; print(google_ads_mcp.__file__)"
```

### Authentication / `USER_PERMISSION_DENIED`

Verify credentials and, for MCC access, `GOOGLE_ADS_LOGIN_CUSTOMER_ID`.

### `outside GOOGLE_ADS_MCP_ALLOWED_CUSTOMER_IDS`

Do not widen the allowlist blindly. Confirm which account this MCP instance is
supposed to control and add only the intended customer.

### Raw MCC GAQL says an ownership field must be selected

Add `customer_client.id` when querying `FROM customer_client`, or
`customer_client_link.client_customer` when querying `FROM customer_client_link`.
The field is required only so the MCP can enforce the configured child-account
allowlist on every returned row.

### Write says the MCP is running in read-only mode

This is intentional when:

```dotenv
GOOGLE_ADS_MCP_READ_ONLY=true
```

Switch it to `false` only on an instance that is actually authorized to mutate
Google Ads. Restart the MCP client after changing the environment.

### Pending action is not durable

`list_pending_actions()` reports `durable`. The built-in SQLite `AuditLog` supports
durability. A custom minimal audit backend falls back to in-memory pending actions.

### Pending action cannot decrypt after restart

Restore the same `GOOGLE_ADS_MCP_PENDING_ENCRYPTION_KEY` or the generated
`<audit-db>.pending.key`. If the original key is lost, re-propose the action; the MCP
will not guess/decrypt with a replacement key.

### A beta/insight tool returns NOT_ALLOWLISTED

That is an account/API eligibility result from Google, not an indication that the
MCP tool is missing. See `V25_SERVICE_COVERAGE.md`.

### Remote image URL rejected

Only public HTTPS images are accepted. Private/loopback/link-local networks,
unsafe redirects, unsupported MIME types and oversized responses are intentionally
blocked.

### HTTP startup blocked

Use stdio, or explicitly opt into HTTP only when an external authenticated
security boundary already exists.

## Google Ads API version policy

The code explicitly requests Google Ads API `v25` instead of silently following a
future client-library default. Major Google Ads API upgrades require a contract
review because fields, enums and services can be removed or reshaped.

See:

- `RELEASE_0.16.0.md`
- `V25_SERVICE_COVERAGE.md`
- `SAFETY.md`
