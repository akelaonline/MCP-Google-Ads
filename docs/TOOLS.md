# Tool reference — v0.16 / Google Ads API v25

This file is the **living operator index** for Google Ads MCP. It intentionally stays compact so it can remain current as the tool surface grows.

For the authoritative service-by-service API coverage map, use [`V25_SERVICE_COVERAGE.md`](V25_SERVICE_COVERAGE.md). For production policy, use [`SAFETY.md`](SAFETY.md) and [`SETUP.md`](SETUP.md). Specialized workflows are documented in [`AGENCY_TOOLS.md`](AGENCY_TOOLS.md) and [`BATCH_SMART_BIDDING.md`](BATCH_SMART_BIDDING.md).

## Write behavior

Normal mutations follow:

`propose -> preview -> confirm -> execute -> audit`

A typical write returns:

```json
{
  "status": "pending_confirmation",
  "pending_action_id": "...",
  "risk_level": "standard|spend|destructive|sensitive",
  "description": "...",
  "durable": true
}
```

Use `confirm_pending_action(action_id)` to execute, `cancel_pending_action(action_id)` to discard, `list_pending_actions()` to inspect proposals, and `get_audit_action(action_id)` to inspect all attempts for one action.

With the built-in SQLite audit backend, pending actions are durable across process restarts when their public MCP invocation can be reconstructed. Invocation arguments are encrypted at rest. See `SAFETY.md`.

## Accounts, MCC, access and links

Core operator surfaces include:

- `list_accessible_customers`
- `get_account_hierarchy`
- `get_account_summary`
- `create_customer_client`
- manager-link invite / accept / decline / cancel / unlink / move lifecycle
- account users and invitations
- billing setup and invoice reads
- account budget lifecycle
- ProductLink / ProductLinkInvitation lifecycle
- legacy AccountLink lifecycle
- DataLink and third-party app analytics links
- Google Ads ↔ YouTube link request / accept / reject / revoke / remove lifecycle

### Multi-customer isolation

When `GOOGLE_ADS_MCP_ALLOWED_CUSTOMER_IDS` is configured, reads and writes outside the deployment scope are blocked. Mutations recursively inspect customer-scoped resource references, including nested references in CREATE operations.

Intentional cross-account manager/client linking is allowed only through the explicit linking path and only when the second customer also passes the deployment allowlist.

## Reporting and GAQL

The MCP exposes focused reports for the common operator views plus a raw GAQL fallback. Coverage includes campaigns, ad groups, keywords, ads, search terms, devices, geography, assets, audiences, quality score, policy/disapproval, Shopping performance and change history.

Use raw GAQL when a newly added selectable field does not yet deserve a dedicated convenience tool.

## Campaigns and administration

Supported operator workflows include:

- campaign create / rename / pause / enable / remove
- campaign groups
- campaign drafts and promotion
- Search and generic supported campaign shells
- Standard Shopping
- Demand Gen
- Performance Max
- Smart Campaign workflows
- campaign-level targeting, schedules and exclusions
- automatic-asset removal controls
- campaign/ad-group bid modifiers
- account-level negative criteria

Campaign creation defaults to conservative states where the workflow supports it; major creation helpers create PAUSED resources rather than silently starting spend.

Legacy Local and Smart Shopping creation are intentionally not emulated on obsolete contracts. Use Performance Max.

## Budgets and bidding

Budget and bidding coverage includes:

- campaign budget create/update
- Manual CPC
- Maximize Clicks
- Maximize Conversions
- Maximize Conversion Value
- Target CPA
- Target ROAS
- Target Impression Share
- portfolio/shared bidding strategies
- device and interaction bid modifiers
- Smart Bidding seasonality adjustments
- Smart Bidding data exclusions

Spend-changing operations are centrally classified as `spend` risk.

## Ad groups, ads and creatives

Ad-group lifecycle includes create, status and CPC updates.

Creative coverage includes:

- Responsive Search Ads
- Responsive Display Ads
- Demand Gen image/video creatives
- RSA editing
- Call Ad compatibility via supported RSA + Call Asset flow
- legacy VIDEO creation blocked safely; use Demand Gen video
- ad status/remove
- ad previews where supported

## Assets and AssetSets

The MCP covers common assets and the broader v25 asset-link graph:

- sitelink
- call
- image
- promotion
- callout
- structured snippet
- Business Message / WhatsApp compatibility path
- customer assets
- campaign assets
- ad-group assets
- AssetSets at customer/campaign/ad-group scope
- status/remove operations where exposed
- YouTube upload/status/update/remove where account eligibility permits

Remote image fetching is SSRF-hardened: public HTTPS only, public DNS/IPs, redirect revalidation, MIME allowlist and bounded response size.

## Keywords, negatives and planning

Keyword operations include:

- add
- status/remove
- CPC bid update
- match-type replacement
- campaign/ad-group negatives
- shared negative keyword lists
- bulk operations

Planning includes:

- keyword ideas
- historical metrics
- forecast metrics
- persistent KeywordPlan / campaign / ad-group / keyword lifecycle
- Smart Campaign KeywordThemeConstant suggestions
- Reach Planner v25 request coverage

## Audiences, remarketing and Customer Match

Audience workflows include:

- website remarketing lists
- user-list attachment/detachment
- affinity/in-market segments
- topic targeting
- Audience / CustomAudience / CustomInterest resources
- UserListCustomerType
- RemarketingAction + tag/event snippets
- Customer Match through eligible Google Ads API flows
- Data Manager Customer Match support
- small synchronous UserDataService uploads

Customer identifiers are kept out of normal mutation audit payloads; sensitive invocation arguments needed for durable replay are encrypted at rest.

## Conversions and goals

Measurement coverage includes:

- conversion actions
- offline conversions
- enhanced conversions
- retractions/restatements
- conversion custom variables
- conversion value rules and rule sets
- customer/campaign conversion goals
- lifecycle/acquisition/retention/loyalty goal controls supported by v25
- SKAdNetwork conversion-value schema controls

v25 unified goal contracts are used; removed legacy lifecycle goal services are not referenced.

## Performance Max

PMax coverage includes:

- campaigns
- complete asset groups
- text/image/video assets
- brand-guidelines migration
- audience/search-theme/Local Services/vertical-feed signals
- full listing-group filter replacement
- Shopping product dimensions
- RETAIL Product Tags via `retail_filter_bundle`
- WEBPAGE filters, including multiple permitted root filters
- preview/shareable surfaces where supported
- travel asset suggestions

Listing-tree replacement uses atomic mutation where the related resources must succeed or fail together.

## Experiments

Experiment coverage includes:

- experiment create/update/remove
- schedule
- async error inspection
- promote
- graduate
- end
- ExperimentArm list/create/update/remove
- `update_experiment_traffic_split` for atomic two-arm split changes

The split helper updates both arms in a single request and validates the total=100 invariant before the Google Ads RPC.

## Recommendations and batch operations

Recommendations can be listed, generated where supported, applied or dismissed. Application is spend-risk.

Batch Jobs expose a constrained reviewed manifest instead of arbitrary raw protobuf mutation. Batch results can partially succeed; always inspect row-level outcomes with the batch result tool.

See `BATCH_SMART_BIDDING.md`.

## Specialist and Google-controlled services

The MCP includes wrappers for specialist v25 surfaces where Google controls account eligibility, including:

- Identity Verification
- Incentives
- Multi-Party Authorization reviews
- Local Services leads/conversations/feedback
- Audience Insights
- Benchmarks
- Content Creator Insights
- AssetGeneration text/image generation

These tools do not fake entitlement. If the authenticated Google Ads account is not allowlisted/eligible for the upstream service, the Google API error is returned.

`ReservationService` is not exposed because Google documents it as not publicly available.

## Safety tools

- `list_pending_actions()`
- `confirm_pending_action(action_id)`
- `cancel_pending_action(action_id)`
- `get_recent_audit_log(limit=20)`
- `get_audit_action(action_id)`

## Compatibility boundaries

- Google Ads API target: **v25**
- Python: **3.11+**
- Google Ads Python client: tested/pinned to the 31.x line
- `stdio` is the recommended/default MCP transport
- raw HTTP is blocked unless explicitly enabled behind an external authenticated/restricted boundary
- Merchant Center feed/catalog management remains outside this MCP
- Google Business Profile administration remains outside this MCP

## Detailed references

- [`V25_SERVICE_COVERAGE.md`](V25_SERVICE_COVERAGE.md) — service-level coverage contract
- [`RELEASE_0.16.0.md`](RELEASE_0.16.0.md) — 0.16 release details and validation status
- [`SAFETY.md`](SAFETY.md) — approval, isolation, audit and replay policy
- [`SETUP.md`](SETUP.md) — installation, OAuth, MCC and production configuration
- [`AGENCY_TOOLS.md`](AGENCY_TOOLS.md) — agency administration workflows
- [`BATCH_SMART_BIDDING.md`](BATCH_SMART_BIDDING.md) — Batch Jobs and Smart Bidding event controls

When a new Google Ads API version is adopted, update the service coverage matrix first, then this index only for user-visible workflow changes.