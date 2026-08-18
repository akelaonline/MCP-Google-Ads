# Changelog

## 0.13.0 — 2026-08-18

### Added
- **Customer isolation:** optional `GOOGLE_ADS_MCP_ALLOWED_CUSTOMER_IDS` scopes reads, writes, and account discovery to known Google Ads customer IDs.
- **Strict deployment mode:** `GOOGLE_ADS_MCP_REQUIRE_CUSTOMER_ALLOWLIST=true` refuses startup when no customer scope is configured.
- **Risk-aware approvals:** write actions are centrally classified as `standard`, `spend`, `destructive`, or `sensitive`.
- Separate production auto-approve controls for spend, destructive, and sensitive/account-access actions; all default to false.

### Changed
- Production `GOOGLE_ADS_MCP_AUTO_APPROVE=true` now auto-executes only standard-risk writes unless a high-risk category is explicitly opted in.
- Customer scope is enforced in both the Google Ads client wrapper and the safety layer for defense in depth.
- Pending actions now expose `risk_level` and `confirmation_reason`.
- README, setup, safety documentation, and environment examples now include the recommended multi-client deployment model.

### Compatibility
- Deployments without a customer allowlist retain the previous account scope.
- Internal/direct `SafetyLayer(auto_approve=True)` callers that omit the new policy parameters retain legacy execution semantics; the production context always passes explicit high-risk policy settings.

See `docs/RELEASE_0.13.0.md` for full release and deployment notes.

## 0.12.1 — 2026-08-18

### Fixed
- **P0 production safety:** `create_video_ad` no longer attempts an unsupported legacy VIDEO mutation. Google Ads API v25 only permits fetching/reporting for legacy VIDEO campaigns; the compatibility endpoint now fails safe with a structured `unsupported` result and zero mutation.
- Added real-v25 contract coverage so a legacy `ad.video_ad` write path cannot silently return.

### Added
- **`create_demand_gen_video_ad`** — supported programmatic video path using `DemandGenVideoResponsiveAd`, existing YouTube video IDs, square logos, text assets and an atomic multi-resource mutation. Created PAUSED.

### Changed
- Version bumped to 0.12.1 and docs now distinguish legacy VIDEO reporting from Demand Gen video creation.

## 0.12.0 — 2026-08-18

### Fixed
- Google Ads API v25 compatibility and hardening across campaigns, ads, assets, PMax, bidding, targeting, audiences, conversions, recommendations, atomic writes, SSRF protections and audit/retry behavior. See `docs/RELEASE_0.12.0.md` for the full release notes.

## 0.11.0 — 2026-08-13

### Added
- **Callout and structured snippet extensions** (`tools/assets.py`) — the two remaining common Search extension types that weren't yet covered (sitelinks, calls, messages, images, and promotions already were).
  - `create_callout_asset` — one or more short trust-signal callouts (e.g. "Envío gratis"), attached in a single call.
  - `create_structured_snippet_asset` — a labeled list under a fixed header (e.g. "Servicios": ["Implantes", "Ortodoncia", ...]).

### Notes
- Round 6 of the coverage pass (started 0.6.0).

## 0.10.0 — 2026-08-13

### Added
- **Affinity / In-Market / Custom-Intent + Topic targeting** (`tools/audiences.py`) — Google's predefined interest/purchase-intent segments and Display/YouTube topic targeting, distinct from remarketing/Customer Match lists (which were already covered).
  - `search_user_interests` — look up segment IDs by name.
  - `add_in_market_or_affinity_audience` — attach a segment to an ad group.
  - `add_topic_targeting` — target or exclude a Display/YouTube topic on an ad group (e.g. brand-safety exclusions).

### Notes
- Round 5 of the coverage pass (started 0.6.0). Remaining known gaps are low-priority/rarely-used: Smart campaigns (small-advertiser simplified flow), legacy Display "similar audiences" (deprecated by Google), and a handful of read-only reports not yet wrapped. Flag anything specific still needed.

## 0.9.0 — 2026-08-13

### Added
- **Shopping/Merchant performance reporting** (`tools/reporting.py`).
  - `get_shopping_performance_report` — per-product (SKU-level) impressions/clicks/cost/conversions via `shopping_performance_view`, to see which products drive results vs. burn spend with none.
  - `list_shopping_products` — distinct products currently eligible to serve, read from the Google Ads side (not Merchant Center itself — feed/catalog management stays out of scope, same disclaimer as `create_shopping_campaign`).
- **Conversion Value Rules** (`tools/conversions.py`).
  - `create_conversion_value_rule` — adjust reported conversion value by geography, audience, or device (MULTIPLY or SET), so value-based bidding optimizes toward the segments that actually matter.
  - `list_conversion_value_rules` — read-only listing.
- **PMax asset group signals** (`tools/performance_max.py`) — closes the one gap called out in the 0.6.0 module docstring.
  - `add_asset_group_signal` — audience or search-theme signal to steer PMax's automated targeting.
  - `list_asset_group_signals` — read-only listing.
- **Campaign experiments (A/B trials)** (`tools/experiments.py`, new module).
  - `create_experiment` — branch a trial arm off a base campaign with a traffic split; edit the trial arm afterward with the normal campaign/bidding/ads tools.
  - `list_experiments`, `promote_experiment` (apply trial changes permanently — irreversible), `end_experiment` (discard trial, base campaign unaffected).

### Notes
- Round 4 of the coverage pass (started 0.6.0). This closes out every gap identified in the original audit except a handful of low-priority/rarely-used surfaces (e.g. Smart campaigns for very small advertisers, some legacy Display targeting types) — flag anything specific still missing and it goes in the next round.

## 0.8.0 — 2026-08-13

### Added
- **Call Ads** (`tools/ads.py`).
  - `create_call_ad` — phone-only ad format with no landing page, just a "Call" button; high-intent format for services/B2B where a phone conversation is the actual conversion. Created PAUSED.
- **Demand Gen campaigns** (`tools/ads.py`) — formerly Discovery Ads, runs on Discover feed, Gmail, and YouTube in-feed/Shorts.
  - `create_demand_gen_campaign` — campaign shell (Target CPA or Maximize Conversions), created PAUSED.
  - `create_demand_gen_ad` — multi-asset ad (headlines/descriptions/business name/marketing+logo images), created PAUSED.
- **Placement exclusions** (`tools/targeting.py`).
  - `add_placement_exclusion` — exclude a specific Display/YouTube placement (website, YouTube channel/video, or mobile app) from a campaign, for when the placement report shows spend with no results.

### Notes
- Round 3 of the coverage pass (started 0.6.0). Still open for a future round: campaign experiments (A/B / Trials), asset group signals (PMax audience/search-theme signals), Conversion Value Rules, Shopping/Merchant performance reporting.

## 0.7.0 — 2026-08-13

### Added
- **Advanced bidding strategies** (`tools/bidding.py`) — round 2 of the API coverage pass.
  - `set_maximize_conversion_value` — optimize for total conversion value instead of count (e-commerce/Shopping).
  - `set_target_impression_share` — bid for a target % share of a page location (ANYWHERE_ON_PAGE/TOP_OF_PAGE/ABSOLUTE_TOP_OF_PAGE), for brand-defense/visibility campaigns.
  - `create_portfolio_bidding_strategy`, `attach_shared_bidding_strategy`, `list_portfolio_bidding_strategies` — shared (portfolio) TARGET_CPA/TARGET_ROAS strategies via `BiddingStrategyService`, so multiple campaigns can learn from one shared optimization pool.
- **In-place keyword editing** (`tools/keywords.py`) — previously `update_keyword_status` could only change status, not bid or match type.
  - `update_keyword_bid` — change max CPC without recreating the keyword.
  - `update_keyword_match_type` — `match_type` is immutable on `KeywordInfo` in the API, so this does the correct workaround: adds the same keyword text under the new match type and removes the old one in a single atomic batch (preserving cpc_bid), so there's no gap in coverage.
- **Bulk campaign status** (`tools/bulk.py`).
  - `bulk_update_campaign_status` — pause/enable/remove many campaigns in one call, matching the existing bulk keyword/ad status tools.
- **MCC/client account onboarding** (`tools/accounts.py`).
  - `create_customer_client` — create a new client account under an MCC, auto-linked.
  - `list_manager_links` / `accept_manager_link` — inspect and accept MCC access invitations for an existing client account (the counterpart flow when the client account already exists, vs. `create_customer_client` for a brand-new one).

### Notes
- Round 2 of the coverage pass started in 0.6.0. Still open for a future round: Call/Demand Gen ad formats, campaign experiments (A/B / Trials), asset group signals (PMax audience/search-theme signals), Conversion Value Rules, and placement exclusions.

## 0.6.0 — 2026-08-13

### Added
- **RSA in-place editing** (`tools/ads.py`).
  - `update_responsive_search_ad` — replace headlines/descriptions/final_urls/path1/path2 of an existing ad without removing and recreating it (which previously meant losing accumulated Ad Strength history and serving data).
  - `get_ad_strength` — read-only report of RSA Ad Strength ratings (PENDING/NO_ADS/POOR/AVERAGE/GOOD/EXCELLENT) and policy approval status.
- **Performance Max: images, video, status, and Shopping scoping** (`tools/performance_max.py`) — closes the two biggest documented gaps from 0.5.0 (image assets were explicitly "attach via the UI for now"; listing group filters and asset group status were unbuilt).
  - `add_asset_group_image_asset` — download a public image URL and attach it to an asset group as MARKETING_IMAGE / SQUARE_MARKETING_IMAGE / PORTRAIT_MARKETING_IMAGE / LOGO / LANDSCAPE_LOGO.
  - `add_asset_group_video_asset` — link an existing YouTube video into an asset group.
  - `update_asset_group_status` — pause/enable a single asset group independent of the campaign.
  - `add_asset_group_listing_filter` / `list_asset_group_listing_filters` — scope which products from a linked Shopping feed an asset group can advertise (by brand, item ID, product type, or condition), via `AssetGroupListingGroupFilterService`.
- **Conversion action creation + Enhanced Conversions** (`tools/conversions.py`) — previously conversion actions could only be listed/edited, never created from the MCP.
  - `create_conversion_action` — create a new WEBSITE conversion action (category + counting type + optional default value), created ENABLED.
  - `upload_enhanced_conversion` — like `upload_offline_conversion` but with SHA-256-hashed email/phone user identifiers for better match rate as click-ID-only tracking degrades. Hashing happens locally; raw PII is never sent as-is.
- **Policy/disapproval visibility** (`tools/reporting.py`).
  - `get_disapproved_ads` — ads that are disapproved, policy-limited, or under review, with the specific policy topic. Read-only.

### Notes
- This is round 1 of a broader coverage pass against the full Google Ads API (see the audit that motivated this release). Still open for a future round: portfolio bidding strategies, Maximize Conversion Value, keyword bid/match-type editing in place, Call/Demand Gen ad formats, campaign experiments (A/B), CustomerClientLink management, and asset group signals.

## 0.5.0 — 2026-08-11

### New capabilities
- **Keyword Planner directly inside Claude** (`tools/keyword_planner.py`).
  - `generate_keyword_ideas` — search-volume, competition, and CPC bid ranges from seed keywords or a URL via `KeywordPlanIdeaService.GenerateKeywordIdeas`.
  - `get_keyword_historical_metrics` — volume/CPC lookup for a fixed keyword list without idea expansion.
  - Input validation for `customer_id`, `language`, `limit`, `keywords`, and `page_url`; extended language coverage in `LANGUAGE_IDS`.
- **Google Ads recommendations workflow** (`tools/recommendations.py`).
  - `get_recommendations` lists active recommendations with optional type filtering.
  - `apply_recommendation` and `dismiss_recommendation` run through the existing safety propose/confirm layer.
- **Quality Score reporting** (`tools/reporting.py`).
  - `get_quality_score_report` buckets keyword performance by Quality Score to surface low-QS drag on CPCs.

### Engineering
- Centralized customer-ID helpers in `src/google_ads_mcp/helpers.py` (`normalize_customer_id`, `is_valid_customer_id`).
- Added structured logging via `src/google_ads_mcp/logging_config.py`, controlled by `GOOGLE_ADS_MCP_LOG_LEVEL`.
- Added `Makefile` and `scripts/smoke_test.py` for install / test / smoke-test workflows, plus lint/format placeholders.
- Added `.github/workflows/tests.yml` CI running the full pytest suite on Python 3.11, 3.12, and 3.13.

### Tests
- `tests/test_keyword_planner.py` covers idea generation, historical metrics, argument validation, and error handling.
- `tests/test_recommendations.py` covers apply and dismiss recommendation flows.
- Suite now totals **77 tests**, all passing.

Todas las versiones siguen [Semantic Versioning](https://semver.org/):
`MAJOR.MINOR.PATCH`. Un fix de bug sin romper compatibilidad sube el
`PATCH` (0.1.0 → 0.1.1), una herramienta nueva sube el `MINOR`, un cambio
que rompe algo existente (firma de una tool, comportamiento por defecto)
sube el `MAJOR`.

Al agregar una entrada nueva: crear una sección `## X.Y.Z — YYYY-MM-DD`
arriba de todo (la más reciente siempre primero), con subsecciones
`### Added` / `### Fixed` / `### Changed` según corresponda. No mezclar
fixes de distintas fechas en la misma sección — cada versión pusheada al
repo es una entrada nueva.

## 0.4.0 — 2026-07-24

### Added
- **`tools/targeting.py` — closes a real gap: campaigns created by this MCP
  had no way to set location, language, dayparting, or device bid
  modifiers.** Without this, a brand-new campaign defaults to "All
  countries and territories," which is essentially never what an agency
  wants.
  - `add_location_targeting` — accepts common place names ("argentina",
    "buenos aires") via a small built-in lookup table, or a raw geo target
    constant ID for anything else. Supports exclusion (`negative=True`).
  - `set_language_targeting`, `add_ad_schedule` (dayparting, with optional
    bid modifier), `set_device_bid_modifier`.
  - `list_campaign_criteria` — read-only view of everything targeting-related
    on a campaign in one call (locations, languages, schedules, device
    modifiers, negatives together).
- **`tools/campaign_types.py` — Shopping and Local campaigns.**
  - `create_shopping_campaign` — campaign shell only; explicitly documented
    prerequisite (a product feed already live and linked in Google Merchant
    Center, a separate API this MCP does not wrap) so it doesn't imply more
    coverage than it has.
  - `create_local_campaign` — campaign + its core text/business-name asset,
    for physical-location businesses (relevant for e.g. real estate or
    clinic accounts with a storefront).
- **Four new reports** in `tools/reporting.py`: `get_geographic_performance`
  (spend by actual user location, not targeted location — the tool for
  catching spend leaking outside your intended area), `get_device_performance`,
  `get_asset_performance` (which specific creative piece is pulling weight),
  and `get_audience_performance`.
- **Documented, not silently skipped: `docs/TOOLS.md` is explicit about
  where Shopping and Local campaigns depend on infrastructure outside
  Google Ads itself** (Merchant Center, Business Profile) — the tool
  creates what the Ads API can create and says plainly what it can't.
- 18 new tests (`test_targeting_tools.py`, `test_campaign_types_tools.py`),
  plus `tests/conftest.py` extended with the new enums these modules touch
  (`DayOfWeekEnum`, `DeviceEnum`, `AdvertisingChannelSubTypeEnum`, etc.).
  66 tests total, all passing; every module still imports and registers
  cleanly against a real `FastMCP` instance (verified separately from the
  unit tests, which run against fakes).

## 0.3.0 — 2026-07-24

### Added
- **`tools/audiences.py` — full audience lifecycle**, not just attaching an
  existing list:
  - `create_remarketing_list` — website-visitor list (requires the site tag
    to already be installed; does not backfill past traffic).
  - `create_customer_match_list` + `upload_customer_match_members` —
    contact-based audiences. Emails/phones are SHA-256 hashed locally
    before upload; this tool never transmits raw PII.
  - `remove_audience_from_ad_group` — the missing counterpart to
    `attach_audience_to_ad_group`.
- **`tools/performance_max.py` — PMax campaign + asset group creation.**
  `create_performance_max_campaign` (shell, PAUSED) and `create_asset_group`
  (text-only: headlines/long headline/descriptions/business name, PAUSED).
  Deliberately does NOT wrap listing group filters or asset group
  signals yet — those need their own careful design, and a half-built
  version would be riskier than not having it.
- **Image and promotion campaign assets**, added to `tools/assets.py`:
  `create_image_asset` (downloads from a URL, uploads, attaches) and
  `create_promotion_asset` (percent-off or flat-amount-off extension).
- **`tools/bulk.py` — batch operations in a single API call** instead of
  one round-trip per item: `bulk_update_keyword_status` and
  `bulk_update_ad_status` (both can span multiple ad groups in one call),
  and `bulk_add_negative_keywords_multi_scope` (roll the same negative
  list out across many campaigns/ad groups at once — e.g. applying the
  Instituto Cambridge negative list to every active campaign in the
  account in one shot instead of one `add_negative_keywords` call per
  campaign).
- **Display and video ad creation**, added to `tools/ads.py`:
  `create_responsive_display_ad` (with image upload) and `create_video_ad`
  (in-stream YouTube, referencing an existing video by ID).
- **Documented a real API limitation instead of faking support for it**:
  Google Ads' UI-only "Automated Rules" have no corresponding API
  resource — `docs/TOOLS.md` now has a "Not supported — by design" section
  explaining this instead of the MCP silently doing nothing or the docs
  staying silent about the gap.
- 27 new tests (`test_audiences_tools.py`, `test_performance_max_tools.py`,
  `test_bulk_tools.py`, `test_image_promotion_assets.py`), plus a shared
  `tests/conftest.py` fake-client fixture set (auto-vivifying proto
  builder, fake mutate results, fake MCP registrar) so new tool modules
  don't have to re-implement the same fakes. `test_mutate_method_name.py`
  extended to cover every new service these modules touch (`UserListService`,
  `AssetGroupService`, `AssetGroupAssetService`) — the exact class of bug
  fixed in 0.1.1, now guarded against for the new surface area too.

## 0.2.0 — 2026-07-23

### Added
- **`tools/assets.py` — campaign-level assets (sitelinks, call, message).**
  Closes the biggest real-world gap found while operating a WhatsApp-driven
  account: previously an ad could only push users to the landing page and
  hope they found the contact button there. Each `create_*_asset` tool
  does the create-then-link flow (AssetService, then CampaignAssetService)
  in one call, so a single `confirm_pending_action` either creates and
  attaches the asset or does nothing at all.
  - `create_sitelink_asset` — extra links under the ad (e.g. "Ver cursos", "Sucursales").
  - `create_call_asset` — click-to-call extension.
  - `create_message_asset` — click-to-message (WhatsApp/SMS): opens a chat
    directly from the ad, with a pre-filled message and business name.
    This is the tool that lets "WhatsApp is our real conversion" actually
    be reflected in the ad itself, not just the landing page.
  - `list_campaign_assets` — read-only, what's attached to a campaign today.
  - `remove_campaign_asset` — detach without deleting the underlying asset.
- **Conversion action lifecycle management**, added to `tools/conversions.py`:
  - `update_conversion_action_status` — ENABLED/REMOVED/HIDDEN. Prefer
    over deleting a conversion action when the goal is just to stop it
    from being counted.
  - `set_conversion_action_counting` — include/exclude an action from the
    account's primary Conversions metric and from automated bidding
    (Maximize Conversions / Target CPA / Target ROAS all optimize toward
    this), without touching whether the action keeps recording data. This
    is the fix for the exact situation found auditing Instituto Cambridge:
    a soft signal (a quiz/"Test de Nivel" completion) outweighing the real
    business conversion (WhatsApp contact) in what Smart Bidding
    optimizes for. Excluding it from counting stops that without losing
    the historical data or breaking any existing report.
- 9 new tests in `tests/test_assets_tools.py` covering the create-then-link
  flow, input validation (character limits), and both conversion-action
  tools. `tests/test_mutate_method_name.py` extended to cover the three
  new services this module touches (`AssetService`, `CampaignAssetService`,
  `ConversionActionService`).

## 0.1.3 — 2026-07-23

### Added
- **Changelog is now surfaced from the README** — a version badge and a
  "Changelog" link in the top nav bar, plus a row in the Documentation
  table, so anyone landing on the repo sees at a glance that it's
  actively maintained and where to check what changed.

### Changed
- **Quick start now verifies the install instead of assuming it worked.**
  Added a one-line smoke test (`import google_ads_mcp`) right after
  `pip install -e .`, with an explicit "if this fails, nuke and rebuild
  the venv" fallback — this is the exact failure mode documented in
  0.1.2, now caught at setup time instead of surfacing later as an
  intermittent Claude Desktop connection failure.
- **MCP config example now points at `.venv/bin/python` directly**
  instead of a bare `python`, since Claude Desktop launches the server
  with its own `PATH` that may not resolve to the intended virtualenv —
  this was the root cause of the "works in terminal, fails in Claude"
  reports.

## 0.1.2 — 2026-07-23

### Fixed
- **Documented a corrupted-venv failure mode** seen in the wild: a macOS
  Finder folder merge (e.g. copying/dragging an old project checkout on
  top of this one) leaves `.venv` with duplicated entries suffixed
  `" 2"` (`.venv/bin/python 2`, `.venv/lib 2`, etc.). The mix of stale and
  current site-packages causes `ModuleNotFoundError: No module named
  'google_ads_mcp'` to appear intermittently across Claude Desktop
  restarts, which is confusing to debug from the MCP error log alone since
  it looks identical to "package never installed." Added a
  `docs/SETUP.md` troubleshooting entry describing the `" 2"` file
  signature and the fix (`rm -rf .venv && python -m venv .venv && pip
  install -e .`), plus a one-liner to spot other merged/duplicated files
  in the project root.

## 0.1.1 — 2026-07-23

### Fixed
- **Every mutation on a `*CriterionService` failed at confirm time** (e.g.
  `add_negative_keywords`, `update_keyword_status`, `remove_keyword`,
  `add_keywords`), with errors like
  `'CampaignCriterionServiceClient' object has no attribute
  'mutate_campaign_criterions'`. `_mutate_method_name` derived the RPC
  method name by blindly appending "s" to the snake_cased service name,
  which produces `mutate_campaign_criterions` / `mutate_ad_group_criterions`
  — neither exists on the real client (the correct, irregular plural is
  `..._criteria`). Added an explicit irregular-plural lookup table
  (`_IRREGULAR_MUTATE_METHODS`) covering `CampaignCriterionService`,
  `AdGroupCriterionService`, `AssetGroupCriterionService`, and
  `CustomerNegativeCriterionService`, plus a clear `GoogleAdsMcpError`
  (instead of a raw `AttributeError`) if a future service is still missing
  from the table.
- **`create_campaign_budget` / `update_campaign_budget` failed at confirm
  time** with `unexpected keyword argument 'partial_failure'`.
  `GoogleAdsClientWrapper.mutate` unconditionally passed `partial_failure`
  and `validate_only` to every mutate RPC, but some services (e.g.
  `CampaignBudgetService.mutate_campaign_budgets`) don't accept either.
  `mutate()` now inspects the target method's signature and only forwards
  the kwargs it actually declares.
- Added `tests/test_mutate_method_name.py` covering both regressions,
  including a guard that no `*CriterionService` ever resolves to a
  `..._criterions` method name.

## 0.1.0 — Initial release
Created by Akela (https://github.com/akelaonline).

- Full read/write Google Ads MCP server on the official `google-ads` Python client (API v20).
- ~40 tools across accounts, reporting (GAQL + pre-built reports), campaigns, budgets, bidding
  strategies, ad groups, responsive search ads, keywords/negatives, audiences, and offline
  conversion upload.
- Human-in-the-loop safety layer: every write proposes a change and requires
  `confirm_pending_action` before it executes, with an opt-in `GOOGLE_ADS_MCP_AUTO_APPROVE`
  for automated pipelines.
- SQLite audit log of every executed mutation.
- stdio and HTTP transports (FastMCP).
- OAuth refresh-token helper (`python -m google_ads_mcp.auth --generate-refresh-token`).
