# Google Ads MCP 0.16.4

**Release date:** 2026-08-21
**Google Ads API:** v25
**Release type:** functional-gap closure — ad schedules, tracking URL options, call conversions, app campaigns and Dynamic Search Ads

0.16.4 closes the functional gaps identified in the 0.16.3 operator review (six gaps; one of them turned out to be a Google-side removal, not an MCP gap). It also fixes a latent v25 contract bug in Standard Shopping creation that only a live-account call would have surfaced.

## New tools

### Ad schedules (`targeting.py`)
- `update_ad_schedule(customer_id, campaign_id, criterion_id, start_hour, end_hour, bid_modifier)` — edits a daypart criterion with a precise update mask.
- `remove_ad_schedule(customer_id, campaign_id, criterion_id)` — removes one daypart criterion.

### Tracking URL / URL options (`url_options.py`, new module)
- `set_campaign_tracking_url` / `set_ad_group_tracking_url` / `set_account_tracking_url` — v25 fields `tracking_url_template`, `final_url_suffix` and `url_custom_parameters` (campaign and ad group; account level has no custom parameters in v25). Empty list clears custom parameters; only provided fields are changed.
- `get_campaign_tracking_url` / `get_ad_group_tracking_url` / `get_account_tracking_url` — read back what is currently configured.

### Call conversion uploads (`conversions.py`)
- `upload_call_conversion(customer_id, conversion_action_id, caller_id, call_start_date_time, conversion_date_time, conversion_value, currency_code, consent)` — `ConversionUploadService.upload_call_conversions` with partial-failure surfacing, E.164 caller validation, `+` normalization and caller-id masking (last 4 digits) in audit payloads and descriptions. The target action must be ENABLED and type `UPLOAD_CALLS`. v25 models consent as a `Consent` message (ad data + ad personalization flags), so `consent=GRANTED|DENIED` is written to both.

### App campaigns (`app_campaigns.py`, new module)
- `create_app_campaign(customer_id, name, campaign_budget_resource_name, app_id, app_store, bidding_strategy_goal_type, target_cpa, target_roas, campaign_sub_type, ...)` — created PAUSED. Uses v25 `MULTI_CHANNEL` channel (the `APP` channel value no longer exists) plus `APP_CAMPAIGN` / `APP_CAMPAIGN_FOR_ENGAGEMENT` sub-type and `app_campaign_setting` with `bidding_strategy_goal_type`. Goal-to-bidding mapping is validated up front:

| `bidding_strategy_goal_type` | campaign bidding | target required |
|---|---|---|
| OPTIMIZE_INSTALLS_TARGET_INSTALL_COST | target_cpa | `target_cpa` |
| OPTIMIZE_IN_APP_CONVERSIONS_TARGET_INSTALL_COST | target_cpa | `target_cpa` |
| OPTIMIZE_IN_APP_CONVERSIONS_TARGET_CONVERSION_COST | target_cpa | `target_cpa` |
| OPTIMIZE_RETURN_ON_ADVERTISING_SPEND | target_roas | `target_roas` |
| OPTIMIZE_PRE_REGISTRATION_CONVERSION_VOLUME | maximize_conversions | — |
| OPTIMIZE_INSTALLS_WITHOUT_TARGET_INSTALL_COST | maximize_conversions | — |
| OPTIMIZE_IN_APP_CONVERSIONS_WITHOUT_TARGET_CPA | maximize_conversions | — |
| OPTIMIZE_TOTAL_VALUE_WITHOUT_TARGET_ROAS | maximize_conversion_value | — |

Ad groups for app campaigns carry no type in v25; `create_ad_group` with `ad_group_type='AUTO'` now resolves the app-campaign channel (`MULTI_CHANNEL`) to "no type" just like Demand Gen.

### Dynamic Search Ads (`dynamic_search_ads.py`, new module)
- `create_dsa_campaign(...)` — created PAUSED. Campaigns use `AdvertisingChannelType.SEARCH` + `dynamic_search_ads_setting` (domain, language, `use_supplied_urls_only`). **v25 has no `SEARCH_DYNAMIC_ADS` channel sub-type** (verified against the v25 proto and the `campaign.advertising_channel_sub_type` field reference), so the campaign no longer attempts to set one — the DSA marker lives on the ad group type.
- `create_dsa_ad_group(...)` — `AdGroupType.SEARCH_DYNAMIC_ADS` (v25 value 13).
- `add_webpage_target(customer_id, campaign_id, conditions, criterion_name, negative, bid_modifier)` — webpage criteria with operand in {URL, CATEGORY, PAGE_TITLE, PAGE_CONTENT, CUSTOM_LABEL} and operator in {EQUALS, CONTAINS} (the v25 operator set).
- `list_webpage_targets(customer_id, campaign_id)` — read current webpage targets.

## Latent contract fix

- `create_shopping_campaign` previously wrote `advertising_channel_sub_type = STANDARD_SHOPPING`. The v25 enum and field reference do not define that value (Standard Shopping is identified by `SHOPPING` channel + `shopping_setting`), so the old code would have been rejected by the live API. It is removed; the MCP parameter `campaign_type="STANDARD_SHOPPING"` remains as a compatibility gate. This was a latent bug that no offline test could catch because the fake enums were more permissive than v25.

## Known boundary (not an MCP gap)

- Standard ad previews (`AdService.generate_preview`) were removed from the Google Ads API; the v25 `AdService` stub only exposes `mutate_ads` (verified against the installed v25 service stubs). The supported preview surfaces remain PMax shareable previews (`generate_pmax_shareable_previews`) and YouTube previews. The MCP documents this boundary instead of faking an endpoint that does not exist.

## Validation

`python scripts/validate_local.py` is green end-to-end against this commit:

```text
isolated smoke  -> SMOKE OK (53 tool modules, zero duplicate-tool warnings, canonical owners verified)
ruff check      -> All checks passed!
pytest -q       -> 277 passed
```

New coverage: 45 tests, including `tests/test_v16_4_functional_gaps_contracts.py`, which build real v25 protobuf messages through the real `GoogleAdsClient` and assert exact update masks, channel/sub-type values, enum values (APP_CAMPAIGN=12, `MinuteOfHour.ZERO=2`, `WebpageConditionOperand.URL=2`), the `Consent` message shape, and the absence of the removed channel sub-types.

As with every 0.16.x release, no live Google Ads account was exercised: all validation is offline/mocked. Live-account E2E remains the required separate step before production replacement.
