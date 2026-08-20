# Google Ads MCP 0.16.0

**Release date:** 2026-08-20  
**Google Ads API:** v25  
**Release theme:** v25 coverage completion + multi-customer production hardening

0.16.0 consolidates the incremental coverage releases through 0.15.0 into a
production-oriented Google Ads operator. The goal of this release is not merely
more tools: it closes the remaining stable-public service gaps while tightening
customer isolation, confirmation durability, read-only controls and API-contract
accuracy for agencies operating real client accounts.

## Coverage result

`docs/V25_SERVICE_COVERAGE.md` is the release coverage contract.

**Stable-public Google Ads API v25 services without deliberate MCP treatment: 0.**

Coverage is intentionally honest about Google-controlled boundaries:

- AssetGenerationService — closed beta / access controlled.
- AudienceInsightsService — allowlisted.
- BenchmarksService — allowlisted.
- ContentCreatorInsightsService — allowlisted.
- IncentiveService — explicitly allowlisted by Google.
- ReachPlanService — requires a Reach Plan-allowlisted developer token/account.
- MultiPartyAuthReviewService — beta.
- Billing, Local Services, Customer Match, Identity Verification and YouTube upload
  remain subject to product/account eligibility.
- ReservationService — not publicly callable; the MCP does not fake support.
- CustomerSkAdNetworkConversionValueSchemaService — deliberately specialized:
  schema reads are exposed, but a generic schema writer is not.

## Final release-audit fixes

The final v0.16 audit found three contract issues before the release tag was cut.
All three were fixed before publication.

### CustomerManagerLink v25 RPC

The generated v25 method is singular:

`mutate_customer_manager_link(..., operations=[...])`

The generic wrapper previously would have pluralized the method name to
`mutate_customer_manager_links`, causing live accept/decline/unlink operations to
fail at runtime. 0.16.0 now explicitly maps `CustomerManagerLinkService` to the
correct singular method while retaining the real `operations[]` request field.

### Audience ASSET_GROUP naming rules

Google v25 does not permit an `ASSET_GROUP`-scoped Audience to set or update
`name`. The MCP already enforced this on creation; the release audit found that
metadata updates did not re-check the current scope.

0.16.0 now:

- reads the current Audience scope before a name/scope update;
- blocks renaming an `ASSET_GROUP` Audience unless it is being promoted;
- requires a name when promoting `ASSET_GROUP -> CUSTOMER`;
- refuses redundant promotion of an already-CUSTOMER Audience;
- fails closed when the current scope cannot be established safely.

### SKAdNetwork false writable surface removed

Google Ads API v25 publishes a
`MutateCustomerSkAdNetworkConversionValueSchema` RPC, but the public v25 resource
reference marks both `resource_name` and `schema` as **output-only**.

Earlier completion code exposed two dict-to-protobuf schema writers. Those tools
have been removed. 0.16.0 exposes:

- `list_customer_skad_network_conversion_value_schemas` for schema visibility;
- `get_customer_skad_network_schema_capability` explaining the deliberate boundary.

The release also includes a source regression guard that fails if either removed
SKAd writer function is reintroduced. This prevents an undocumented write path
from being presented as production-safe coverage.

## Production hardening

### Recursive cross-customer mutation isolation

Request-level `customer_id` validation is insufficient with MCC credentials. A
mutation for customer A can contain nested resource references to customer B.

0.16.0 recursively inspects populated protobuf resource references before
resource-specific and atomic mutations. Cross-customer references are blocked by
default.

A narrow manager/client-link exception is supported because
`CustomerClientLinkService` legitimately references another Google Ads account.
Every referenced account still has to pass the deployment allowlist.

### MCC hierarchy read isolation

The allowlist is also enforced on linked-customer GAQL rows:

- `customer_client` is filtered by `customer_client.id`;
- `customer_client_link` by `customer_client_link.client_customer`;
- `customer_manager_link` by `customer_manager_link.manager_customer`.

Raw GAQL uses the same production client. If a hierarchy query omits the ownership
field required for filtering, the MCP fails closed rather than returning
unfilterable cross-tenant metadata.

### Durable pending confirmations

Pending proposals can survive process restarts when the built-in SQLite audit
backend is used.

- Public invocation arguments needed for replay are encrypted with Fernet.
- `GOOGLE_ADS_MCP_PENDING_ENCRYPTION_KEY` supports a stable deployment key.
- Without one, a sibling pending key file is created with restrictive permissions
  where supported.
- Database and key must be persisted together in container deployments.
- Missing/corrupt replay state fails closed; no Google Ads mutation is attempted.
- Replay retains the same action ID for consistent audit history.

Custom/legacy audit backends remain compatible and keep process-local pending
behavior if they do not implement durable persistence.

### Read-only kill switch

```dotenv
GOOGLE_ADS_MCP_READ_ONLY=true
```

When enabled:

- reads, reports and GAQL continue working;
- audit inspection and pending listing remain available;
- pending actions may be cancelled;
- new write proposals are blocked centrally;
- confirmation of existing pending actions is also blocked.

### Confirm/cancel race hardening

Pending confirm/cancel operations are serialized within one MCP process so the
same action cannot enter execution twice concurrently and cancellation cannot
race a confirmation already entering execution.

The SQLite pending table is not a distributed lease system. One running MCP
process should own one pending-action database unless an external single-writer
mechanism is added.

### Effect-based risk classification

Risk classification now follows the effect on live delivery:

- resources explicitly prepared PAUSED may remain `standard` where appropriate;
- live creative attachments and existing RSA edits are `spend`;
- targeting, keyword, audience and conversion-biddability changes are `spend`;
- removals/unlinks/terminal actions remain `destructive`;
- account access, billing, sensitive data and high-impact control-plane writes
  remain `sensitive`.

Global standard auto-approve never implicitly enables spend, destructive or
sensitive auto-approval.

## Coverage added or completed

### Accounts, MCC, access and billing

- Full manager/client link lifecycle including move-manager workflows.
- Customer creation and mutable operational settings.
- User invitations, role changes and removals.
- AccountLink, ProductLink, ProductLinkInvitation and DataLink workflows.
- Third-party app analytics linking and shareable-ID rotation.
- Billing setup, payments-account discovery, invoices and account-budget proposals.

### Campaign administration and bidding

- Campaign Groups and Campaign Draft lifecycle.
- Smart Campaign settings, status and suggestions.
- Automatic asset removal.
- Customer/ad-group assets and AssetSets across supported scopes.
- Campaign/ad-group bid modifiers.
- Portfolio bidding strategies, seasonality adjustments and data exclusions.
- Controlled asynchronous Batch Jobs with row-level result inspection.

### Performance Max and creative operations

- PMax asset groups, signals, supported listing-filter structures and brand-guideline
  migration.
- RETAIL Product Tags and WEBPAGE listing filters where v25 permits them.
- Shareable previews and Travel asset suggestions.
- YouTube video upload/update/status/remove for eligible accounts.
- AssetGeneration wrappers for Google-approved beta users.

### Planning, measurement and audiences

- Keyword ideas, historical metrics, forecasts and persistent Keyword Plans.
- All six public ReachPlanService RPCs, subject to Google's Reach Plan allowlist.
- Conversion custom variables, value rules/rule sets and adjustment workflows.
- Unified v25 goal controls for acquisition/retention/loyalty.
- Audience, CustomAudience, CustomInterest and UserListCustomerType lifecycle.
- Customer Match through supported upload paths with PII excluded from normal audit
  payloads.
- RemarketingAction lifecycle and tag/event snippets.
- SKAdNetwork schema visibility with an explicit no-fake-writer capability guard.

### Specialist/platform services

- GoogleAdsField metadata introspection.
- Local Services leads, conversations and feedback.
- Identity Verification get/start.
- Incentives fetch/apply for allowlisted users.
- Multi-Party Authorization review workflow.
- Brand/creator/audience/benchmark specialist RPCs according to Google access rules.

## v25 compatibility fixes included in this release

- Legacy lifecycle goal services removed in v25 are not referenced; the unified
  GoalService/campaign-goal model is used.
- Creator Insights callers use current request fields.
- Reach Planner uses the current v25 targeting/frequency contract.
- Advertising Partner ProductLinkInvitation enforces required domain data.
- PMax RETAIL/WEBPAGE listing-filter semantics follow current v25 shapes.
- CustomerManagerLink uses the real singular RPC name with repeated operations.
- Audience ASSET_GROUP name-update restrictions are enforced before mutation.
- Undocumented SKAdNetwork schema writers are removed.

## Safety model

Every normal write remains:

`propose -> preview -> confirm -> execute -> audit`

Risk classes:

- `standard`
- `spend`
- `destructive`
- `sensitive`

`GOOGLE_ADS_MCP_AUTO_APPROVE=true` does not implicitly enable the three high-risk
classes. Each requires its own explicit opt-in.

## Validation status

The repository contains generated-v25 contract and regression coverage for the
major protobuf-heavy paths, production isolation, durable replay, read-only mode,
risk classification and the final release-audit fixes.

For this final completion pass, the ChatGPT execution environment could inspect
and update GitHub but could not install/clone the local dependency stack because
outbound package/network access was unavailable. Per repository policy, GitHub
Actions was not used. Therefore this release does **not** claim a newly executed
full pytest/Ruff/live-account run from this environment.

Before deploying over an existing production installation, run in a normal
networked development environment:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python scripts/smoke_test.py
ruff check src tests scripts
pytest -q
```

A live validation customer should be explicitly allowlisted, with high-risk
auto-approve disabled, and should verify read-only behavior, proposal/cancel,
proposal/confirm, restart replay, MCC tenant isolation, legitimate manager linking,
concurrent confirm protection and live-delivery risk gating.

## Upgrade

```bash
git pull origin main
source .venv/bin/activate
pip install -e .
```

Persist the audit DB and pending encryption key together. Do not share one pending
database between simultaneous MCP worker processes without an external claim or
single-writer mechanism.

See:

- `docs/V25_SERVICE_COVERAGE.md`
- `docs/SAFETY.md`
- `docs/SETUP.md`
- `.env.example`
