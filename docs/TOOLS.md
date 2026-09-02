# Tool reference — v0.16 / Google Ads API v25

This file is the **living operator index** for Google Ads MCP. It intentionally stays compact so it can remain current as the tool surface grows.

For the authoritative service-by-service API coverage map, use [`V25_SERVICE_COVERAGE.md`](V25_SERVICE_COVERAGE.md). For production policy, use [`SAFETY.md`](SAFETY.md) and [`SETUP.md`](SETUP.md). Specialized workflows are documented in [`AGENCY_TOOLS.md`](AGENCY_TOOLS.md) and [`BATCH_SMART_BIDDING.md`](BATCH_SMART_BIDDING.md).

## Operating modes

The MCP supports three deliberate deployment modes:

1. **Read-only** — `GOOGLE_ADS_MCP_READ_ONLY=true`. Reporting, GAQL, audit inspection and pending cancellation remain available; new write proposals and pending confirmations are blocked centrally.
2. **Write-capable with confirmation** — `GOOGLE_ADS_MCP_READ_ONLY=false` and `GOOGLE_ADS_MCP_AUTO_APPROVE=false`. Recommended for live accounts.
3. **Controlled automation** — global auto-approve can be enabled, but `spend`, `destructive` and `sensitive` classes still require their own explicit opt-ins.

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

With the built-in SQLite audit backend, pending actions are durable across process restarts when their public MCP invocation can be reconstructed. Invocation arguments are encrypted at rest. `confirm` and `cancel` are serialized inside one running MCP process to prevent double confirmation races. One running process should own one pending-action database; the SQLite store is not a distributed claim/lease system. See `SAFETY.md`.

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

MCC hierarchy/link reads are also filtered centrally. Rows from `customer_client`, `customer_client_link`, and `customer_manager_link` that reference customers outside the allowlist are removed before they are returned, including through raw GAQL. If a hierarchy/link query omits the ownership field needed to identify the referenced customer safely, the query fails closed rather than returning ambiguous cross-tenant metadata.

Intentional cross-account manager/client linking is allowed only through the explicit linking path and only when the second customer also passes the deployment allowlist.

## Reporting and GAQL

The MCP exposes focused reports for the common operator views plus a raw GAQL fallback. Coverage includes campaigns, ad groups, keywords, ads, search terms, devices, geography, assets, audiences, quality score, policy/disapproval, Shopping performance, search impression share / lost-IS budget & rank diagnostics, and change history.

Use raw GAQL when a newly added selectable field does not yet deserve a dedicated convenience tool. Deployment customer isolation still applies to raw GAQL.

## Campaigns and administration

Supported operator workflows include:

- campaign create / rename / pause / enable / remove
- campaign groups
- campaign drafts and promotion
- Search and generic supported campaign shells
- Standard Shopping (including listing-group/product-group trees via `shopping_listing_groups`)
- Demand Gen
- Performance Max
- Smart Campaign workflows
- campaign-level targeting, schedules (add/update/remove) and exclusions
- tracking URL templates, final URL suffixes and custom URL parameters at account/campaign/ad-group level
- automatic-asset removal controls
- campaign/ad-group bid modifiers
- account-level negative criteria
- Dynamic Search Ads campaigns, DSA ad groups (`SEARCH_DYNAMIC_ADS`) and webpage targets
- App campaigns (ACi/ACe) with v25 `MULTI_CHANNEL` + `app_campaign_setting`

Campaign creation defaults to conservative states where the workflow supports it; major creation helpers create PAUSED resources rather than silently starting spend.

Standard ad previews (`AdService.generate_preview`) no longer exist in the v25 API; use PMax shareable previews (`generate_pmax_shareable_previews`) or YouTube previews where the surface applies.

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

Ads explicitly created `PAUSED` may remain `standard`. Editing an existing RSA is `spend` because it can immediately change live delivery.

## Assets and AssetSets

The MCP covers common assets and the broader v25 asset-link graph:

- sitelink
- call
- image
- promotion
- callout
- structured snippet
- lead form
- price
- location (account-level)
- mobile app / app deep link
- Business Message / WhatsApp compatibility path
- customer assets
- campaign assets
- ad-group assets
- AssetSets at customer/campaign/ad-group scope
- status/remove operations where exposed
- YouTube upload/status/update/remove where account eligibility permits

Risk follows effect rather than naming: resource-only preparation may be `standard`, while helpers that create **and attach** sitelink/call/image/promotion/callout/snippet/Business Message assets to live delivery are `spend`, matching the generic `attach_asset_*` policy.

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

Keyword creation, match-type changes and negative targeting are treated as `spend` risk because they can change delivery even without an explicit bid amount in the request.

Planning includes:

- keyword ideas
- historical metrics
- forecast metrics
- persistent KeywordPlan / campaign / ad-group / keyword lifecycle
- Smart Campaign KeywordThemeConstant suggestions
- Reach Planner v25 request coverage

## Audiences, targeting and Customer Match

Audience/targeting workflows include:

- website remarketing lists
- user-list attachment/detachment
- affinity/in-market segments
- topic targeting
- location/language/placement targeting and exclusions (including positive placements for Display/YouTube)
- audience exclusions at ad-group and campaign level
- Audience / CustomAudience / CustomInterest resources
- UserListCustomerType
- RemarketingAction + tag/event snippets
- Customer Match through eligible Google Ads API flows
- Data Manager Customer Match support
- small synchronous UserDataService uploads

Live targeting changes are conservatively treated as `spend` risk. Customer identifiers are kept out of normal mutation audit payloads; sensitive invocation arguments needed for durable replay are encrypted at rest.

## Conversions and goals

Measurement coverage includes:

- conversion actions
- offline conversions (with optional GDPR `consent`)
- call conversions (`upload_call_conversion`, UPLOAD_CALLS actions)
- enhanced conversions (with optional GDPR `consent`)
- retractions/restatements
- conversion custom variables
- conversion value rules and rule sets
- customer/campaign conversion goals
- lifecycle/acquisition/retention/loyalty goal controls supported by v25
- SKAdNetwork conversion-value schema controls

v25 unified goal contracts are used; removed legacy lifecycle goal services are not referenced. Changes that alter whether a conversion/goal is biddable are treated as `spend` risk; first-party conversion uploads remain `sensitive`.

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
- `update_experiment_arm_traffic_splits` for atomic two-arm split changes
- `update_experiment_traffic_split` as a compatibility alias

The split helper updates both arms in a single request and validates the total=100 invariant before the Google Ads RPC. Traffic-split changes are `spend` risk.

## Recommendations and batch operations

Recommendations can be listed, generated where supported, applied or dismissed. Application is spend-risk.

Batch Jobs expose a constrained reviewed manifest instead of arbitrary raw protobuf mutation. Batch results can partially succeed; always inspect row-level outcomes with the batch result tool.

See `BATCH_SMART_BIDDING.md`.

## Merchant Center (Merchant API)

Separate from the Google Ads gRPC surface: a lightweight REST client for
`merchantapi.googleapis.com` (the replacement for Content API for Shopping,
which Google sunset 2026-08-18). Shares the Google Ads OAuth client; either
reuses `GOOGLE_ADS_REFRESH_TOKEN` (if generated with `--include-merchant-center`)
or a separate `GOOGLE_MERCHANT_CENTER_REFRESH_TOKEN`.

- **Config/status**: `get_merchant_center_configuration`
- **Accounts**: `list_merchant_center_accounts`, `get_merchant_center_account`, `list_merchant_center_sub_accounts`, `list_merchant_center_account_issues`
- **Products**: `list_merchant_center_products`, `get_merchant_center_product`, `list_merchant_center_product_issues` (disapproved/ineligible + why), `get_merchant_center_product_performance`, `search_merchant_center_reports` (raw MCQL, like `run_gaql_query` for Google Ads)
- **Product writes** (propose/confirm, same safety model): `insert_merchant_center_product` (create or update; Merchant API has no separate update call), `remove_merchant_center_product` (destructive risk)
- **Data sources (feeds)**: `list_merchant_center_datasources`, `get_merchant_center_datasource`, `fetch_merchant_center_datasource` (propose/confirm)

Merchant Center account IDs are numeric like Google Ads customer IDs and are
reused as the `customer_id` for pending-action/audit/allowlist purposes; a
configured `GOOGLE_ADS_MCP_ALLOWED_CUSTOMER_IDS` allowlist must also include
any Merchant Center account ID used with write tools.

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

In read-only mode, list/audit/cancel remain available, while propose/confirm paths are blocked.

## Compatibility boundaries

- Google Ads API target: **v25**
- Python: **3.11+**
- Google Ads Python client: tested/pinned to the 31.x line
- `stdio` is the recommended/default MCP transport
- raw HTTP is blocked unless explicitly enabled behind an external authenticated/restricted boundary
- one running process should own one `audit.db`
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