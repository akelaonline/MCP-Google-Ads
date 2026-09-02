# Google Ads MCP 0.17.0

> **Google Ads API v25 · Merchant Center (Merchant API) beta · 362/362 tests**

**Release date:** 2026-09-02  
**Google Ads API:** v25  
**Release type:** new capability — Google Merchant Center support

Google Ads MCP 0.17.0 adds a second product surface to the server: **Google Merchant Center**, via Google's Merchant API. It keeps the full v0.16 Google Ads read/write surface unchanged and adds Shopping/product-feed operations behind the same propose/confirm safety model.

If you are installing the project for the first time, start with the [README](../README.md). If you already run an older version, use the [safe local update procedure](UPDATE_LOCAL.md).

---

## Why this release exists

Google shut down **Content API for Shopping** on **2026-08-18**, the API that most third-party Shopping tooling used for over a decade. Its replacement, **Merchant API** (`merchantapi.googleapis.com`), is a different, modular REST surface with its own sub-APIs (accounts, products, datasources, reports).

Google Ads MCP had no Shopping/Merchant Center coverage before 0.17.0. This release closes that gap using the current, supported API — not the retired one.

---

## What's new

### Merchant Center tools (beta)

A new `tools/merchant_center.py` module, backed by a new lightweight REST client (`merchant_client.py`) that mirrors the existing Data Manager client pattern: it reuses the Google Ads OAuth client credentials, has no dependency on a Merchant API SDK, and requests the `content` OAuth scope.

**Account status & diagnostics**

```text
get_merchant_center_configuration
list_merchant_center_accounts
get_merchant_center_account
list_merchant_center_sub_accounts
list_merchant_center_account_issues
```

**Product catalog**

```text
list_merchant_center_products
get_merchant_center_product
list_merchant_center_product_issues     # pre-built MCQL: disapproved/ineligible products, and why
get_merchant_center_product_performance # pre-built MCQL: clicks/impressions/conversions
search_merchant_center_reports          # raw MCQL, like run_gaql_query for Google Ads
```

**Product writes — propose/confirm, same safety model as every Google Ads write**

```text
insert_merchant_center_product   # create OR update; Merchant API has no separate update call
remove_merchant_center_product   # destructive risk, via the existing remove_ convention
```

**Data sources (feeds)**

```text
list_merchant_center_datasources
get_merchant_center_datasource
fetch_merchant_center_datasource # propose/confirm: trigger an out-of-schedule fetch
```

### Configuration

Two new optional environment variables:

```dotenv
GOOGLE_MERCHANT_CENTER_REFRESH_TOKEN=
GOOGLE_MERCHANT_CENTER_ID=
```

`GOOGLE_MERCHANT_CENTER_REFRESH_TOKEN` is optional: if unset, the server falls back to `GOOGLE_ADS_REFRESH_TOKEN`, so a single OAuth grant with both scopes covers both products. Generate it with:

```bash
python -m google_ads_mcp.auth --generate-refresh-token --include-merchant-center
```

`GOOGLE_MERCHANT_CENTER_ID` is an optional default account, used whenever a tool call omits `merchant_id`.

### Safety model, unchanged and reused

Merchant Center account IDs are numeric, like Google Ads customer IDs, and are reused as the `customer_id` for the existing pending-action/audit/allowlist machinery:

- Every write goes through `propose → preview → confirm → execute → audit`, exactly like Google Ads writes.
- `remove_merchant_center_product` is classified `destructive` risk automatically (the existing `remove_` convention), so global auto-approve alone does not execute it.
- The read-only kill switch (`GOOGLE_ADS_MCP_READ_ONLY=true`) blocks Merchant Center writes exactly like Google Ads writes.
- If a deployment sets `GOOGLE_ADS_MCP_ALLOWED_CUSTOMER_IDS` / `GOOGLE_ADS_MCP_REQUIRE_CUSTOMER_ALLOWLIST`, Merchant Center account IDs used with write tools must also be included in that allowlist.

No new safety code paths were introduced — Merchant Center writes reuse `SafetyLayer` as-is.

---

## Why "beta"

Merchant API attribute coverage (the fields accepted on a product) evolves independently of Google Ads API versioning, and this release has **not yet been exercised against a live production Merchant Center account** the way 0.16.8 was for Google Ads. `insert_merchant_center_product` accepts an `extra_attributes` escape hatch for any field not covered by the named kwargs — verify field names against Google's current Merchant API reference before relying on them in production.

Recommended first use: run the read tools (`get_merchant_center_configuration`, `list_merchant_center_account_issues`, `list_merchant_center_product_issues`) against a real account before proposing any write.

---

## Validation

Local gate is green:

```text
isolated smoke  → SMOKE OK (56 tool modules, zero duplicate-tool warnings)
ruff check      → All checks passed
pytest -q       → 362 passed (16 new Merchant Center tests)
```

Run it yourself with:

```bash
python scripts/validate_local.py
```

`tests/test_merchant_center_tools.py` covers: configuration reporting, request shaping (method/path/query per tool), MCQL query building and input validation, the propose/confirm flow for every write tool, destructive-risk classification, and read-only-mode blocking — using a fake Merchant Center REST client, no live account required.

---

## What is included, unchanged from 0.16.8

0.17.0 includes the complete v0.16 Google Ads line as-is — no Google Ads tool signature, safety behavior, or risk classification changed in this release. See [`docs/RELEASE_0.16.8.md`](RELEASE_0.16.8.md) and [`V25_SERVICE_COVERAGE.md`](V25_SERVICE_COVERAGE.md) for that surface.

---

## Upgrade from an older checkout

Preserve your existing `.env`, audit database, and pending-action encryption key.

```bash
cd MCP-Google-Ads

git status
git fetch origin
git pull --ff-only origin main

source .venv/bin/activate
python -m pip install -e ".[dev]"
python scripts/validate_local.py
```

Merchant Center is opt-in: if you don't set `GOOGLE_MERCHANT_CENTER_REFRESH_TOKEN` / `GOOGLE_MERCHANT_CENTER_ID` and never generated a token with `--include-merchant-center`, the new tools simply report `configured: false` and the rest of the server behaves exactly as before.

Do **not** copy `.env.example` over an existing `.env`.

Full procedure: [`UPDATE_LOCAL.md`](UPDATE_LOCAL.md).

---

## First use after upgrade

```text
Do we have access to Merchant Center account <your account id>?
```

should call `get_merchant_center_configuration` and `get_merchant_center_account`/`list_merchant_center_account_issues` — all reads, nothing pending. Only after confirming the expected account should a write (`insert_merchant_center_product`, `remove_merchant_center_product`, `fetch_merchant_center_datasource`) be proposed, and it should return `pending_confirmation` before anything changes.

---

## Safety notes

- Treat Merchant Center writes with the same discipline as Google Ads spend/destructive changes: review the `pending_confirmation` preview before calling `confirm_pending_action`.
- If Merchant Center access lives on a different Google account/grant than Google Ads, set `GOOGLE_MERCHANT_CENTER_REFRESH_TOKEN` explicitly rather than relying on the fallback.
- Include Merchant Center account IDs in `GOOGLE_ADS_MCP_ALLOWED_CUSTOMER_IDS` if that allowlist is enabled.

Full model: [`SAFETY.md`](SAFETY.md).

---

## About the project

Google Ads MCP is built and maintained by **Alejandro José · Akela** as part of a broader body of work around AI products, marketing technology, automation, analytics and production tooling.

- [GitHub · akelaonline](https://github.com/akelaonline)
- [Marketing Digital Experience · AI consulting](https://marketingdigitalexperience.com)
- [MKT Marketing Digital · agency](https://mktmarketingdigital.com)
- [Instagram · @akelaonline](https://www.instagram.com/akelaonline/)
- [Email · alejandro@mktmarketingdigital.com](mailto:alejandro@mktmarketingdigital.com)

> **Build useful things. Ship them. Learn from production.**

---

## Documentation

- [README — Español](../README.md)
- [README — English](../README.en.md)
- [Setup](SETUP.md)
- [MCP clients](CLIENTS.md)
- [Safety model](SAFETY.md)
- [Tool reference](TOOLS.md)
- [Examples](EXAMPLES.md)
- [Google Ads API v25 coverage](V25_SERVICE_COVERAGE.md)
- [Production validation checklist](VALIDATION_CHECKLIST.md)
- [Changelog](../CHANGELOG.md)

---

**Google Ads MCP 0.17.0 · MIT License · Built by [Akela](https://github.com/akelaonline)**
