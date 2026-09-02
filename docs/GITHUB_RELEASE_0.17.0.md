# v0.17.0 — Google Merchant Center support (beta)

![Google Ads MCP by Alejandro José · Akela](assets/google-ads-mcp-akela.svg)

**Operate Google Ads from Claude — don't just read it.**

Google Ads MCP 0.17.0 adds Google Merchant Center coverage to the same self-hosted MCP server: account diagnostics, product catalog, product writes, and feed/data-source management over the new Merchant API, using the same `propose → preview → confirm → execute → audit` safety model as every Google Ads write tool.

## Highlights

- ✅ **16 new Merchant Center tools** — accounts, products, product writes, data sources, MCQL reporting
- ✅ **Google Ads API v25**, unchanged
- ✅ **362/362 pytest** (16 new)
- ✅ **Ruff clean**
- ✅ **Isolated smoke green** — 56 tool modules
- ✅ Same propose/confirm/audit safety model, reused as-is
- ✅ Read-only kill switch also covers Merchant Center writes
- ⚠️ Merchant Center tools are **beta**: validated locally (unit tests + smoke), not yet live-tested against a real Merchant Center account

## What changed in 0.17.0

Google's legacy Content API for Shopping (`content.googleapis.com`) sunset on 2026-08-18. This release adds a minimal REST client for its replacement, the Merchant API (`merchantapi.googleapis.com`), and 16 tools built on it:

```text
get_merchant_center_configuration
list_merchant_center_accounts
get_merchant_center_account
list_merchant_center_sub_accounts
list_merchant_center_account_issues
list_merchant_center_products
get_merchant_center_product
list_merchant_center_product_issues
get_merchant_center_product_performance
search_merchant_center_reports
insert_merchant_center_product
remove_merchant_center_product
list_merchant_center_datasources
get_merchant_center_datasource
fetch_merchant_center_datasource
```

Merchant Center reuses the existing Google Ads OAuth client. Generate one refresh token covering both APIs with:

```bash
python -m google_ads_mcp.auth --generate-refresh-token --include-merchant-center
```

or point `GOOGLE_MERCHANT_CENTER_REFRESH_TOKEN` at a separate token if Merchant Center access lives on a different Google account. Optional `GOOGLE_MERCHANT_CENTER_ID` sets a default account ID so tool calls can omit `merchant_id`.

Product and data-source writes go through the same safety layer as Google Ads: `insert_merchant_center_product` and `fetch_merchant_center_datasource` propose first, `remove_merchant_center_product` is classified DESTRUCTIVE risk and gated behind `GOOGLE_ADS_MCP_AUTO_APPROVE_DESTRUCTIVE`. `GOOGLE_ADS_MCP_READ_ONLY=true` blocks every Merchant Center write the same way it already blocks Google Ads writes.

## Validation

```text
isolated smoke  → SMOKE OK (56 tool modules)
ruff check      → All checks passed
pytest -q       → 362 passed
```

Validation for this release is local only: unit tests use a fake Merchant Center client, and the smoke test confirms the server boots and registers every tool. Unlike 0.16.8, this release has **not** yet been exercised against a real Merchant Center account. Read-only tools first is the recommended way to validate against your own account before enabling writes.

## Install

```bash
git clone https://github.com/akelaonline/MCP-Google-Ads.git
cd MCP-Google-Ads
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e ".[dev]"
cp .env.example .env
```

Then follow the step-by-step tutorial in the README.

## Upgrade

Preserve your `.env`, audit DB and pending-action encryption key:

```bash
cd MCP-Google-Ads
git fetch origin
git pull --ff-only origin main
source .venv/bin/activate
python -m pip install -e ".[dev]"
python scripts/validate_local.py
```

Merchant Center is opt-in: if you don't set a Merchant Center refresh token or ID, the new tools simply report as unconfigured. Nothing about your existing Google Ads setup changes.

## Recommended production policy

```dotenv
GOOGLE_ADS_MCP_READ_ONLY=false
GOOGLE_ADS_MCP_AUTO_APPROVE=false
GOOGLE_ADS_MCP_AUTO_APPROVE_SPEND=false
GOOGLE_ADS_MCP_AUTO_APPROVE_DESTRUCTIVE=false
GOOGLE_ADS_MCP_AUTO_APPROVE_SENSITIVE=false
```

For the first boot after an upgrade, starting with `GOOGLE_ADS_MCP_READ_ONLY=true` is the conservative path — this now also covers Merchant Center writes.

## Documentation

- 🇦🇷🇪🇸 [README en Español](../README.md)
- 🇬🇧🇺🇸 [README in English](../README.en.md)
- [Full 0.17.0 technical release notes](RELEASE_0.17.0.md)
- [Setup](SETUP.md)
- [Tools reference](TOOLS.md)
- [MCP clients](CLIENTS.md)
- [Safety model](SAFETY.md)
- [Examples](EXAMPLES.md)
- [Google Ads API v25 coverage](V25_SERVICE_COVERAGE.md)
- [Changelog](../CHANGELOG.md)

## Built by Akela

**Alejandro José · Akela** — AI Products · Marketing Technology · Automation

- [Marketing Digital Experience](https://marketingdigitalexperience.com)
- [MKT Marketing Digital](https://mktmarketingdigital.com)
- [GitHub](https://github.com/akelaonline)
- [Instagram @akelaonline](https://www.instagram.com/akelaonline/)
- [alejandro@mktmarketingdigital.com](mailto:alejandro@mktmarketingdigital.com)

> **Build useful things. Ship them. Learn from production.**

MIT License.
