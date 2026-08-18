# Tool reference — v0.15 / Google Ads API v25

All normal write tools go through the shared safety layer. v0.14 agency-management additions are indexed in [`AGENCY_TOOLS.md`](AGENCY_TOOLS.md); v0.15 Batch/Smart Bidding operations are documented in [`BATCH_SMART_BIDDING.md`](BATCH_SMART_BIDDING.md).

Default write response:

```json
{
  "status": "pending_confirmation",
  "pending_action_id": "...",
  "description": "..."
}
```

Call `confirm_pending_action(action_id)` to execute or `cancel_pending_action(action_id)` to discard.

`GOOGLE_ADS_MCP_AUTO_APPROVE=true` auto-executes standard-risk writes in the production context; spend, destructive, and sensitive actions remain separately gated. See `docs/SAFETY.md`.

## Accounts & MCC

### `list_accessible_customers()`
Read-only. Lists customer IDs available to the authenticated identity.

### `get_account_hierarchy(login_customer_id)`
Read-only. Returns enabled manager/client accounts below an MCC.

### `get_account_summary(customer_id)`
Read-only. Basic customer name, currency, time zone, status, manager/test-account flags.

### `create_customer_client(login_customer_id, descriptive_name, currency_code="USD", time_zone="America/Argentina/Buenos_Aires")` `[write]`
Creates a new client account under an MCC. Currency and time zone are effectively account-creation decisions; verify before confirmation.

### `list_manager_links(customer_id)`
Read-only. Lists MCC links and their current state.

### `accept_manager_link(customer_id, manager_link_resource_name)` `[write]`
Accepts a pending manager link.

---

## Reporting

### `run_gaql_query(customer_id, query)`
Read-only raw GAQL fallback for cases not covered by a specialized report tool.

### `get_campaign_performance(customer_id, date_range, campaign_id=None)`
Campaign cost/click/conversion metrics.

### `get_ad_group_performance(customer_id, date_range, campaign_id=None)`
Ad-group performance.

### `get_keyword_performance(customer_id, date_range, ad_group_id=None)`
Keyword performance including quality-score fields when available.

### `get_search_terms_report(customer_id, date_range, campaign_id=None)`
Actual user queries that matched ads.

### `get_ad_performance(customer_id, date_range, ad_group_id=None)`
Per-ad delivery and conversion metrics.

### `get_change_history(customer_id, days=7)`
Google Ads change-event history. Google limits the underlying resource to its supported recent window.

### `get_geographic_performance(customer_id, date_range, campaign_id=None)`
Performance by actual user geography.

### `get_device_performance(customer_id, date_range, campaign_id=None)`
Performance by device.

### `get_asset_performance(customer_id, date_range, campaign_id=None)`
Asset-level performance where exposed by Google Ads.

### `get_audience_performance(customer_id, date_range, campaign_id=None)`
Audience criterion performance.

### `get_quality_score_report(customer_id, date_range=None)`
Quality Score distribution/performance.

### `get_disapproved_ads(customer_id, campaign_id=None)`
Policy/disapproval state for ads.

### `get_shopping_performance_report(customer_id, campaign_id=None, date_range=None)`
Shopping performance view by product.

### `list_shopping_products(customer_id, campaign_id=None)`
Read-only Google Ads-side product visibility. Merchant Center feed management is outside this MCP.

---

## Campaigns

### `list_campaigns(customer_id, status_filter=None)`
Read-only campaign inventory.

### `create_campaign(customer_id, name, campaign_budget_resource_name, channel_type="SEARCH", bidding_strategy="MAXIMIZE_CONVERSIONS", target_cpa=None, target_roas=None, start_date=None, end_date=None, contains_eu_political_advertising="DOES_NOT_CONTAIN_EU_POLITICAL_ADVERTISING")` `[write]`
Creates a **PAUSED** campaign.

`start_date` / `end_date` are convenience inputs in `YYYY-MM-DD`; v0.12 maps them to API v25 date-time fields.

New campaigns explicitly declare EU political-advertising status. Override the default if the campaign actually contains EU political advertising.

Supported generic bidding modes in this creator:

- `MANUAL_CPC`
- `MAXIMIZE_CONVERSIONS`
- `TARGET_CPA`
- `TARGET_ROAS`

Use specialized campaign creators when the channel requires additional structure.

### `update_campaign_status(customer_id, campaign_id, status)` `[write]`
`ENABLED`, `PAUSED`, or `REMOVED`.

### `update_campaign_name(customer_id, campaign_id, new_name)` `[write]`
Renames an existing campaign.

### `remove_campaign(customer_id, campaign_id)` `[write]`
Permanent removal path. Prefer pause when reversibility matters.

---

## Shopping & legacy campaign types

### `create_shopping_campaign(customer_id, name, campaign_budget_resource_name, merchant_center_id, sales_country="AR", campaign_type="STANDARD_SHOPPING", target_roas=None, contains_eu_political_advertising=...)` `[write]`
Creates a PAUSED **Standard Shopping** campaign. `sales_country` is retained as a compatibility argument and maps to the current feed-label path.

Requires an already linked Merchant Center setup.

`SMART_SHOPPING` is intentionally rejected. Use Performance Max.

### `create_local_campaign(...)`
Compatibility endpoint only. v0.12 intentionally refuses legacy Local Campaign creation and performs no mutation. Use Performance Max plus location/business assets.

---

## Budgets

### `create_campaign_budget(customer_id, name, daily_amount, delivery_method="STANDARD", shared=False)` `[write]`
Creates a budget. `daily_amount` must be positive. API v25 uses Standard delivery.

### `update_campaign_budget(customer_id, budget_id, new_daily_amount)` `[write]`
Changes daily budget amount; value must be positive.

---

## Bidding

### `set_manual_cpc(customer_id, campaign_id, enhanced_cpc=True)` `[write]`
Switches campaign bidding to Manual CPC.

### `set_maximize_clicks(customer_id, campaign_id, target_cpc=None)` `[write]`
Maximize Clicks, optionally with a CPC ceiling.

### `set_maximize_conversions(customer_id, campaign_id, target_cpa=None)` `[write]`
Maximize Conversions, optionally with target CPA.

### `set_maximize_conversion_value(customer_id, campaign_id, target_roas=None)` `[write]`
Maximize Conversion Value, optionally with target ROAS.

### `set_target_cpa(customer_id, campaign_id, target_cpa)` `[write]`
Standalone Target CPA.

### `set_target_roas(customer_id, campaign_id, target_roas)` `[write]`
Standalone Target ROAS.

### `set_target_impression_share(customer_id, campaign_id, location, target_percent, max_cpc_bid_ceiling=None)` `[write]`
Target Impression Share. `location` is a current `TargetImpressionShareLocation` enum name such as `TOP_OF_PAGE`.

### `create_portfolio_bidding_strategy(customer_id, name, strategy_type, target_cpa=None, target_roas=None)` `[write]`
Creates a shared `TARGET_CPA` or `TARGET_ROAS` bidding strategy.

### `attach_shared_bidding_strategy(customer_id, campaign_id, bidding_strategy_resource_name)` `[write]`
Attaches a campaign to a portfolio strategy.

### `list_portfolio_bidding_strategies(customer_id)`
Read-only portfolio strategy inventory.

---

## Ad groups

### `create_ad_group(customer_id, campaign_id, name, cpc_bid=None, status="PAUSED", ad_group_type="AUTO")` `[write]`
Campaign-aware creation.

`AUTO` resolves the campaign channel:

- Search → `SEARCH_STANDARD`
- Display → `DISPLAY_STANDARD`
- Standard Shopping → `SHOPPING_PRODUCT_ADS`
- Demand Gen → leaves type unset, as required

Ambiguous channels such as Video require an explicit current `AdGroupType` enum name.

Demand Gen rejects ad-group CPC because bidding is campaign-level.

### `update_ad_group_status(customer_id, ad_group_id, status)` `[write]`
Pause/enable/remove.

### `update_ad_group_cpc_bid(customer_id, ad_group_id, new_cpc_bid)` `[write]`
Positive CPC only.

---

## Ads

### `create_responsive_search_ad(customer_id, ad_group_id, headlines, descriptions, final_urls, path1=None, path2=None)` `[write]`
Creates a PAUSED RSA.

- headlines: 3–15, <=30 chars each
- descriptions: 2–4, <=90 chars each
- at least one final URL

### `update_responsive_search_ad(customer_id, ad_group_id, ad_id, headlines=None, descriptions=None, final_urls=None, path1=None, path2=None)` `[write]`
Edits the underlying Ad through API v25 `AdService` / `AdOperation`. Supplied repeated fields replace the full list for that field.

### `get_ad_strength(customer_id, ad_group_id=None, campaign_id=None)`
Read-only RSA Ad Strength/policy view.

### `create_responsive_display_ad(customer_id, ad_group_id, headlines, long_headline, descriptions, business_name, final_urls, marketing_image_urls, logo_image_urls=None, square_marketing_image_urls=None)` `[write]`
Creates image assets plus the PAUSED RDA atomically.

v0.12 requires at least one landscape marketing image and one square marketing image for the current RDA contract.

### `create_video_ad(customer_id, ad_group_id, youtube_video_id, headline, final_urls, description1=None, description2=None, companion_banner_asset_resource_name=None)`
**Compatibility endpoint; no write.** Google Ads API v25 only supports fetching/reporting for legacy `VIDEO` campaigns. This tool returns `status=unsupported`, performs no mutation, and points clients to `create_demand_gen_video_ad`.

### `create_demand_gen_video_ad(customer_id, ad_group_id, youtube_video_ids, headlines, long_headlines, descriptions, business_name, final_urls, logo_image_urls)` `[write]`
Creates YouTube video assets, square logo assets and a PAUSED `DemandGenVideoResponsiveAd` in one atomic `GoogleAdsService.Mutate` request. Supports 1-5 videos/headlines/long-headlines/descriptions/logos. Headlines are <=40 chars, long headlines/descriptions <=90, business name <=25.

### `create_call_ad(customer_id, ad_group_id, country_code, phone_number, business_name, headlines, descriptions, final_urls, call_tracking_enabled=True)` `[write]`
**Compatibility tool.** Google removed legacy Call Ads. v0.12 creates a PAUSED RSA + Call Asset + ad-group asset link atomically.

A final URL is therefore required.

### `create_demand_gen_campaign(customer_id, name, campaign_budget_resource_name, target_cpa=None, contains_eu_political_advertising=...)` `[write]`
Creates a PAUSED Demand Gen campaign shell.

### `create_demand_gen_ad(customer_id, ad_group_id, headlines, descriptions, business_name, final_urls, marketing_image_urls, logo_image_urls, call_to_action_text=None)` `[write]`
Creates image assets plus a PAUSED Demand Gen multi-asset ad atomically.

### `update_ad_status(customer_id, ad_group_id, ad_id, status)` `[write]`
Pause/enable/remove an ad.

### `remove_ad(customer_id, ad_group_id, ad_id)` `[write]`
Permanent removal.

---

## Keywords

### `add_keywords(customer_id, ad_group_id, keywords, cpc_bid=None)` `[write]`
`keywords` is a list of objects:

```json
[
  {"text": "google ads automation", "match_type": "PHRASE"}
]
```

Match types: `EXACT`, `PHRASE`, `BROAD`.

### `update_keyword_status(customer_id, ad_group_id, criterion_id, status)` `[write]`
`REMOVED` uses an actual remove operation.

### `update_keyword_bid(customer_id, ad_group_id, criterion_id, cpc_bid)` `[write]`
Positive CPC only.

### `update_keyword_match_type(customer_id, ad_group_id, criterion_id, match_type)` `[write]`
Keyword match type is immutable. The MCP fetches the current keyword and performs an atomic create-new + remove-old replacement.

### `remove_keyword(customer_id, ad_group_id, criterion_id)` `[write]`
Permanent removal.

### `add_negative_keywords(customer_id, keywords, campaign_id=None, ad_group_id=None)` `[write]`
Exactly one scope. Batch is all-or-nothing.

---

## Keyword Planner

### `generate_keyword_ideas(customer_id, keywords=None, page_url=None, language="en", geo_target_ids=None, limit=100, include_adult_keywords=False)`
Read-only Keyword Planner idea generation with historical metrics.

Provide at least one seed: keyword list or page URL.

### `get_keyword_historical_metrics(customer_id, keywords, language="en", geo_target_ids=None)`
Read-only historical metrics for a known list.

---

## Campaign assets

### `create_sitelink_asset(customer_id, campaign_id, link_text, final_url, description1=None, description2=None)` `[write]`
Creates Asset + CampaignAsset atomically.

### `create_call_asset(customer_id, campaign_id, phone_number, country_code="AR")` `[write]`
Creates and attaches a call asset atomically.

### `create_message_asset(customer_id, campaign_id, phone_number, country_code, business_name, message_text, call_to_action_text="Escribinos")` `[write]`
**Compatibility name.** Creates the current Business Message Asset with WhatsApp provider and attaches it as `BUSINESS_MESSAGE` atomically.

### `create_image_asset(customer_id, campaign_id, image_url, name)` `[write]`
Downloads a public HTTPS image through the SSRF-safe fetcher, creates the asset and attaches it atomically.

### `create_promotion_asset(customer_id, campaign_id, promotion_target, discount_percent=None, money_amount_off=None, currency_code="ARS", promotion_code=None, final_url=None)` `[write]`
Exactly one discount type; creates and attaches atomically.

### `create_callout_asset(customer_id, campaign_id, callout_texts)` `[write]`
Creates multiple callouts and attaches them in one atomic operation set.

### `create_structured_snippet_asset(customer_id, campaign_id, header, values)` `[write]`
Creates and attaches a structured snippet atomically.

### `list_campaign_assets(customer_id, campaign_id)`
Read-only attached-asset inventory, including current Business Message fields.

### `remove_campaign_asset(customer_id, campaign_id, asset_id, field_type)` `[write]`
Detaches the asset from the campaign; does not necessarily delete the underlying Asset resource.

---

## Bulk operations

Bulk status writes are all-or-nothing by default. They do not silently accept partial failures.

### `bulk_update_keyword_status(customer_id, updates, status)` `[write]`
Batch pause/enable/remove keywords.

### `bulk_add_negative_keywords_multi_scope(customer_id, campaign_negatives=None, ad_group_negatives=None)` `[write]`
One atomic multi-scope negative-keyword mutation.

### `bulk_update_ad_status(customer_id, updates, status)` `[write]`
Batch ad status/removal.

### `bulk_update_campaign_status(customer_id, campaign_ids, status)` `[write]`
Batch campaign status/removal.

---

## Audiences & remarketing

### `list_user_lists(customer_id)`
Read-only user-list inventory.

### `create_remarketing_list(customer_id, name, membership_days=30, description=None, url_contains=None, prepopulate=True)` `[write]`
Creates a real rule-based website audience.

`url_contains` is required. For an all-pages audience, pass a hostname shared by all desired URLs, for example `example.com`.

The account's Google Ads tag must already be installed and firing.

### `create_customer_match_list(customer_id, name, description=None)` `[write]`
Creates an empty Customer Match list container.

### `upload_customer_match_members(customer_id, user_list_resource_name, emails=None, phone_numbers=None)` `[write]`
Normalizes/hashes identifiers locally before upload. Raw PII is not included in the safety/audit payload.

### `attach_audience_to_ad_group(customer_id, ad_group_id, user_list_resource_name, bid_modifier=None)` `[write]`
Attaches a user list to an ad group.

### `remove_audience_from_ad_group(customer_id, ad_group_id, criterion_id)` `[write]`
Removes the ad-group audience criterion.

### `search_user_interests(customer_id, name_query)`
Read-only lookup of predefined affinity/in-market interest categories.

### `add_in_market_or_affinity_audience(customer_id, ad_group_id, user_interest_id, bid_modifier=None)` `[write]`
Adds a predefined interest criterion.

### `add_topic_targeting(customer_id, ad_group_id, topic_id, negative=False)` `[write]`
Targets or excludes a topic constant.

---

## Targeting

### `add_location_targeting(customer_id, campaign_id, locations, negative=False, country_code=None, locale="en")` `[write]`
Numeric inputs are treated as GeoTargetConstant criterion IDs. Text names are resolved live through Google's suggestion service. Ambiguous names fail safely and ask for a numeric criterion ID.

### `set_language_targeting(customer_id, campaign_id, language_codes)` `[write]`
True replacement semantics: existing language criteria are removed and the supplied language constants are created in one mutation.

### `add_ad_schedule(customer_id, campaign_id, day_of_week, start_hour, end_hour, bid_modifier=None)` `[write]`
One day/window per call. Bid modifier must be within current valid range.

### `set_device_bid_modifier(customer_id, campaign_id, device, bid_modifier)` `[write]`
Idempotent update-or-create. Devices: `MOBILE`, `DESKTOP`, `TABLET`.

`0` opts out; otherwise supported range is `0.1–10.0`.

### `add_placement_exclusion(customer_id, campaign_id, placement_url, placement_type="WEBSITE")` `[write]`
Placement types: `WEBSITE`, `YOUTUBE_CHANNEL`, `YOUTUBE_VIDEO`, `MOBILE_APPLICATION`.

### `list_campaign_criteria(customer_id, campaign_id)`
Read-only campaign targeting/criterion inventory.

---

## Conversions

### `list_conversion_actions(customer_id)`
Read-only conversion actions including type and primary/secondary state.

### `create_conversion_action(customer_id, name, category, counting_type="ONE_PER_CLICK", value=None, currency_code="USD", conversion_action_type="WEBPAGE")` `[write]`
Creates an ENABLED conversion action.

Use `conversion_action_type="UPLOAD_CLICKS"` when the action will receive GCLID/GBRAID/WBRAID offline click uploads. Conversion action type is immutable after creation.

### `upload_offline_conversion(customer_id, conversion_action_id, gclid, conversion_date_time, conversion_value, currency_code="USD")` `[write]`
Before proposal/execution the MCP verifies that the target conversion action is ENABLED and type `UPLOAD_CLICKS`.

### `upload_enhanced_conversion(customer_id, conversion_action_id, gclid, conversion_date_time, email=None, phone_number=None, conversion_value=None, currency_code="USD")` `[write]`
Offline click upload with locally normalized/hashed first-party identifiers.

Emails are lowercased/trimmed; Gmail/Googlemail local parts are normalized before SHA-256. Phone numbers must normalize to E.164.

### `update_conversion_action_status(customer_id, conversion_action_id, status)` `[write]`
Writable current states: `ENABLED`, `HIDDEN`, `REMOVED`.

### `set_conversion_action_counting(customer_id, conversion_action_id, include_in_conversions_metric)` `[write]`
Compatibility argument retained from earlier releases. v0.12 maps it to the mutable `primary_for_goal` field because the old include-in-conversions resource field is immutable.

### `create_conversion_value_rule(customer_id, action, action_value, geo_target_ids=None, audience_condition=None, device_type=None)` `[write]`
Creates an ENABLED value rule. Actions: `ADD`, `MULTIPLY`, `SET`.

At least one condition is required.

### `list_conversion_value_rules(customer_id)`
Read-only rule inventory.

---

## Performance Max

### `create_performance_max_campaign(customer_id, name, campaign_budget_resource_name, target_cpa=None, target_roas=None, contains_eu_political_advertising=...)` `[write]`
Creates a PAUSED PMax campaign.

At most one target. v0.12 uses current Maximize Conversions / Maximize Conversion Value strategy shapes.

This workflow creates PMax with brand guidelines disabled so business-name/logo assets live in the AssetGroup.

### `create_asset_group(customer_id, campaign_id, name, final_urls, headlines, long_headline, descriptions, business_name, marketing_image_urls, square_marketing_image_urls, logo_image_urls)` `[write]`
Creates a **complete non-retail AssetGroup and required assets atomically**.

Current v0.12 minimums:

- 3–15 headlines, <=30 chars;
- one long headline, <=90 chars;
- 2–5 descriptions, <=90 chars;
- at least one description <=60 chars;
- business name <=25 chars;
- at least one landscape marketing image;
- at least one square marketing image;
- at least one square logo for this brand-guideline mode.

### `update_asset_group_final_urls(customer_id, asset_group_id, final_urls)` `[write]`
Replaces destination URLs.

### `add_asset_group_text_asset(customer_id, asset_group_id, text, field_type)` `[write]`
Creates + links a text asset atomically. Field types include `HEADLINE`, `LONG_HEADLINE`, `DESCRIPTION`, `BUSINESS_NAME`.

### `add_asset_group_image_asset(customer_id, asset_group_id, image_url, field_type)` `[write]`
Creates + links an image asset atomically using the safe image fetcher.

### `add_asset_group_video_asset(customer_id, asset_group_id, youtube_video_id)` `[write]`
Creates + links a YouTube video asset atomically.

### `remove_asset_group_asset(customer_id, asset_group_id, asset_id, field_type)` `[write]`
Unlinks an asset from an AssetGroup.

### `update_asset_group_status(customer_id, asset_group_id, status)` `[write]`
`ENABLED` or `PAUSED`.

### `add_asset_group_listing_filter(customer_id, asset_group_id, campaign_id, product_condition=None, product_brand=None, product_item_id=None, product_type_l1=None)` `[write]`
Retail PMax product scoping. Exactly one dimension per call. v0.12 builds a complete root + included unit + excluded “Other” partition atomically.

### `list_asset_group_listing_filters(customer_id, asset_group_id=None)`
Read-only listing filter tree.

### `list_asset_groups(customer_id, campaign_id=None)`
Read-only AssetGroup inventory.

### `add_asset_group_signal(customer_id, asset_group_id, signal_type, audience_resource_name=None, search_theme_text=None)` `[write]`
`signal_type`: `AUDIENCE` or `SEARCH_THEME`.

### `list_asset_group_signals(customer_id, asset_group_id=None)`
Read-only PMax signals.

---

## Experiments

### `create_experiment(customer_id, base_campaign_id, name, traffic_split_percent=50, experiment_type="SEARCH_CUSTOM", suffix=" [experiment]")` `[write]`
Creates a system-managed experiment plus control/treatment arms.

The control arm points to the base campaign. The treatment arm is left without the base campaign so Google can create the in-design draft campaign. Inspect `in_design_campaigns` before modifying/scheduling the treatment.

### `list_experiments(customer_id)`
Read-only experiment + arm details including in-design campaigns.

### `promote_experiment(customer_id, experiment_resource_name)` `[write]`
Promotes treatment changes into the base campaign.

### `end_experiment(customer_id, experiment_resource_name)` `[write]`
Ends without promoting.

---

## Recommendations

### `get_recommendations(customer_id, type_filter=None, include_dismissed=False)`
Read-only. API v25 uses `recommendation.dismissed`; there is no current recommendation status enum field.

### `apply_recommendation(customer_id, resource_name)` `[write]`
Applies a Google recommendation through the safety layer. No partial-failure mode.

### `dismiss_recommendation(customer_id, resource_name)` `[write]`
Dismisses a recommendation through the current nested v25 dismiss operation type.

---

## Safety & audit tools

### `list_pending_actions()`
Shows unconfirmed actions, age and attempt count.

### `confirm_pending_action(action_id)`
Executes one proposal. On a transient failure the action remains pending and can be retried with the **same ID**.

### `cancel_pending_action(action_id)`
Discards a proposal.

### `get_recent_audit_log(limit=20)`
Recent execution attempts including payload/result metadata.

### `get_audit_action(action_id)`
Every recorded attempt for one stable action ID.

---

## Operational boundaries

- This server wraps Google Ads, not Merchant Center feed/product administration.
- Google Business Profile linking is external to the campaign mutate tools.
- Legacy Local Campaign, Smart Shopping, Call Ad and Message Asset API shapes are not sent to Google v25.
- `create_call_ad` and `create_message_asset` retain their public names only as compatibility wrappers around current supported structures.
- Image URLs must be public HTTPS and pass the SSRF/content/size safety checks.
- Raw HTTP transport is blocked by default; see `docs/SETUP.md`.

---

## Batch Jobs — v0.15

### `list_batch_jobs(customer_id, status_filter=None, limit=100)`
Read-only. Lists recent Batch Jobs. `status_filter` accepts `PENDING`, `RUNNING`, or `DONE`.

### `submit_batch_job(customer_id, operations)` `[write: sensitive]`
Validates and proposes one controlled mixed-resource Batch Job. The whole manifest is previewed/audited before Google creates the job. Supported kinds: `campaign_status`, `ad_group_status`, `ad_status`, `keyword_status`, `campaign_budget_amount`, `keyword_bid`, `add_campaign_negative_keyword`. Maximum 10,000 operations and 20 MiB JSON per MCP submission. Batch Jobs have partial-success semantics; confirm results afterward.

### `get_batch_job_results(customer_id, batch_job_resource_name, page_size=1000, page_token=None, return_mutable_resource=False)`
Read-only. Returns one result page for a Batch Job, including row-level errors/results exposed by Google.

## Smart Bidding controls — v0.15

### `list_seasonality_adjustments(customer_id, limit=100)`
Read-only.

### `create_seasonality_adjustment(customer_id, name, start_date_time, end_date_time, conversion_rate_modifier, scope="CHANNEL", advertising_channel_types=None, campaign_ids=None, devices=None, description=None)` `[write: spend]`
Creates a short expected conversion-rate event. Supports CHANNEL or CAMPAIGN scope, SEARCH/DISPLAY/SHOPPING, optional DESKTOP/MOBILE/TABLET, up to 2,000 campaigns, interval <=14 days, modifier 0.1–10.0.

### `remove_seasonality_adjustment(customer_id, adjustment_id)` `[write: destructive]`
Removes a seasonality adjustment.

### `list_data_exclusions(customer_id, limit=100)`
Read-only.

### `create_data_exclusion(customer_id, name, start_date_time, end_date_time, scope="CHANNEL", advertising_channel_types=None, campaign_ids=None, devices=None, description=None)` `[write: spend]`
Creates a conversion-data exclusion for a measurement incident. Same channel/campaign/device and interval limits as seasonality adjustments.

### `remove_data_exclusion(customer_id, data_exclusion_id)` `[write: destructive]`
Removes a data exclusion.

### `generate_keyword_recommendations(customer_id, seed_keywords, url_seed=None)`
Read-only. Calls `RecommendationService.GenerateRecommendations` for Search `KEYWORD` recommendations using 1–20 keyword seeds and an optional URL seed. Generation does not apply the recommendation.

