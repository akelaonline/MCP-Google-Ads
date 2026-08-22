# Google Ads MCP 0.16.8

> **Recommended release · Google Ads API v25 · 346/346 tests · Live E2E validated**

**Release date:** 2026-08-21  
**Google Ads API:** v25  
**Release type:** production hardening + deterministic tool registry

Google Ads MCP 0.16.8 is the recommended build of the v0.16 line. It keeps the broad read/write Google Ads surface introduced across 0.16.4–0.16.7, closes a subtle public-tool registration bug, and has now passed both the complete local gate and a real-account end-to-end validation.

If you are installing the project for the first time, start with the [README](../README.md). If you already run an older version, use the [safe local update procedure](UPDATE_LOCAL.md).

---

## What Google Ads MCP is

Google Ads MCP is a self-hosted Model Context Protocol server that lets Claude —or any compatible MCP client— **operate Google Ads instead of only reporting on it**.

The intended operating model is:

```text
propose → preview → confirm → execute → audit
```

Reads can run immediately. Consequential writes remain behind the safety layer and can be kept fully manual with auto-approve disabled.

Core production properties in 0.16.8:

- Google Ads API v25;
- read/write campaign-management surface;
- MCC / multi-customer isolation;
- explicit deployment allowlists;
- read-only kill switch;
- risk classes (`standard`, `spend`, `destructive`, `sensitive`);
- durable encrypted pending actions;
- SQLite audit trail;
- deterministic public-tool ownership;
- offline/local validation before deployment;
- self-hosted operation without a required SaaS middleware.

---

## Release highlights

### ✅ 346/346 tests

The complete local gate is green:

```text
isolated smoke  → SMOKE OK
ruff check      → All checks passed
pytest -q       → 346 passed
```

Run it yourself with:

```bash
python scripts/validate_local.py
```

### ✅ Real-account E2E validated

0.16.8 has been exercised against a real Google Ads MCC with reversible test operations:

- read-only kill switch;
- MCC / cross-customer isolation;
- propose → cancel;
- propose → confirm;
- audit action correlation;
- durable pending action after process restart.

No production budget, campaign delivery, or live advertising configuration was intentionally modified by the validation pass.

### ✅ Deterministic tool registration

A public MCP tool now has one explicit owner. Known superseded modules can be skipped only when they are declared as legacy; any unexpected competing implementation causes server construction to fail instead of being silently discarded.

### ✅ Conversion Value Rules ownership fixed

The ergonomic typed implementation is now the default public tool:

```text
create_conversion_value_rule
  → google_ads_mcp.tools.conversions
```

The full protobuf-JSON path remains available separately:

```text
create_conversion_value_rule_from_json
```

The richer read remains:

```text
list_conversion_value_rules
  → google_ads_mcp.tools.remaining_core_services
```

---

## The 0.16.8 registry bug

The issue was subtle because the server could still build and the canonical-owner smoke check could still look correct.

`_candidate_should_register()` treated **every non-canonical implementation of a known tool name as legacy**, even when that module was actually a newer competing implementation rather than the old superseded source.

That meant a legitimate new implementation could disappear from the assembled MCP without raising an error.

The concrete case was `create_conversion_value_rule`:

- `conversions.py` contained the typed implementation with `geo_target_ids`, `audience_condition`, and `device_type`;
- `remaining_core_services.py` occupied the canonical slot;
- the typed implementation was silently omitted from the public MCP even though isolated module tests could still reach it.

---

## The fix

### Declared legacy only

`invocation.py` now maintains an explicit legacy map. For each canonical public tool:

1. the canonical module registers;
2. only explicitly declared superseded modules may be skipped silently;
3. any other module competing for the same public name raises `RuntimeError` during server construction.

This changes duplicate registration from an ambiguous warning/silent omission into a deterministic contract.

### Canonical owners in 0.16.8

```text
list_asset_group_signals
  → google_ads_mcp.tools.pmax_signals_listing

add_asset_group_signal
  → google_ads_mcp.tools.pmax_signals_listing

list_asset_group_listing_filters
  → google_ads_mcp.tools.pmax_signals_listing

create_conversion_value_rule
  → google_ads_mcp.tools.conversions

list_conversion_value_rules
  → google_ads_mcp.tools.remaining_core_services
```

### Regression protection

`tests/test_tool_registry_sweep.py` now:

1. builds the real assembled server;
2. asserts canonical ownership;
3. scans the tools tree for duplicate public definitions;
4. permits only declared legacy sources;
5. verifies an undeclared duplicate raises;
6. verifies declared legacy is skipped only in the intended case.

---

## What is included in the v0.16 line

0.16.8 includes all previous v0.16 capabilities and fixes, including:

- Search, Standard Shopping, Performance Max, Demand Gen, App Campaigns, Dynamic Search Ads, Smart Campaigns;
- campaign budgets and advanced bidding;
- RSA, Responsive Display and extended assets;
- keywords, negatives, placements, schedules, audiences and exclusions;
- Customer Match and remarketing;
- offline, call and enhanced conversions with consent support;
- Conversion Value Rules and unified v25 goals;
- PMax asset groups, signals, listing filters and previews;
- experiments and atomic traffic splits;
- Batch Jobs and Smart Bidding controls;
- billing, ProductLink/DataLink and YouTube/app analytics links;
- Keyword Planner, Reach Planner and specialist v25 services;
- MCC hierarchy/account management;
- read-only mode, confirmation policy, encrypted durable replay and audit logging.

For service-by-service coverage, use [`V25_SERVICE_COVERAGE.md`](V25_SERVICE_COVERAGE.md).

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

Do **not** copy `.env.example` over an existing `.env`.

Do **not** delete the audit DB or its Fernet key just to make an update easier; code and persistent pending state are different concerns.

Full procedure: [`UPDATE_LOCAL.md`](UPDATE_LOCAL.md).

---

## First production start after upgrade

For a conservative deployment, start read-only:

```dotenv
GOOGLE_ADS_MCP_READ_ONLY=true
```

Verify:

```text
List my accessible Google Ads customer IDs.
```

Then run a normal report.

Only after confirming the expected account scope should a write-capable deployment switch to:

```dotenv
GOOGLE_ADS_MCP_READ_ONLY=false
GOOGLE_ADS_MCP_AUTO_APPROVE=false
GOOGLE_ADS_MCP_AUTO_APPROVE_SPEND=false
GOOGLE_ADS_MCP_AUTO_APPROVE_DESTRUCTIVE=false
GOOGLE_ADS_MCP_AUTO_APPROVE_SENSITIVE=false
```

A first write should be reversible and should return `pending_confirmation` before anything changes.

---

## Validation record

### Local gate

```text
Google Ads API contract: v25
Tool modules: 55
Duplicate-tool warnings: 0
Ruff: clean
Pytest: 346 passed
```

### Live-account E2E

The following flows were validated against a real production MCC using reversible metadata operations on a disposable test account:

#### Read-only kill switch

With:

```dotenv
GOOGLE_ADS_MCP_READ_ONLY=true
```

reads and GAQL remained available, while a write was rejected before creating a pending action or contacting Google Ads for a mutation.

#### Cross-customer isolation

A deliberate cross-customer resource reference was attempted by targeting one customer's ad group while referencing another customer's user list.

The MCP rejected it before mutation:

```text
Cross-customer mutation was blocked before contacting Google Ads.
```

Both accounts remained unchanged.

#### Propose → cancel

A reversible write returned `pending_confirmation`. The account was checked before confirmation and remained unchanged. `cancel_pending_action()` removed the proposal without a Google Ads mutation.

#### Propose → confirm

A second reversible proposal was confirmed. The real account reflected the expected change, and the audit log recorded success under the same action ID.

#### Durable restart replay

A pending action was left unconfirmed and the MCP process was restarted while preserving the audit DB and encryption key. The action was restored from the durable store and could be confirmed after restart without generating a second proposal.

---

## Safety notes

- Use an explicit allowlist for MCC deployments.
- Keep high-risk auto-approve flags disabled unless the workflow has been intentionally designed for unattended mutations.
- One running MCP process should own one `audit.db`; the confirmation lock is process-local, not distributed.
- Persist the Fernet key with the audit DB.
- Do not expose the HTTP transport directly to the public Internet; the project does not bundle an identity provider.
- Access-controlled Google Ads services remain subject to Google-side eligibility.

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

**Google Ads MCP 0.16.8 · MIT License · Built by [Akela](https://github.com/akelaonline)**
