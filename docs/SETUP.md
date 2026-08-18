# Setup

This guide configures Google Ads MCP for Google Ads API v25, including the v0.13 production isolation policy.

## Requirements

- Python 3.11+
- Google Ads Developer Token
- Google Cloud OAuth 2.0 Desktop client
- OAuth refresh token with the `adwords` scope
- Optional MCC login customer ID when operating child accounts through a manager

Production mutations require the appropriate Google Ads API access level and account permissions.

## 1. Create the virtual environment

```bash
git clone https://github.com/akelaonline/MCP-Google-Ads.git
cd MCP-Google-Ads
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e .
cp .env.example .env
```

Verify the package before configuring an MCP host:

```bash
.venv/bin/python -c "import google_ads_mcp; print('OK', google_ads_mcp.__version__, google_ads_mcp.__file__)"
```

## 2. Google Ads Developer Token

Obtain the Developer Token from the Google Ads API Center in your manager account and add it to `.env`:

```dotenv
GOOGLE_ADS_DEVELOPER_TOKEN=...
```

Test access is suitable for test accounts. Production accounts require the Google access level appropriate for your use case.

## 3. OAuth Desktop client

In Google Cloud Console:

1. Create/select a project.
2. Enable the Google Ads API.
3. Configure the OAuth consent screen.
4. Create an OAuth client of type **Desktop app**.
5. Add the client ID and secret to `.env`:

```dotenv
GOOGLE_ADS_CLIENT_ID=...
GOOGLE_ADS_CLIENT_SECRET=...
```

## 4. Generate a refresh token

Install the optional auth dependency:

```bash
pip install -e ".[auth]"
```

Then run:

```bash
python -m google_ads_mcp.auth --generate-refresh-token
```

Complete the browser flow and copy the resulting refresh token into `.env`:

```dotenv
GOOGLE_ADS_REFRESH_TOKEN=...
```

Treat the refresh token like a password. Do not commit `.env`.

## 5. MCC / manager accounts

If the authenticated user reaches client accounts through an MCC, set the manager customer ID:

```dotenv
GOOGLE_ADS_LOGIN_CUSTOMER_ID=1234567890
```

Digits or the usual dashed display form are accepted; the MCP normalizes customer IDs before API calls.

## 6. Production customer isolation

A Google Ads OAuth identity or MCC can often see many accounts. For a deployment dedicated to one customer, explicitly scope the MCP:

```dotenv
GOOGLE_ADS_MCP_ALLOWED_CUSTOMER_IDS=123-456-7890
GOOGLE_ADS_MCP_REQUIRE_CUSTOMER_ALLOWLIST=true
```

For a controlled deployment that intentionally serves several customers:

```dotenv
GOOGLE_ADS_MCP_ALLOWED_CUSTOMER_IDS=123-456-7890,987-654-3210
GOOGLE_ADS_MCP_REQUIRE_CUSTOMER_ALLOWLIST=true
```

When an allowlist is configured, reads and writes outside it are blocked centrally and `list_accessible_customers()` is filtered. Strict mode refuses startup when the list is empty.

If you need `get_account_hierarchy()` against an MCC, include the MCC customer ID in the allowlist as well, because the hierarchy query is scoped to that manager customer.

Leaving both settings unset preserves the historical “all accounts reachable by these credentials” behavior. That is convenient for development but is not the recommended isolation model for customer-specific production instances.

## 7. Write safety defaults

Recommended production configuration:

```dotenv
GOOGLE_ADS_MCP_AUTO_APPROVE=false
GOOGLE_ADS_MCP_AUTO_APPROVE_SPEND=false
GOOGLE_ADS_MCP_AUTO_APPROVE_DESTRUCTIVE=false
GOOGLE_ADS_MCP_AUTO_APPROVE_SENSITIVE=false
GOOGLE_ADS_MCP_PENDING_TTL_MINUTES=30
GOOGLE_ADS_MCP_AUDIT_DB=
GOOGLE_ADS_MCP_TRANSPORT=stdio
GOOGLE_ADS_MCP_ALLOW_INSECURE_HTTP=false
```

With global auto-approve disabled, write tools create pending actions and the account changes only after `confirm_pending_action(action_id)`.

When global auto-approve is deliberately enabled, only `standard` risk writes execute automatically by default. Spend-changing, destructive, and sensitive/account-access operations each require their own explicit opt-in. This prevents one generic automation flag from authorizing every category of live-account change.

The default audit database is:

```text
~/.google_ads_mcp/audit.db
```

## 8. Claude Desktop / Claude Code

Use the virtualenv Python by **absolute path**. Do not rely on a bare `python` command because desktop MCP hosts may use a different `PATH`.

Example:

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

Restart the MCP client after changing its configuration.

First smoke request:

```text
List my accessible Google Ads customer IDs.
```

Then try a read-only query before any mutation:

```text
Show campaign performance for customer 123-456-7890 for the last 7 days.
```

## HTTP transport

HTTP is intentionally blocked by default because this server exposes read, write, and confirmation tools and does not bundle a remote authentication provider.

For normal local Claude use, keep:

```dotenv
GOOGLE_ADS_MCP_TRANSPORT=stdio
```

If you deliberately run it behind your own authenticated and network-restricted reverse proxy, HTTP requires explicit opt-in:

```dotenv
GOOGLE_ADS_MCP_TRANSPORT=http
GOOGLE_ADS_MCP_HTTP_PORT=8080
GOOGLE_ADS_MCP_ALLOW_INSECURE_HTTP=true
```

`ALLOW_INSECURE_HTTP=true` does **not** add authentication. It only acknowledges that you are providing the security boundary externally. Never expose the raw HTTP server publicly.

## Google Ads API version

The project pins the Python dependency to the tested 31.x client line and explicitly requests API `v25`.

This is intentional. Floating silently to the library's future default API version can break fields and enums without a code change.

When upgrading Google Ads API versions, update both the dependency range and the real-protobuf contract tests.

## Troubleshooting

### `ModuleNotFoundError: google_ads_mcp`

The most common cause is launching the MCP with the wrong Python executable.

Check:

```bash
/absolute/path/to/.venv/bin/python -c "import google_ads_mcp; print(google_ads_mcp.__file__)"
```

If the environment looks corrupted, rebuild it rather than patching individual files:

```bash
rm -rf .venv
python -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -e .
```

### Authentication error

Check that all four credential variables are present and that the refresh token was minted by the same OAuth client:

```dotenv
GOOGLE_ADS_DEVELOPER_TOKEN=
GOOGLE_ADS_CLIENT_ID=
GOOGLE_ADS_CLIENT_SECRET=
GOOGLE_ADS_REFRESH_TOKEN=
```

For MCC access, also verify `GOOGLE_ADS_LOGIN_CUSTOMER_ID`.

### Customer blocked by allowlist

If a request returns `outside GOOGLE_ADS_MCP_ALLOWED_CUSTOMER_IDS`, verify that the intended customer ID is included in the deployment's `.env`. Do not widen the list simply to make an unexpected ID work; first confirm which client/account the MCP instance is supposed to control.

### Startup says the customer allowlist is required but empty

You enabled strict isolation:

```dotenv
GOOGLE_ADS_MCP_REQUIRE_CUSTOMER_ALLOWLIST=true
```

Add the intended customer IDs to `GOOGLE_ADS_MCP_ALLOWED_CUSTOMER_IDS` or turn strict mode off only if the deployment is intentionally allowed to reach every account available to the credentials.

### A write returns `pending_confirmation` while AUTO_APPROVE is true

Check `risk_level`. In v0.13, spend, destructive, and sensitive actions remain confirmation-gated unless their corresponding high-risk auto-approve flag is explicitly enabled. This is expected production behavior.

### Confirmation fails transiently

A failed confirmation stays pending. Fix the underlying problem and retry the **same action ID**. The audit log records each attempt under that ID.

### Remote image URL rejected

Image tools only fetch public HTTPS images. Private/loopback/link-local hosts, non-HTTPS URLs, unsafe redirects, unsupported image MIME types, and oversized responses are rejected intentionally.

### HTTP startup is blocked

Use `stdio`, or explicitly configure `GOOGLE_ADS_MCP_ALLOW_INSECURE_HTTP=true` only when an external authenticated/restricted proxy is already protecting the endpoint.

## Validation

Developer/test install:

```bash
pip install -e ".[dev]"
python scripts/smoke_test.py
pytest tests/ -v
ruff check src tests scripts
```

The test suite includes real Google Ads v25 generated protobuf contract tests and does not require live account credentials for those contracts.
