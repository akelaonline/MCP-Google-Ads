# FAQ — Google Ads MCP v0.16

## What does this MCP do?

It gives an MCP client structured **read/write** access to Google Ads API v25. It covers reporting, campaigns, budgets, bidding, ad groups, ads, assets, keywords, audiences, targeting, conversions/goals, Performance Max, experiments, recommendations, MCC/account access, billing/product links, Batch Jobs, Smart Bidding controls and specialist Google Ads services.

For the service-by-service coverage contract, see [`V25_SERVICE_COVERAGE.md`](V25_SERVICE_COVERAGE.md).

## Can I run it reporting-only?

Yes. v0.16 has a central kill switch:

```dotenv
GOOGLE_ADS_MCP_READ_ONLY=true
```

Read/report/GAQL tools still work. New write proposals are blocked and existing pending actions cannot be confirmed. Pending actions may still be inspected or cancelled.

This is stronger than merely keeping auto-approve off: the instance categorically refuses Google Ads mutations through the safety layer.

## Does a write change the account immediately?

Not by default.

```dotenv
GOOGLE_ADS_MCP_READ_ONLY=false
GOOGLE_ADS_MCP_AUTO_APPROVE=false
```

A normal write returns `pending_confirmation`. Nothing has changed yet. Execute it with `confirm_pending_action(action_id)` or discard it with `cancel_pending_action(action_id)`.

## What are the risk classes?

- `standard` — ordinary writes that do not directly alter live delivery, access or sensitive data.
- `spend` — budget/bidding and other delivery-changing operations such as enabled keywords, negatives, match changes, location/language/placement targeting, audience/topic attachment and conversion-biddability changes.
- `destructive` — remove/unlink/terminal operations.
- `sensitive` — account access, customer data, billing/linking and other sensitive operations.

Even if global auto-approve is enabled, spend/destructive/sensitive actions remain separately gated unless their own explicit opt-in is enabled.

## What happens if confirmation fails?

The pending action is not deleted first. A transient Google/network failure keeps the same action available for retry and records the failed attempt under the same action ID.

## Can two confirmations execute the same pending action?

Inside one running MCP process, v0.16 serializes pending list/confirm/cancel operations so simultaneous confirmation requests cannot both enter execution for the same action.

This is not a distributed lock. Do not point several simultaneously running MCP processes/workers at the same `audit.db`.

## Do pending actions survive an MCP restart?

With the built-in SQLite audit backend, **yes** for tracked MCP calls. v0.16 stores the original public tool invocation required for replay and encrypts those arguments at rest with Fernet.

For a stable production deployment, either persist the generated sibling key file with the audit database or define:

```dotenv
GOOGLE_ADS_MCP_PENDING_ENCRYPTION_KEY=
```

If the persisted invocation cannot be decrypted or reconstructed, confirmation fails closed and no Google Ads mutation is executed.

## Can one MCP control several Google Ads accounts?

Yes. MCC credentials can expose many customer accounts. Production deployments should scope that access explicitly:

```dotenv
GOOGLE_ADS_MCP_ALLOWED_CUSTOMER_IDS=123-456-7890,987-654-3210
GOOGLE_ADS_MCP_REQUIRE_CUSTOMER_ALLOWLIST=true
```

Reads/writes outside the configured scope are blocked and account discovery is filtered.

## Can an allowed MCC leak metadata about a child account outside the allowlist?

The common hierarchy surfaces are filtered centrally in v0.16. `customer_client` rows are filtered by `customer_client.id`, and `customer_client_link` rows are filtered by the linked `client_customer`.

This also applies to raw `run_gaql_query()`. If a raw hierarchy query omits the ownership field required to filter each row safely, the MCP fails closed instead of returning unfilterable cross-client metadata.

## Can customer A accidentally reference a campaign/asset belonging to customer B?

v0.16 recursively checks customer-scoped resource references in mutation payloads, including nested references inside CREATE operations. Mixed-client mutations are blocked before the Google Ads RPC.

The deliberate exception is real manager/client linking. That path may reference a second Google Ads customer only when the second customer also passes the deployment allowlist.

## Which Google Ads API version does v0.16 target?

Google Ads API **v25**. The project explicitly requests `v25` and pins the Google Ads Python client to the tested 31.x line instead of floating to a future default API version.

## Does the MCP support Performance Max?

Yes. Coverage includes campaigns, asset groups, text/image/video assets, signals, brand-guidelines migration, listing filters, Shopping dimensions, RETAIL Product Tags, WEBPAGE filters and supported preview/shareable workflows.

## Does it support experiments?

Yes. Experiment lifecycle and ExperimentArm lifecycle are exposed. The preferred `update_experiment_arm_traffic_splits` tool changes both arms atomically so Google's total=100 traffic invariant is preserved. `update_experiment_traffic_split` remains as a compatibility alias.

## Does it support Customer Match?

Yes where the Google account/integration is eligible. The MCP supports legacy Google Ads API flows, Data Manager support and small UserDataService uploads.

Normal audit payloads do not contain raw Customer Match identifiers. Sensitive invocation arguments needed for durable replay are encrypted at rest.

## Does it support Batch Jobs?

Yes, through a constrained reviewed manifest. The MCP intentionally does not expose arbitrary raw protobuf mutations through Batch Jobs.

Batch jobs can partially succeed. Always inspect row-level results after completion.

## Can it create traditional legacy VIDEO campaigns?

No. Google Ads API v25 does not provide the old programmatic VIDEO creation contract used by legacy implementations. The compatibility endpoint fails safe and performs no mutation. Use Demand Gen video workflows instead.

## Can it manage Merchant Center feeds/products?

No. Merchant Center catalog/feed management is a separate product/API. This MCP can operate Google Ads Shopping/PMax resources assuming the required Merchant Center linking already exists.

## Can it manage Google Business Profile?

No. Google Business Profile administration is outside the Google Ads API boundary.

## What about Google-controlled beta/allowlisted services?

The MCP exposes relevant v25 wrappers for services such as Asset Generation, Audience Insights, Benchmarks, Creator Insights, Incentives and other eligibility-controlled surfaces.

The MCP does not fake access. If Google has not enabled the authenticated account for a service, the upstream Google Ads error is returned.

`ReservationService` is not exposed because Google documents it as not publicly available.

## Is HTTP safe to expose publicly?

No. `stdio` is the recommended/default transport. Raw HTTP is blocked by default because the server includes powerful write and confirmation tools and does not bundle a remote identity provider.

`GOOGLE_ADS_MCP_ALLOW_INSECURE_HTTP=true` only removes the startup block; it does **not** add authentication. Use it only behind your own authenticated and network-restricted boundary.

## Where is the audit log?

Default:

```text
~/.google_ads_mcp/audit.db
```

Use `get_recent_audit_log()` for recent executions and `get_audit_action(action_id)` to inspect every attempt for one action.

## Is every Google Ads mutation reversible?

No. The audit log is an execution trail, not a universal rollback system. Prefer pause/disable over remove where Google supports a reversible status.

## How do I validate an upgrade?

In a normal networked development environment:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python scripts/smoke_test.py
ruff check src tests
pytest -q
```

For production confidence, start in read-only mode, verify allowed account/reporting scope, confirm a mutation is blocked, then switch to confirmation mode and exercise propose+cancel, propose+confirm, restart replay, MCC read filtering, cross-customer mutation blocking and any manager/client link workflow you use.

## Where should I start?

- [`SETUP.md`](SETUP.md) — install/OAuth/production configuration
- [`SAFETY.md`](SAFETY.md) — confirmation, risk, audit and isolation
- [`TOOLS.md`](TOOLS.md) — operator index
- [`V25_SERVICE_COVERAGE.md`](V25_SERVICE_COVERAGE.md) — service coverage contract
- [`RELEASE_0.16.0.md`](RELEASE_0.16.0.md) — current release details