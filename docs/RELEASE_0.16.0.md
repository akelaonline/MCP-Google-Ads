# Google Ads MCP 0.16.0

**Release date:** 2026-08-20  
**Google Ads API:** v25  
**Release theme:** complete v25 operator coverage + multi-customer production hardening

0.16.0 is the completion pass that follows the incremental coverage releases up
through 0.15.0. The goal of this release is not to add another handful of tools;
it is to remove the remaining situations where an operator can read or create a
Google Ads object but cannot complete its lifecycle from the MCP — while tightening
production safety for real multi-account deployments.

## Headline changes

### Audited Google Ads API v25 service coverage

The repository now includes `V25_SERVICE_COVERAGE.md`, audited against the
official v25 service reference. Every publicly callable v25 service is represented
by focused tools, constrained protobuf-JSON wrappers, GAQL/resource helpers, or a
combination of those.

Google-controlled surfaces are exposed but accurately labeled:

- AssetGenerationService — closed beta.
- AudienceInsightsService — allowlisted.
- BenchmarksService — allowlisted.
- ContentCreatorInsightsService — allowlisted.
- IncentiveService — allowlisted/eligibility controlled.
- MultiPartyAuthReviewService — beta.
- Local Services, billing, SKAdNetwork, Identity Verification and YouTube upload —
  subject to product/account eligibility.
- ReservationService — documented by Google as **not publicly available**, so the
  MCP does not fake support.

### Cross-customer mutation isolation is recursive

MCC credentials can legitimately access many customers. Request-level
`customer_id` validation alone does not prevent an operation constructed for
customer A from containing a nested resource reference belonging to customer B.

0.16.0 recursively scans populated protobuf fields in resource-specific and
atomic mutations. Customer-scoped references inside CREATE, UPDATE and REMOVE
operations are checked before the Google Ads RPC.

A deliberately narrow exception exists for real manager/client linking:
`CustomerClientLinkService` CREATE can reference a second customer, but that
customer must still pass `GOOGLE_ADS_MCP_ALLOWED_CUSTOMER_IDS` when the deployment
uses an allowlist. Ordinary campaign/ad/asset/criterion operations retain strict
same-customer isolation.

### MCC hierarchy reads are isolated too

The production allowlist now applies to hierarchy/link metadata returned through
`customer_client` and `customer_client_link`, including raw `run_gaql_query()`.

An allowed MCC can see children that are not intended for the current deployment.
0.16 filters those rows centrally before returning them. If a raw hierarchy/link
query does not select the field required to identify the referenced child customer,
the MCP fails closed instead of returning unfilterable cross-tenant metadata.

This closes a gap where write isolation could be correct while account metadata
from another tenant was still visible through an allowed manager account.

### Durable pending confirmations across restart

Pending write proposals no longer have to disappear with the Python process.
With the built-in SQLite audit backend, the MCP persists pending metadata and the
original public MCP invocation required to reconstruct the write.

- Invocation arguments are encrypted with Fernet before SQLite storage.
- `GOOGLE_ADS_MCP_PENDING_ENCRYPTION_KEY` can provide a stable deployment key.
- If no key is configured, a sibling `<audit-db>.pending.key` file is created with
  restrictive permissions where supported.
- Container deployments must persist the database and key together, or configure
  the environment key.
- If pending state cannot be decrypted/reconstructed, confirmation fails closed;
  no Google Ads mutation is attempted.
- A replay retains the same action ID, so retry/audit history stays correlated.
- Public MCP tool names are stored separately from internal shared risk aliases,
  so specialized helpers remain replayable even when they share a risk category.

Custom/legacy audit backends that implement only `record()` remain compatible;
they simply keep the previous in-memory pending behavior.

### Read-only kill switch

0.16 adds a central reporting-only/emergency-freeze mode:

```dotenv
GOOGLE_ADS_MCP_READ_ONLY=true
```

When enabled:

- reads, reports and GAQL continue working;
- audit inspection and pending listing remain available;
- pending actions may still be cancelled;
- new write proposals are blocked centrally;
- `confirm_pending_action()` is also blocked, including for proposals created
  before the process restarted with read-only enabled.

This is stronger than relying on an agent instruction such as “do not confirm.”

### Confirm/cancel race hardening

Within one running MCP process, pending control operations are serialized. Two
simultaneous confirmations cannot both enter execution for the same pending action,
and a cancellation cannot race a confirmation that is already entering execution.

This guarantee is process-local. The SQLite pending table is not a distributed
claim/lease system. One running MCP process should own one `audit.db`; several
simultaneous workers should not share the same pending database unless an external
single-writer/claim mechanism is added.

## Coverage added or completed

### Accounts, MCC and access

- Full manager link lifecycle: invite, accept/decline, cancel, unlink and move.
- Customer creation and mutable customer operational settings.
- User invitations, role updates/removal and invitation revocation.
- AccountLink legacy/specific link management.
- Modern ProductLink and ProductLinkInvitation flows, with Merchant Center's
  documented origin restriction respected.
- DataLink and third-party app analytics lifecycle.
- Google Ads ↔ YouTube video link request/accept/reject/revoke/remove lifecycle.

### Campaign administration

- Campaign Groups.
- Campaign Draft create/rename/promote/async-error/remove lifecycle.
- Smart Campaign suggestions, atomic campaign creation, status and mutable settings.
- Automatic asset removal at campaign and ad level.
- Customer/ad-group assets and AssetSets at customer/campaign/ad-group scope.
- Campaign/ad-group bid modifiers.
- Account-level negative criteria.

### Performance Max

- Audience, search-theme, Local Services and vertical-feed AssetGroup signals.
- Full listing-group replacement with atomic operations.
- SHOPPING product dimensions and explicit “everything else” nodes.
- RETAIL Product Tag filters through `retail_filter_bundle.shared_set`.
- WEBPAGE listing filters with multiple root filters as permitted by v25.
- Brand-guidelines migration.
- Asset-group and supported YouTube shareable previews.
- Travel asset suggestions.

### Experiments

- Full Experiment lifecycle: mutate, schedule, async errors, promote, graduate, end.
- ExperimentArm list/create/update/remove.
- Preferred `update_experiment_arm_traffic_splits` helper for atomic two-arm
  traffic-split changes.
- Compatibility alias `update_experiment_traffic_split` retained for callers using
  the shorter name.
- The split helper validates Google's total=100 invariant before the RPC and
  mutates both arms in one request.

### Keywords and planning

- Keyword ideas and historical metrics.
- Direct forecast metrics.
- Persistent KeywordPlan lifecycle: plan, campaign, ad group, positive and
  negative keywords.
- Smart Campaign KeywordThemeConstant suggestions.
- All six public ReachPlanService RPCs using v25 request contracts.

### Measurement and audiences

- Conversion custom variables.
- Conversion value rules and rule sets.
- v25 unified conversion/lifecycle/acquisition/retention/loyalty goal controls.
- Conversion retractions/restatements.
- Customer Match through existing Google Ads APIs plus Data Manager support.
- Small UserDataService uploads with PII excluded from normal audit payloads.
- Audience, CustomAudience, CustomInterest and UserListCustomerType lifecycle.
- RemarketingAction lifecycle and Google tag/event snippets.
- SKAdNetwork conversion-value schema mutation including v25 warnings flag.

### Platform and specialist services

- GoogleAdsField introspection.
- Local Services leads, conversations and feedback.
- Identity Verification get/start.
- Incentives fetch/apply.
- Multi-Party Authorization review resolution.
- Brand suggestions.
- YouTube video upload/update/status/remove.
- AssetGeneration text/image generation wrappers for Google allowlisted beta users.
- Audience, benchmark and creator insight RPCs for allowlisted accounts.

## v25 compatibility fixes included in this release

- Legacy lifecycle goal services removed in v25 are no longer referenced; unified
  GoalService/campaign-goal contracts are used.
- Creator Insights callers use the v25 request contract (`search_topics`, not the
  removed `search_brand`). Strict protobuf parsing rejects removed fields.
- Reach Planner uses `plannable_location_ids` and
  `cookie_frequency_cap_setting`; the v25 protobuf contract rejects removed fields.
- Advertising Partner ProductLinkInvitation requires `allowed_domain`.
- Performance Max RETAIL/Webpage listing-filter semantics match v25.
- Campaign interaction modifier code uses the actual v25 enum exposed by the
  generated client (`CALLS`) while the Google guide describes the concept as CALL.

## Safety model

Every normal write remains:

`propose -> preview -> confirm -> execute -> audit`

Risk classes remain:

- `standard`
- `spend`
- `destructive`
- `sensitive`

`GOOGLE_ADS_MCP_AUTO_APPROVE=true` does not implicitly enable the three high-risk
classes. Each requires its own explicit opt-in.

0.16 also tightens classification for delivery-changing operations that previously
could look harmless simply because no explicit currency amount appeared in the
payload. Enabled keyword creation, keyword match changes/negatives,
location/language/placement targeting, audience/topic attachment and conversion
biddability changes are now conservatively classified as `spend`.

Normal creative/resource preparation such as creating callouts or sitelinks remains
`standard` by design.

Customer data, identity, billing/access/linking and SKAd changes are `sensitive`;
removals/unlinks/terminal actions are `destructive`.

## Compatibility

- Existing MCP tool names remain available unless they represented a Google API
  contract that v25 itself removed or no longer permits.
- `update_experiment_traffic_split` remains available as a compatibility alias.
- Existing safety environment variables remain valid.
- `GOOGLE_ADS_MCP_READ_ONLY` is additive and defaults to `false`.
- `cryptography>=42` is a runtime dependency for encrypted pending replay.
- Existing custom audit backends do not need to implement the durable pending API;
  they fall back to process-local pending actions.
- HTTP remains disabled by default because this project intentionally does not ship
  a remote identity provider. Use stdio or put HTTP behind your own authenticated
  restricted proxy.

## Validation status

The repository contains real-v25 protobuf contract tests and regressions for:

- cross-customer create/update/remove isolation;
- legitimate allowlisted MCC manager/client linking;
- MCC hierarchy/link read filtering, including raw GAQL fail-closed behavior;
- durable pending restart replay;
- encrypted invocation arguments;
- public-tool/safety-alias replay;
- high-risk delivery classification;
- read-only blocking for proposal and confirmation paths;
- confirm/cancel process-local serialization;
- ExperimentArm contracts and atomic split behavior;
- AssetGeneration registration/contracts;
- the major protobuf-heavy v25 write surfaces.

The ChatGPT execution environment used for this completion pass did **not** have
the `google-ads` Python package/FastMCP/Ruff stack installed and could not install
or clone dependencies, so it did not execute the complete pytest/Ruff/smoke suite
or a live-account end-to-end run. The code was reviewed against the official v25
reference and regression tests were added to the repository. Run the local
validation commands below in a normal networked development environment before
deploying over an existing production installation:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python scripts/smoke_test.py
ruff check src tests scripts
pytest -q
```

A live account test should use a dedicated allowlisted test customer with
high-risk auto-approve disabled and exercise:

1. account discovery/read;
2. read-only mode: reads succeed, proposal and confirmation fail closed;
3. harmless proposed write + cancel;
4. proposed write + confirm;
5. restart between propose and confirm;
6. MCC access to multiple customers and verification that non-allowlisted
   `customer_client`/`customer_client_link` rows are not returned;
7. deliberate mixed-client mutation that must be blocked;
8. a legitimate manager/client link between two explicitly allowlisted accounts;
9. two concurrent confirms for one pending action, verifying only one execution.

## Upgrade

```bash
git pull origin main
source .venv/bin/activate
pip install -e .
```

If you use containers, make sure the audit DB and pending-action encryption key are
persistent before upgrading. Do not share the same pending DB between simultaneous
MCP worker processes.

See:

- `docs/V25_SERVICE_COVERAGE.md`
- `docs/SAFETY.md`
- `docs/SETUP.md`
- `.env.example`