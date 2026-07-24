# Changelog

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
