# Google Ads MCP 0.16.5

**Release date:** 2026-08-21
**Google Ads API:** v25
**Release type:** expert-scope closure — GDPR consent on uploads, impression-share diagnostics, Standard Shopping listing groups, ad rotation

0.16.5 implements the four-item expert-scope plan produced by the bug-hunting review of 0.16.4.

## New tools

### GDPR consent on conversion uploads (`conversions.py`)
- `upload_offline_conversion(..., consent="GRANTED"|"DENIED")` and `upload_enhanced_conversion(..., consent=...)` now write the v25 `Consent` message (`ad_user_data` + `ad_personalization`, both `ConsentStatus`). Required for EEA conversions; omitted by default so non-EEA flows are unchanged.

### Search impression share (`reporting.py`)
- `get_impression_share_report(customer_id, date_range, campaign_id)` — per campaign:
  - `search_impression_share`, `search_exact_match_impression_share`
  - `search_top_impression_share`, `search_absolute_top_impression_share`
  - `search_budget_lost_impression_share` (+ top/absolute-top variants) — share lost to budget
  - `search_rank_lost_impression_share` (+ top/absolute-top variants) — share lost to ad rank
  Values are 0-1 fractions; `cost_micros` is converted to base currency.

### Standard Shopping listing groups (`shopping_listing_groups.py`, new module)
- `add_shopping_listing_group(customer_id, ad_group_id, listing_group_type, dimension, parent_criterion_id, bid_modifier)` — builds the v25 `AdGroupCriterion.listing_group` tree. Root is a SUBDIVISION with no dimension; children link via `parent_ad_group_criterion`. Supported dimensions:
  - `PRODUCT_BRAND` / `PRODUCT_ITEM_ID` / `PRODUCT_GROUPING` / `PRODUCT_LABELS` — string value
  - `PRODUCT_TYPE` — `level` (LEVEL1..LEVEL5) + `value`
  - `PRODUCT_CATEGORY` — `level` + `category_id` (Google's category ID)
  - `PRODUCT_CONDITION` / `PRODUCT_CHANNEL` / `PRODUCT_CHANNEL_EXCLUSIVITY` — enum value
- `update_shopping_listing_group` — bid modifier and/or status with a precise update mask.
- `remove_shopping_listing_group` — note SUBDIVISIONs with children must be removed bottom-up.
- `list_shopping_listing_groups` — reads the tree (type, parent, case value, path).

### Ad rotation (`campaigns.py`)
- `set_campaign_ad_rotation(customer_id, campaign_id, rotation)` — `OPTIMIZE`, `CONVERSION_OPTIMIZE`, `ROTATE`, `ROTATE_INDEFINITELY` via `campaign.ad_serving_optimization_status`.

## Contract notes (verified against real v25 protos, google-ads 31.2.0)
- `ProductCondition.NEW` is **3** in v25 (not 2); the fake enum was corrected and the contract test asserts the real value.
- The `Consent` message on `ClickConversion` mirrors the `CallConversion` shape (ad data + ad personalization), consistent with 0.16.4.
- `AdServingOptimizationStatusEnum.ROTATE_INDEFINITELY` is 5 in v25; asserted in the contract test.

## Validation
`python scripts/validate_local.py` green end-to-end:

```text
isolated smoke  -> SMOKE OK (54 tool modules, zero duplicate-tool warnings)
ruff check      -> All checks passed!
pytest -q       -> 305 passed
```

22 new tests, including `tests/test_v16_5_expert_scope_contracts.py` (real v25 protobuf build checks for the consent message, listing-group case values/update masks, and ad rotation).

As with every 0.16.x release, no live Google Ads account was exercised: all validation is offline/mocked. Live-account E2E remains the required separate step before production replacement.
