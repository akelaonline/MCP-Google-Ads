# Setup

This guide configures Google Ads MCP **0.16.3** for Google Ads API v25.

> **Validation target:** use `0.16.3`. Do not replace a working production MCP with `0.16.0`, `0.16.1`, or `0.16.2`. Run the local validation gate first; see `RELEASE_0.16.3.md`.

## Requirements

- Python 3.11+
- Google Ads Developer Token
- Google Cloud OAuth 2.0 Desktop client
- OAuth refresh token with the `adwords` scope
- Optional MCC login customer ID when operating child accounts through a manager

Some Google services additionally require Google allowlisting/product eligibility. See `V25_SERVICE_COVERAGE.md`.

## 1. Install

```bash
git clone https://github.com/akelaonline/MCP-Google-Ads.git
cd MCP-Google-Ads
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e ".[dev]"
cp .env.example .env
```

Verify:

```bash
.venv/bin/python -c "import google_ads_mcp; print('OK', google_ads_mcp.__version__, google_ads_mcp.__file__)"
```

Expected version:

```text
0.16.3
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

`GOOGLE_ADS_LOGIN_CUSTOMER_ID` is normally the MCC customer ID when the OAuth identity reaches client accounts through a manager. Customer IDs may be copied in dashed display form; the MCP normalizes them.

To generate a refresh token:

```bash
pip install -e ".[auth]"
python -m google_ads_mcp.auth --generate-refresh-token
```

Never commit `.env`.

## 3. Production customer isolation

A manager credential can usually access more accounts than one MCP instance should control. Restrict each deployment explicitly:

```dotenv
GOOGLE_ADS_MCP_ALLOWED_CUSTOMER_IDS=123-456-7890,987-654-3210
GOOGLE_ADS_MCP_REQUIRE_CUSTOMER_ALLOWLIST=true
```

When configured:

- customer-scoped reads and writes outside the list are blocked;
- account discovery is filtered;
- MCC `customer_client`, `customer_client_link`, and `customer_manager_link` rows are filtered to allowed referenced accounts;
- mutation payloads are recursively inspected for cross-customer resource references, including protobuf maps/Structs and repeated/list values.

If the MCP queries an MCC hierarchy, include the manager customer itself in the allowlist.

### Raw GAQL against MCC hierarchy resources

In an allowlisted deployment:

- `FROM customer_client` must select `customer_client.id`;
- `FROM customer_client_link` must select `customer_client_link.client_customer`;
- `FROM customer_manager_link` must select `customer_manager_link.manager_customer`.

The MCP needs those fields to prove ownership of each relationship row. Queries that omit them fail closed rather than returning ambiguous cross-client metadata.

### MCC link operations

A legitimate manager/client invite references two accounts. That narrow operation is permitted only when both customers are inside the deployment allowlist. Normal campaign/ad/asset operations remain same-customer only.

## 4. Choose a write mode

### Reporting-only / emergency freeze

```dotenv
GOOGLE_ADS_MCP_READ_ONLY=true
```

Reads, reports and GAQL remain available. New write proposals and confirmation of existing pending actions are blocked. Pending actions may still be inspected/cancelled.

### Normal production writes with human confirmation — recommended

```dotenv
GOOGLE_ADS_MCP_READ_ONLY=false
GOOGLE_ADS_MCP_AUTO_APPROVE=false
GOOGLE_ADS_MCP_AUTO_APPROVE_SPEND=false
GOOGLE_ADS_MCP_AUTO_APPROVE_DESTRUCTIVE=false
GOOGLE_ADS_MCP_AUTO_APPROVE_SENSITIVE=false
GOOGLE_ADS_MCP_PENDING_TTL_MINUTES=30
```

Writes return a preview and `pending_action_id`; `confirm_pending_action(action_id)` performs the mutation.

### Controlled unattended automation

```dotenv
GOOGLE_ADS_MCP_AUTO_APPROVE=true
GOOGLE_ADS_MCP_AUTO_APPROVE_SPEND=false
GOOGLE_ADS_MCP_AUTO_APPROVE_DESTRUCTIVE=false
GOOGLE_ADS_MCP_AUTO_APPROVE_SENSITIVE=false
```

Only `standard` writes auto-execute by default. Delivery-changing actions such as enabled keyword changes, targeting, conversion-biddability, live asset attachment and editing an existing RSA are classified as `spend`. Ads explicitly prepared `PAUSED` may remain `standard`.

## 5. Audit DB and durable pending actions

Default:

```text
~/.google_ads_mcp/audit.db
```

Override:

```dotenv
GOOGLE_ADS_MCP_AUDIT_DB=/persistent/path/google-ads-mcp.db
```

Pending proposals are persisted in SQLite and replay arguments are encrypted. Generate a stable Fernet key for containers/servers:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

```dotenv
GOOGLE_ADS_MCP_PENDING_ENCRYPTION_KEY=<generated-key>
```

If omitted, the MCP creates `<audit-db>.pending.key`. Persist both DB and key. If the key is unavailable/corrupt, confirmation fails closed.

One running MCP process should own one `audit.db`; the pending lock is process-local, not a distributed claim mechanism.

## 6. Claude / any MCP client

The server is client-agnostic. Claude, IDE agents, or any compatible MCP client can operate the same server.

Recommended local transport is stdio using the virtualenv Python by absolute path:

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

Restart the MCP client after code/config changes.

Initial checks:

```text
List my accessible Google Ads customer IDs.
Show campaign performance for customer 123-456-7890 for the last 7 days.
Propose pausing campaign 123. Do not confirm it.
```

See `CLIENTS.md` for connection patterns.

## 7. HTTP transport

Recommended:

```dotenv
GOOGLE_ADS_MCP_TRANSPORT=stdio
GOOGLE_ADS_MCP_ALLOW_INSECURE_HTTP=false
```

HTTP startup is blocked by default because the server exposes read/write/confirmation tools and does not ship a remote identity provider.

Only behind your own authenticated/restricted boundary:

```dotenv
GOOGLE_ADS_MCP_TRANSPORT=http
GOOGLE_ADS_MCP_HTTP_PORT=8080
GOOGLE_ADS_MCP_ALLOW_INSECURE_HTTP=true
```

`ALLOW_INSECURE_HTTP=true` is only a startup opt-in. It does not add authentication.

## 8. Upgrade an existing installation to the 0.16.3 test candidate

Preserve `.env`, the audit DB and the pending encryption key.

```bash
cd MCP-Google-Ads
git fetch origin
git pull --ff-only origin main
source .venv/bin/activate
python -m pip install -e ".[dev]"
python scripts/validate_local.py
```

The validator runs isolated smoke + Ruff + full pytest. **Do not replace the running production MCP unless it ends with `LOCAL VALIDATION GREEN` and reports version `0.16.3`.**

The smoke stage also verifies that these formerly duplicated public names have one canonical runtime owner and produce no FastMCP duplicate-registration warning:

- `list_asset_group_signals`
- `add_asset_group_signal`
- `list_asset_group_listing_filters`
- `list_conversion_value_rules`
- `create_conversion_value_rule`

See `UPDATE_LOCAL.md` for the full safe-update procedure.

## 9. Live validation after the local gate is green

Start the candidate with:

```dotenv
GOOGLE_ADS_MCP_READ_ONLY=true
```

Then follow `VALIDATION_CHECKLIST.md` in order:

1. account discovery/reporting/GAQL;
2. read-only write rejection;
3. MCC hierarchy read isolation;
4. propose/cancel;
5. propose/confirm;
6. restart/durable replay;
7. cross-customer mutation blocking;
8. legitimate manager/client link exception;
9. PMax/conversion canonical tool checks;
10. auto-approve risk boundaries;
11. double-confirm protection.

## Troubleshooting

### `ImportError: cannot import name 'from_micros'`

That was a 0.16.0 regression. Update to 0.16.3, reinstall the editable package, and verify `google_ads_mcp.__version__`.

### FastMCP prints `Component already exists`

0.16.3 should not emit duplicate public-tool warnings for the known PMax/ConversionValueRule names. If it does, stop validation and report the exact warning plus Git SHA; do not proceed to live writes.

### `ModuleNotFoundError: google_ads_mcp`

The MCP host is usually launching the wrong Python:

```bash
/absolute/path/to/.venv/bin/python -c "import google_ads_mcp; print(google_ads_mcp.__file__)"
```

### Authentication / `USER_PERMISSION_DENIED`

Verify credentials and, for MCC access, `GOOGLE_ADS_LOGIN_CUSTOMER_ID`.

### `outside GOOGLE_ADS_MCP_ALLOWED_CUSTOMER_IDS`

Do not widen the allowlist blindly. Add only accounts this MCP instance is intended to control.

### Pending action cannot decrypt after restart

Restore the same `GOOGLE_ADS_MCP_PENDING_ENCRYPTION_KEY` or generated `<audit-db>.pending.key`. If the original key is lost, re-propose the action; the MCP will not guess.

### Beta/insight tool returns `NOT_ALLOWLISTED`

That is Google-side eligibility, not a missing MCP tool. See `V25_SERVICE_COVERAGE.md`.

## API version policy

The code explicitly requests Google Ads API `v25`. Major API upgrades require contract review because fields, enums and services can be removed or reshaped.

See:

- `RELEASE_0.16.3.md`
- `UPDATE_LOCAL.md`
- `VALIDATION_CHECKLIST.md`
- `V25_SERVICE_COVERAGE.md`
- `SAFETY.md`
