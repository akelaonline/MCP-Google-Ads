# Google Ads MCP 0.16.0

**Release date:** 2026-08-20  
**Google Ads API:** v25  
**Release theme:** complete v25 operator coverage + multi-customer production hardening

0.16.0 is the completion pass that follows the incremental coverage releases up
through 0.15.0. The goal of this release is not to add another handful of tools;
it is to remove the remaining situations where an operator can read or create a
Google Ads object but cannot complete its lifecycle from the MCP.

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

### Cross-customer mutation isolation is now recursive

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
  so helpers such as the different Product Link and Billing tools remain replayable.

Custom/legacy audit backends that implement only `record()` remain compatible;
they simply keep the previous in-memory pending behavior.

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
- Atomic two-arm traffic-split update so both values can be changed in one
  `MutateExperimentArms` request while preserving Google's total=100 invariant.

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

New 0.16.0 writes were classified conservatively: experiment launch/splits,
PMax listing/signal changes, bid modifiers, conversion goals/rules and live asset
links are spend-risk; customer data, identity, billing/access/linking and SKAd
changes are sensitive; removals/unlinks/terminal actions are destructive.

## Compatibility

- Existing MCP tool names remain available unless they represented a Google API
  contract that v25 itself removed or no longer permits.
- Existing safety environment variables remain valid.
- `cryptography>=42` is a new runtime dependency for encrypted pending replay.
- Existing custom audit backends do not need to implement the durable pending API;
  they fall back to process-local pending actions.
- HTTP remains disabled by default because this project intentionally does not ship
  a remote identity provider. Use stdio or put HTTP behind your own authenticated
  restricted proxy.

## Validation status

The repository contains real-v25 protobuf contract tests and new regressions for:

- cross-customer create/update/remove isolation;
- legitimate allowlisted MCC manager/client linking;
- durable pending restart replay;
- encrypted invocation arguments;
- public-tool/safety-alias replay;
- high-risk classification;
- ExperimentArm contracts and atomic split behavior;
- the major protobuf-heavy v25 write surfaces.

The ChatGPT execution environment used for this completion pass did **not** have
the `google-ads` Python package installed and could not install/clone dependencies,
so it did not execute the complete pytest suite or a live-account end-to-end run.
The code was reviewed against the official v25 reference and regression tests were
added to the repository. Run the local validation commands below in a normal
networked development environment before deploying over an existing production
installation:

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
python scripts/smoke_test.py
ruff check src tests
pytest -q
```

A live account test should use a dedicated allowlisted test customer with
high-risk auto-approve disabled and exercise:

1. read/account discovery;
2. harmless proposed write + cancel;
3. proposed write + confirm;
4. restart between propose and confirm;
5. MCC access to two allowlisted customers and a deliberately mixed-client
   operation that must be blocked;
6. a legitimate manager/client link between two explicitly allowlisted accounts.

## Upgrade

```bash
git pull origin main
source .venv/bin/activate
pip install -e .
```

If you use containers, make sure the audit DB and pending-action encryption key are
persistent before upgrading.

See:

- `docs/V25_SERVICE_COVERAGE.md`
- `docs/SAFETY.md`
- `docs/SETUP.md`
- `.env.example`
