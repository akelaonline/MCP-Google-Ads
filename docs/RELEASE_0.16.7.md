# Google Ads MCP 0.16.7

**Release date:** 2026-08-21
**Google Ads API:** v25
**Release type:** minor-gap closure — extension inheritance, campaign dates, change-history filters, tCPA/tROAS CPC bounds

0.16.7 closes the remaining minor gaps identified in the expert review sweep. All four items are verified against real v25 protobufs.

## New tools / changes

### Extension inheritance (`campaigns.py`)
- `set_campaign_excluded_asset_field_types(customer_id, campaign_id, field_types)` — writes v25 `campaign.excluded_parent_asset_field_types` (repeated `AssetFieldType`). Values are deduplicated and validated against the real enum; an empty list re-enables inheritance of all account-level extensions.

### Campaign dates (`campaigns.py`)
- `update_campaign_dates(customer_id, campaign_id, start_date, end_date)` — maps `YYYY-MM-DD` to v25 `start_date_time` / `end_date_time` via the existing `apply_campaign_dates` helper, with a precise update mask.

### Change-history filters (`reporting.py`)
- `get_change_history(days, resource_type, operation, user_email)` — optional filters on `change_resource_type` (enum name), `resource_change_operation` (ADD/SET/REMOVE) and `user_email`. Values are validated to prevent GAQL injection.

### Target CPA / Target ROAS CPC bounds (`bidding.py`)
- `set_target_cpa(..., cpc_bid_ceiling, cpc_bid_floor)` and `set_target_roas(..., cpc_bid_ceiling, cpc_bid_floor)` — write the v25 `cpc_bid_ceiling_micros` / `cpc_bid_floor_micros` fields; floor > ceiling is rejected.

## Validation

`python scripts/validate_local.py` green end-to-end:

```text
isolated smoke  -> SMOKE OK (55 tool modules, zero duplicate-tool warnings)
ruff check      -> All checks passed!
pytest -q       -> 341 passed
```

11 new tests in `tests/test_v16_7_minor_gaps_contracts.py` build real v25 messages and assert exact update masks and enum values (SITELINK=13, CALLOUT=11).

As with every 0.16.x release, no live Google Ads account was exercised: all validation is offline/mocked. Live-account E2E remains the required separate step before production replacement.
