# Google Ads MCP 0.16.6

**Release date:** 2026-08-21
**Google Ads API:** v25
**Release type:** expert-scope-2 closure — extended assets, placement targeting, frequency caps, audience exclusions, conversion custom variables

0.16.6 implements the five-item plan from the third expert review. It also fixes another latent production bug that only a live-account call would have surfaced (`create_image_asset` used a non-existent `AssetFieldType.IMAGE`).

## New tools

### Extended assets (`assets_extended.py`, new module)
- `create_lead_form_asset(customer_id, campaign_id, business_name, headline, description, call_to_action_type, privacy_policy_url, fields, desired_intent, post_submit_*, webhook_url)` — Lead Form asset + atomic campaign link. Fields support `single_choice_answers`; delivery via `WebhookDelivery.advertiser_webhook_url`.
- `create_price_asset(customer_id, campaign_id, price_type, language_code, offerings, price_qualifier, currency_code)` — Price asset + atomic campaign link. Offerings take numeric `price` amounts converted to the v25 `Money` shape (amount_micros + currency_code); units are PriceExtensionPriceUnit values.
- `create_location_asset(customer_id, place_id)` — account-level Location asset. **v25 has no LOCATION AssetFieldType**, so there is no campaign link; Google serves location assets automatically on accounts with a linked Business Profile.
- `create_mobile_app_asset(customer_id, campaign_id, app_id, app_store, link_text)` — mobile-app extension + atomic campaign link (AssetFieldType.MOBILE_APP).
- `create_app_deep_link_asset(customer_id, app_deep_link_uri)` — account-level asset; **no APP_DEEP_LINK AssetFieldType** exists in v25.

### Positive placement targeting (`targeting.py`)
- `add_placement_target(customer_id, campaign_id, placement_url, placement_type, bid_modifier)` — WEBSITE / YOUTUBE_CHANNEL / YOUTUBE_VIDEO / MOBILE_APPLICATION with optional bid modifier. Negative form remains `add_placement_exclusion`.

### Frequency caps (`campaigns.py`)
- `set_campaign_frequency_caps(customer_id, campaign_id, caps)` — list of `{level, event_type, time_unit, time_length, cap}` (AD_GROUP_AD/AD_GROUP/CAMPAIGN; IMPRESSION/VIDEO_VIEW; DAY/WEEK/MONTH). Empty list clears.

### Audience exclusions (`targeting.py`)
- `exclude_audience_from_ad_group(customer_id, ad_group_id, audience_resource_name)` — modern Audience (`customers/{id}/audiences/{id}`) via `AdGroupCriterion.audience`, or legacy UserList/CustomAudience/CustomInterest.
- `exclude_audience_from_campaign(customer_id, campaign_id, audience_resource_name)` — legacy kinds only; v25 `CampaignCriterion` has no modern `audience` field, so modern Audience resources are rejected with guidance to exclude at ad-group level.

### Conversion custom variables (`conversions.py`)
- `upload_offline_conversion`, `upload_enhanced_conversion`, `upload_call_conversion` accept `custom_variables=[{"name": ..., "value": ...}]` → `ClickConversion`/`CallConversion.custom_variables`.

## Latent contract fix

- `create_image_asset` linked campaigns with AssetFieldType `"IMAGE"` — that value does not exist in v25 (verified against the real enum). The correct value is `MARKETING_IMAGE`. `tests/conftest.py`'s fake `AssetFieldTypeEnum` was more permissive than v25 and masked this; it now mirrors real v25 values (SITELINK=13, CALL=16, PRICE=24, LEAD_FORM=9, MOBILE_APP=14, ...).

## Validation

`python scripts/validate_local.py` green end-to-end:

```text
isolated smoke  -> SMOKE OK (55 tool modules, zero duplicate-tool warnings)
ruff check      -> All checks passed!
pytest -q       -> 330 passed
```

25 new tests, including `tests/test_v16_6_expert_scope_2_contracts.py` with real v25 protobuf builds (frequency-cap entries, placement criteria, audience exclusions, Money price offerings, webhook delivery, custom variables on uploads, AssetFieldType values).

As with every 0.16.x release, no live Google Ads account was exercised: all validation is offline/mocked. Live-account E2E remains the required separate step before production replacement.
