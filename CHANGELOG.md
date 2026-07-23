# Changelog

## Unreleased

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
