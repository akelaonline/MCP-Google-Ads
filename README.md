<div align="center">

# Google Ads MCP

**Production-grade read/write Model Context Protocol server for Google Ads API v25.**

Operate Google Ads from Claude or any compatible MCP client with explicit confirmation,
SQLite audit, encrypted durable pending actions, MCC/customer isolation, a hard read-only
mode, and broad v25 coverage.

Built by [**Akela**](https://github.com/akelaonline)

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](pyproject.toml)
[![Google Ads API v25](https://img.shields.io/badge/Google%20Ads%20API-v25-4285F4.svg)](https://developers.google.com/google-ads/api)
[![Version](https://img.shields.io/badge/version-0.16.3-informational.svg)](docs/RELEASE_0.16.3.md)

[Quick start](#quick-start) · [Safety](#safety-by-default) · [Validation](#validation-before-production) · [Coverage](docs/V25_SERVICE_COVERAGE.md) · [Docs](#documentation)

</div>

---

## What this is

Google Ads MCP is a local MCP server designed to **operate**, not only report on, Google Ads accounts. Claude, an IDE agent, or another MCP-compatible client can use the same server.

It covers reporting and GAQL; campaign, budget and bidding operations; ads, assets, keywords and targeting; audiences and Customer Match; conversions/goals; Performance Max; experiments; Smart Campaigns; batch jobs; MCC/account access; billing/product links; planning; and specialist v25 services.

Every normal write follows:

```text
propose -> preview -> confirm -> execute -> audit
```

For reporting-only deployments:

```dotenv
GOOGLE_ADS_MCP_READ_ONLY=true
```

Read-only keeps reporting/GAQL/audit inspection available but blocks both new write proposals and confirmation of previously pending actions.

## Current validation target: 0.16.3

**0.16.3 is the version to test. Do not replace a known-good production MCP with 0.16.0, 0.16.1, or 0.16.2.**

The v0.16 line was deliberately validated iteratively in a real local dependency environment:

- **0.16.0**: failed server/tool import because `from_micros()` was missing; recursive MCC isolation also missed protobuf map/`Struct` values.
- **0.16.1**: restored server startup and fixed the recursive walker. A clean local run then collected **231 tests**, exposing 13 stale test-double failures and FastMCP warnings for duplicate public tool registration.
- **0.16.2**: synchronized the test clients with the production isolation contract and made public tool ownership deterministic. A clean local run then built the server cleanly (0 duplicate-tool warnings) but still reported 3 stale-fixture pytest failures and 22 Ruff findings.
- **0.16.3**: resolves the remaining 3 pytest failures and all 22 Ruff findings without weakening any safety or isolation behavior. `python scripts/validate_local.py` is green end-to-end (smoke, Ruff, 232/232 pytest) against this version.

See [`docs/RELEASE_0.16.3.md`](docs/RELEASE_0.16.3.md).

### Deterministic public tool ownership

The local re-test identified legacy/new implementations competing for the same names. 0.16.2 explicitly assigned the v25-complete runtime owners, unchanged in 0.16.3:

```text
list_asset_group_signals             -> pmax_signals_listing.py
add_asset_group_signal               -> pmax_signals_listing.py
list_asset_group_listing_filters     -> pmax_signals_listing.py
list_conversion_value_rules          -> remaining_core_services.py
create_conversion_value_rule         -> remaining_core_services.py
```

Legacy source definitions are not registered as public FastMCP tools. Any unexpected future duplicate public name now fails server construction rather than being silently overwritten by registration order.

## Safety by default

### MCC/customer isolation

Use an explicit deployment allowlist when one credential can reach several customers:

```dotenv
GOOGLE_ADS_MCP_ALLOWED_CUSTOMER_IDS=123-456-7890,987-654-3210
GOOGLE_ADS_MCP_REQUIRE_CUSTOMER_ALLOWLIST=true
```

The server:

- blocks customer-scoped reads/writes outside the allowlist;
- filters account discovery;
- filters `customer_client`, `customer_client_link`, and `customer_manager_link` rows, including raw GAQL;
- recursively inspects customer-scoped resource names in CREATE/UPDATE/REMOVE payloads, including protobuf maps/Structs and repeated/list fields;
- permits the intentional two-customer manager/client link only when both customers are allowlisted.

### Risk classes

Writes are classified as:

- `standard`
- `spend`
- `destructive`
- `sensitive`

Delivery-changing operations are conservative. Enabled keyword changes, targeting, conversion-biddability, live asset attachment, and editing an existing RSA are `spend` even when no explicit currency value appears in the request.

Recommended production policy:

```dotenv
GOOGLE_ADS_MCP_READ_ONLY=false
GOOGLE_ADS_MCP_AUTO_APPROVE=false
GOOGLE_ADS_MCP_AUTO_APPROVE_SPEND=false
GOOGLE_ADS_MCP_AUTO_APPROVE_DESTRUCTIVE=false
GOOGLE_ADS_MCP_AUTO_APPROVE_SENSITIVE=false
```

### Durable pending confirmations

Pending proposals are persisted in SQLite and replay arguments are encrypted with Fernet. Provide a stable key:

```dotenv
GOOGLE_ADS_MCP_PENDING_ENCRYPTION_KEY=<fernet-key>
```

or persist the generated `<audit-db>.pending.key` beside the DB. Missing/corrupt encryption state fails closed.

Use one running MCP process per `audit.db`; the pending-action lock is process-local, not distributed.

## Capabilities

| Domain | Coverage |
|---|---|
| Accounts & MCC | discovery/hierarchy, manager/client links, users/roles/invitations, customer settings |
| Reporting | campaigns, ad groups, ads, keywords, search terms, devices, geo, assets, audiences, shopping, change history, raw GAQL |
| Campaigns | Search, Standard Shopping, Performance Max, Demand Gen, Smart Campaigns |
| Budgets & bidding | budget lifecycle, Manual CPC, Max Clicks/Conversions/Value, CPA/ROAS/Impression Share, portfolio bidding, bid modifiers |
| Ads & assets | RSA, Responsive Display, Demand Gen, images/video/calls/sitelinks/callouts/snippets/promotions/Business Message/WhatsApp |
| Keywords & targeting | lifecycle, bids, match types, negatives, shared/account exclusions, location/language/device/audience/topic targeting |
| Audiences | remarketing, UserList, Customer Match, Audience, CustomAudience, CustomInterest |
| Conversions & goals | actions, offline/enhanced uploads, adjustments, custom variables, value rules/sets, unified v25 goals |
| Performance Max | campaign/asset groups/assets, signals, SHOPPING/RETAIL/WEBPAGE listing filters, brand guidelines, previews |
| Experiments | lifecycle, arms, schedule/errors/promote/graduate/end, atomic traffic split updates |
| Batch / Smart Bidding | controlled Batch Jobs, seasonality adjustments, data exclusions |
| Billing & links | payments accounts, billing setup, account budgets/invoices, ProductLink/Invitation, DataLink, YouTube/app analytics |
| Planning / specialist | Keyword Planner, Reach Planner, Travel/brand suggestions, Local Services, Identity, Incentives, SKAd visibility, YouTube upload |
| Access-controlled | Audience Insights, Benchmarks, Creator Insights; Asset Generation closed beta |

See [`docs/V25_SERVICE_COVERAGE.md`](docs/V25_SERVICE_COVERAGE.md) and [`docs/TOOLS.md`](docs/TOOLS.md).

## Quick start

```bash
git clone https://github.com/akelaonline/MCP-Google-Ads.git
cd MCP-Google-Ads
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e ".[dev]"
cp .env.example .env
```

Configure at least:

```dotenv
GOOGLE_ADS_DEVELOPER_TOKEN=
GOOGLE_ADS_CLIENT_ID=
GOOGLE_ADS_CLIENT_SECRET=
GOOGLE_ADS_REFRESH_TOKEN=
GOOGLE_ADS_LOGIN_CUSTOMER_ID=
```

Local stdio MCP example:

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

`stdio` is recommended. HTTP remains blocked by default; if deliberately enabled, place it behind your own authenticated/restricted boundary. `GOOGLE_ADS_MCP_ALLOW_INSECURE_HTTP=true` does **not** provide authentication.

## Validation before production

After pulling `main`, validate the exact local checkout **before** replacing a running MCP:

```bash
git fetch origin
git pull --ff-only origin main
source .venv/bin/activate
python -m pip install -e ".[dev]"
python scripts/validate_local.py
```

The validator runs:

```text
isolated offline smoke -> Ruff -> complete pytest
```

The smoke uses a temporary audit DB and read-only configuration, imports every tool module, builds the server, tests the `from_micros()` regression, exercises nested MCC map/list isolation, and verifies canonical tool ownership.

Only proceed when it ends with:

```text
LOCAL VALIDATION GREEN
validated commit: <sha>
validated version: 0.16.3
```

Then follow [`docs/VALIDATION_CHECKLIST.md`](docs/VALIDATION_CHECKLIST.md) for the live-account sequence: read-only checks, MCC isolation, propose/cancel, propose/confirm, durable restart replay, cross-customer blocking, legitimate manager/client linking, risk boundaries and double-confirm behavior.

This repository intentionally has **no GitHub Actions workflow**; validation is local/manual.

## Scope boundaries

This MCP wraps Google Ads API, not every adjacent Google advertising product.

- Merchant Center catalog/feed editing belongs to Merchant API; Ads-side linking and Shopping/PMax operations are covered here.
- Google Business Profile resource administration is separate.
- Legacy Smart Shopping should use Performance Max.
- Removed/unsupported legacy video writes are not emulated.
- Google beta/allowlisted services still require Google-side eligibility.
- `ReservationService` is not publicly available and is not faked.

## Documentation

- [0.16.3 release / re-test notes](docs/RELEASE_0.16.3.md)
- [Safe local update procedure](docs/UPDATE_LOCAL.md)
- [Production validation checklist](docs/VALIDATION_CHECKLIST.md)
- [Setup](docs/SETUP.md)
- [MCP clients](docs/CLIENTS.md)
- [Safety model](docs/SAFETY.md)
- [Tool reference](docs/TOOLS.md)
- [Google Ads API v25 coverage](docs/V25_SERVICE_COVERAGE.md)
- [Agency tools](docs/AGENCY_TOOLS.md)
- [Batch jobs & Smart Bidding](docs/BATCH_SMART_BIDDING.md)
- [Examples](docs/EXAMPLES.md)
- [FAQ](docs/FAQ.md)
- [Changelog](CHANGELOG.md)

## License

MIT. See [`LICENSE`](LICENSE).
