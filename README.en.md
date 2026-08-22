<div align="center">

<a href="README.md"><img src="https://img.shields.io/badge/🇦🇷_🇪🇸-Español-6DA544?style=for-the-badge" alt="Español"></a>
<a href="README.en.md"><img src="https://img.shields.io/badge/🇬🇧_🇺🇸-English-00246B?style=for-the-badge" alt="English"></a>

# Google Ads MCP

**The MCP server that operates Google Ads from Claude — not just reads it.**

Reporting, campaigns, budgets, audiences, conversions and Performance Max, always under your control: every write is proposed, previewed, and waits for your confirmation before it ever touches a real account.

Built and maintained by [**Akela**](https://github.com/akelaonline)

[![License: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](pyproject.toml)
[![Google Ads API v25](https://img.shields.io/badge/Google%20Ads%20API-v25-4285F4.svg)](https://developers.google.com/google-ads/api)
[![Version](https://img.shields.io/badge/version-0.16.8-informational.svg)](docs/RELEASE_0.16.8.md)
[![Tests](https://img.shields.io/badge/tests-346%2F346-success.svg)](docs/RELEASE_0.16.8.md)

[Quick start](#quick-start) · [Safety](#safety-by-default) · [Validation](#validation-before-production) · [Coverage](docs/V25_SERVICE_COVERAGE.md) · [Docs](#documentation)

</div>

---

## What this is

**Google Ads MCP** is a [Model Context Protocol](https://modelcontextprotocol.io) server that connects Claude — or any compatible MCP client — directly to the Google Ads API v25, built to **operate** accounts, not just report on them.

Built for agencies and account managers running **Google Ads and Meta Ads** campaigns from the same AI assistant: reporting and raw GAQL; campaign, budget, and bidding operations; ads, assets, keywords, and targeting; audiences and Customer Match; conversions and goals; Performance Max; experiments; Smart Campaigns; batch jobs; MCC/account access; billing and product links; planning; and specialist v25 services.

Keywords: *AI-powered Google Ads automation, PPC campaign management with Claude, MCP server for digital advertising, AI ad spend control, digital marketing agency with Claude, Google Ads API v25 integration, AI assistant for Google Ads.*

Every real write follows the same path, no shortcuts:

```text
propose -> preview -> confirm -> execute -> audit
```

For reporting-only deployments:

```dotenv
GOOGLE_ADS_MCP_READ_ONLY=true
```

Read-only keeps reporting, GAQL, and audit inspection available, but blocks both new write proposals and confirmation of previously pending actions.

## Why trust this tool

- **Never executes without your confirmation.** Every write sits "pending" until you explicitly approve it — nothing hits a real account by accident.
- **Verified client isolation.** If you manage multiple accounts through an MCC, the server blocks — before ever calling Google — any operation that tries to mix resources from two different customers.
- **Full, reversible audit trail.** Every proposed, confirmed, or cancelled action is logged; pending actions survive even a server restart.
- **Validated against real production accounts**, not just in theory: every version passes an automated test suite (346/346 on 0.16.8) plus a manual live-account validation pass before being recommended for daily use.

## Current version: 0.16.8

**0.16.8 is the recommended version today.** Do not replace a working production installation with 0.16.0, 0.16.1, or 0.16.2 — those had known issues fixed in later releases.

The v0.16 line was validated iteratively, always against a real local environment:

- **0.16.0**: failed server import (missing `from_micros()`); recursive MCC isolation also missed protobuf map/`Struct` values.
- **0.16.1**: fixed startup and the recursive walker. A clean local run then collected **231 tests**, exposing 13 stale test-double failures and duplicate-tool-registration warnings.
- **0.16.2**: synchronized test clients with the real isolation contract and made public tool ownership deterministic. The server built cleanly (0 duplicate warnings), but 3 fixture failures and 22 Ruff findings remained.
- **0.16.3**: resolves the remaining 3 pytest failures and all 22 Ruff findings without weakening any safety behavior. `validate_local.py` is green end-to-end (smoke, Ruff, 232/232 pytest).
- **0.16.4**: closes functional gaps — ad schedule update/remove, tracking URL options (account/campaign/ad group), call conversion uploads, full App Campaigns (v25 `MULTI_CHANNEL`), Dynamic Search Ads. Also fixes four latent v25 contract bugs, plus a new test that verifies every service/method the codebase uses against the real v25 stubs.
- **0.16.5**: GDPR consent on offline/enhanced uploads, lost impression-share reporting, Standard Shopping listing groups, per-campaign ad rotation.
- **0.16.6**: extended assets (lead form, price, location, mobile app, deep link), positive placement targeting, frequency caps, audience exclusions at campaign/ad-group level, conversion custom variables.
- **0.16.7**: minor gaps — excluded asset field types per campaign, campaign dates, change-history filters, CPC bid ceiling/floor on Target CPA/ROAS.
- **0.16.8**: fixes a silent duplicate-tool registration bug — only explicitly declared legacy modules may be skipped; `create_conversion_value_rule` is now owned by `conversions.py` (typed conditions), with the protobuf-JSON variant exposed separately as `create_conversion_value_rule_from_json`. Guarded by a dedicated registry regression test.

`python scripts/validate_local.py` is green end-to-end (smoke, Ruff, **346/346 pytest**) on 0.16.8 — also validated with a real end-to-end pass against a live Google Ads account: read-only mode, cross-customer isolation, propose/cancel, propose/confirm, and durable pending-action replay after a restart.

See [`docs/RELEASE_0.16.8.md`](docs/RELEASE_0.16.8.md) and the per-version release notes for 0.16.4–0.16.7 in [`docs/`](docs/).

### Deterministic public tool ownership

```text
list_asset_group_signals             -> pmax_signals_listing.py
add_asset_group_signal               -> pmax_signals_listing.py
list_asset_group_listing_filters     -> pmax_signals_listing.py
create_conversion_value_rule         -> conversions.py        (typed conditions)
list_conversion_value_rules          -> remaining_core_services.py (rich read)
```

Only modules explicitly declared as superseded legacy may be skipped silently — any other module competing for the same public name fails server construction instead of being lost without a trace. Guarded by a regression test that builds the real assembled server and asserts no undeclared duplicate exists anywhere in the tree.

## Safety by default

### MCC / customer isolation

Use an explicit deployment allowlist when one credential can reach several customers:

```dotenv
GOOGLE_ADS_MCP_ALLOWED_CUSTOMER_IDS=123-456-7890,987-654-3210
GOOGLE_ADS_MCP_REQUIRE_CUSTOMER_ALLOWLIST=true
```

The server:

- blocks customer-scoped reads/writes outside the allowlist;
- filters account discovery;
- filters `customer_client`, `customer_client_link`, and `customer_manager_link` rows, including raw GAQL;
- recursively inspects customer-scoped resource references in every CREATE/UPDATE/REMOVE payload, including protobuf maps/Structs and repeated/list fields;
- permits the intentional two-customer manager/client link only when both customers are allowlisted.

### Risk classes

Every write is classified as:

- `standard`
- `spend`
- `destructive`
- `sensitive`

Delivery-changing operations are conservative. Enabled keyword changes, targeting, conversion-biddability, and live asset attachment are classified `spend` even when no explicit currency value appears in the request.

Recommended production policy:

```dotenv
GOOGLE_ADS_MCP_READ_ONLY=false
GOOGLE_ADS_MCP_AUTO_APPROVE=false
GOOGLE_ADS_MCP_AUTO_APPROVE_SPEND=false
GOOGLE_ADS_MCP_AUTO_APPROVE_DESTRUCTIVE=false
GOOGLE_ADS_MCP_AUTO_APPROVE_SENSITIVE=false
```

### Durable pending confirmations

Pending proposals are persisted in SQLite, and replay arguments are encrypted with Fernet. Provide a stable key:

```dotenv
GOOGLE_ADS_MCP_PENDING_ENCRYPTION_KEY=<fernet-key>
```

or let the server generate `<audit-db>.pending.key` beside the database. Missing or corrupt encryption state fails closed — nothing executes.

Run one MCP process per `audit.db`; the pending-action lock is process-local, not distributed.

## Capabilities

| Domain | Coverage |
|---|---|
| Accounts & MCC | discovery/hierarchy, manager/client links, users/roles/invitations, customer settings |
| Reporting | campaigns, ad groups, ads, keywords, search terms, devices, geo, assets, audiences, shopping, impression share / lost-IS, change history (with filters), raw GAQL |
| Campaigns | Search, Standard Shopping (incl. listing groups), Performance Max, Demand Gen, **App campaigns**, **Dynamic Search Ads**, Smart Campaigns, ad rotation, frequency caps, campaign dates |
| Budgets & bidding | budget lifecycle, Manual CPC, Max Clicks/Conversions/Value, CPA/ROAS/Impression Share (+ CPC ceiling/floor), portfolio bidding, bid modifiers |
| Ads & assets | RSA, Responsive Display, Demand Gen, images/video/calls/sitelinks/callouts/snippets/promotions/WhatsApp/**lead form/price/location/mobile app/deep link** |
| Keywords & targeting | lifecycle, bids, match types, negatives, shared/account exclusions, location/language/device/audience/topic targeting, **positive placements**, **audience exclusions**, ad schedules, tracking URL options |
| Audiences | remarketing, UserList, Customer Match, Audience, CustomAudience, CustomInterest |
| Conversions & goals | actions, offline/**call**/enhanced uploads (**GDPR consent**, custom variables), adjustments, value rules/sets, unified v25 goals |
| Performance Max | campaign/asset groups/assets, signals, listing filters, brand guidelines, previews |
| Experiments | lifecycle, arms, schedule/errors/promote/graduate/end, atomic traffic split updates |
| Batch / Smart Bidding | controlled Batch Jobs, seasonality adjustments, data exclusions |
| Billing & links | payments accounts, billing setup, account budgets/invoices, product links, YouTube/app analytics |
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

The smoke stage uses a temporary audit DB and read-only configuration, imports every tool module, builds the server, tests the `from_micros()` regression, exercises nested MCC map/list isolation, and verifies canonical tool ownership.

Only proceed when it ends with:

```text
LOCAL VALIDATION GREEN
validated commit: <sha>
validated version: 0.16.8
```

Then follow [`docs/VALIDATION_CHECKLIST.md`](docs/VALIDATION_CHECKLIST.md) for the live-account sequence: read-only checks, MCC isolation, propose/cancel, propose/confirm, durable restart replay, cross-customer blocking, legitimate manager/client linking, risk boundaries, and double-confirm behavior.

This repository intentionally has **no GitHub Actions workflow**; validation is local/manual.

## Scope boundaries

This MCP wraps the Google Ads API, not every adjacent Google advertising product.

- Merchant Center catalog/feed editing belongs to the Merchant API; Ads-side linking and Shopping/PMax operations are covered here.
- Google Business Profile resource administration is separate.
- Legacy Smart Shopping should use Performance Max.
- Removed/unsupported legacy video writes are not emulated.
- Google beta/allowlisted services still require Google-side eligibility.
- `ReservationService` is not publicly available and is not faked.

## Documentation

- [0.16.8 release notes](docs/RELEASE_0.16.8.md)
- [0.16.7 release notes](docs/RELEASE_0.16.7.md)
- [0.16.6 release notes](docs/RELEASE_0.16.6.md)
- [0.16.5 release notes](docs/RELEASE_0.16.5.md)
- [0.16.4 release notes](docs/RELEASE_0.16.4.md)
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
