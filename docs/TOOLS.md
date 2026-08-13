# Tool reference

All write tools (marked **[write]**) return either:
- `{"status": "pending_confirmation", "pending_action_id": "...", ...}` — default behavior, or
- `{"status": "executed", "auto_approved": true, "result": ...}` — only if `GOOGLE_ADS_MCP_AUTO_APPROVE=true`.

Call `confirm_pending_action(action_id)` to execute a pending change, or `cancel_pending_action(action_id)` to discard it.

## Accounts
| Tool | Description |
|---|---|
| `list_accessible_customers()` | All customer IDs reachable with the current credentials. |
| `get_account_hierarchy(login_customer_id)` | Full MCC tree: managers + client accounts. |
| `get_account_summary(customer_id)` | Name, currency, time zone, status. |

## Account onboarding **[write]**
| Tool | Description |
|---|---|
| `create_customer_client(login_customer_id, descriptive_name, currency_code?, time_zone?)` | Create a new client account under an MCC, auto-linked. `currency_code`/`time_zone` are immutable after creation. |
| `list_manager_links(customer_id)` | Read-only: which MCCs have access to a client account, and link status (ACTIVE/PENDING/REFUSED). |
| `accept_manager_link(customer_id, manager_link_resource_name)` | Accept a pending MCC access invitation — the counterpart flow to `create_customer_client` for a client account that already existed and invited this MCC in. |

## Reporting
| Tool | Description |
|---|---|
| `run_gaql_query(customer_id, query)` | Any raw GAQL query. |
| `get_campaign_performance(customer_id, date_range, campaign_id?)` | Cost, clicks, conversions per campaign. |
| `get_ad_group_performance(customer_id, date_range, campaign_id?)` | Same, per ad group. |
| `get_keyword_performance(customer_id, date_range, ad_group_id?)` | Includes quality score. |
| `get_search_terms_report(customer_id, date_range, campaign_id?)` | Actual queries that triggered ads. |
| `get_ad_performance(customer_id, date_range, ad_group_id?)` | Per-ad metrics. |
| `get_change_history(customer_id, days)` | Native `change_event` log, up to 30 days. |
| `get_geographic_performance(customer_id, date_range, campaign_id?)` | Performance by the user's actual location (not the targeted location) — spot spend leaking outside your intended area. |
| `get_device_performance(customer_id, date_range, campaign_id?)` | Performance by MOBILE/DESKTOP/TABLET — the data behind a `set_device_bid_modifier` decision. |
| `get_asset_performance(customer_id, date_range, campaign_id?)` | Which specific asset (sitelink/call/message/image/promotion/RSA piece) is pulling weight. |
| `get_audience_performance(customer_id, date_range, campaign_id?)` | Which attached audience is actually converting vs. just attached for observation. |
| `get_quality_score_report(customer_id, date_range?)` | Aggregate keyword performance by Quality Score bucket (1-10). |
| `get_disapproved_ads(customer_id, campaign_id?)` | Ads that are disapproved, limited by policy, or under review, with the specific policy topic — the fast path to "why isn't this ad serving" without opening the UI. Especially relevant for regulated categories (health, medical devices, finance). |
| `get_shopping_performance_report(customer_id, campaign_id?, date_range?)` | Per-product (SKU-level) performance via `shopping_performance_view` — see which products drive results vs. burn spend with none. |
| `list_shopping_products(customer_id, campaign_id?)` | Distinct products currently eligible to serve in Shopping/PMax, read from the Google Ads side. Feed/catalog management stays in Merchant Center, not this MCP. |

## Campaigns **[write]**
| Tool | Description |
|---|---|
| `list_campaigns(customer_id, status_filter?)` | Read-only list. |
| `create_campaign(customer_id, name, campaign_budget_resource_name, channel_type, bidding_strategy, target_cpa?, target_roas?, start_date?, end_date?)` | Always created PAUSED. |
| `update_campaign_status(customer_id, campaign_id, status)` | ENABLED / PAUSED / REMOVED. |
| `update_campaign_name(customer_id, campaign_id, new_name)` | Rename. |
| `remove_campaign(customer_id, campaign_id)` | Irreversible — prefer PAUSED. |

## Specialized campaign types **[write]**
| Tool | Description |
|---|---|
| `create_shopping_campaign(customer_id, name, campaign_budget_resource_name, merchant_center_id, sales_country?, campaign_type?, target_roas?)` | Created PAUSED. **Requires a product feed already live in Google Merchant Center, linked to this account** — this tool creates the campaign shell only; feed/product management happens in Merchant Center, a separate API this MCP does not wrap. Will fail if `merchant_center_id` isn't already linked. |
| `create_local_campaign(customer_id, name, campaign_budget_resource_name, business_name, headlines[], descriptions[], final_url, target_cpa?)` | Created PAUSED, with its core text asset attached. Requires a linked Google Business Profile for location targeting to resolve — set up separately in the Ads UI. |

## Targeting **[write]**
| Tool | Description |
|---|---|
| `add_location_targeting(customer_id, campaign_id, locations[], negative?)` | `locations` accepts common names ("argentina", "buenos aires" — see `COMMON_GEO_TARGET_IDS`) or raw numeric geo target constant IDs. `negative=True` excludes instead of targets. |
| `set_language_targeting(customer_id, campaign_id, language_codes[])` | Language constant criterion IDs, e.g. "1003" Spanish, "1000" English. |
| `add_ad_schedule(customer_id, campaign_id, day_of_week, start_hour, end_hour, bid_modifier?)` | Dayparting. One call per day/window; call repeatedly to build a full schedule. |
| `set_device_bid_modifier(customer_id, campaign_id, device, bid_modifier)` | `device`: MOBILE / DESKTOP / TABLET. |
| `add_placement_exclusion(customer_id, campaign_id, placement_url, placement_type?)` | Exclude a specific Display/YouTube placement (website domain, YouTube channel/video, or mobile app) from a campaign — for when the placement report shows spend burning with no results. `placement_type`: WEBSITE / YOUTUBE_CHANNEL / YOUTUBE_VIDEO / MOBILE_APPLICATION. |
| `list_campaign_criteria(customer_id, campaign_id)` | Read-only: every targeting criterion on a campaign (locations, languages, schedules, device modifiers, negatives) in one call. |

## Budgets **[write]**
| Tool | Description |
|---|---|
| `create_campaign_budget(customer_id, name, daily_amount, delivery_method?, shared?)` | Returns a resource name to pass into `create_campaign`. |
| `update_campaign_budget(customer_id, budget_id, new_daily_amount)` | Change daily spend cap. |

## Bidding **[write]**
| Tool | Description |
|---|---|
| `set_manual_cpc(customer_id, campaign_id, enhanced_cpc?)` | |
| `set_maximize_clicks(customer_id, campaign_id, target_cpc?)` | Modeled under `target_spend` in the API (no `maximize_clicks` field exists — legacy naming). |
| `set_maximize_conversions(customer_id, campaign_id, target_cpa?)` | |
| `set_maximize_conversion_value(customer_id, campaign_id, target_roas?)` | Optimizes total conversion VALUE, not count — prefer for e-commerce/Shopping where order size varies. |
| `set_target_cpa(customer_id, campaign_id, target_cpa)` | |
| `set_target_roas(customer_id, campaign_id, target_roas)` | e.g. `4.0` = 400%. |
| `set_target_impression_share(customer_id, campaign_id, location, target_percent, max_cpc_bid_ceiling?)` | `location`: ANYWHERE_ON_PAGE / TOP_OF_PAGE / ABSOLUTE_TOP_OF_PAGE. For brand-defense/visibility campaigns rather than click/conversion optimization. |
| `create_portfolio_bidding_strategy(customer_id, name, strategy_type, target_cpa?, target_roas?)` | Create a shared (portfolio) TARGET_CPA or TARGET_ROAS strategy multiple campaigns can attach to and learn from jointly. |
| `attach_shared_bidding_strategy(customer_id, campaign_id, bidding_strategy_resource_name)` | Attach a campaign to a portfolio strategy, overriding its standalone bidding. |
| `list_portfolio_bidding_strategies(customer_id)` | Read-only: portfolio strategies and how many campaigns are attached to each. |

## Ad groups **[write]**
| Tool | Description |
|---|---|
| `create_ad_group(customer_id, campaign_id, name, cpc_bid?, status?)` | |
| `update_ad_group_status(customer_id, ad_group_id, status)` | |
| `update_ad_group_cpc_bid(customer_id, ad_group_id, new_cpc_bid)` | |

## Ads **[write]**
| Tool | Description |
|---|---|
| `create_responsive_search_ad(customer_id, ad_group_id, headlines[], descriptions[], final_urls[], path1?, path2?)` | 3-15 headlines (≤30 chars), 2-4 descriptions (≤90 chars). Created PAUSED. |
| `update_responsive_search_ad(customer_id, ad_group_id, ad_id, headlines?, descriptions?, final_urls?, path1?, path2?)` | Edit an EXISTING RSA in place — no need to remove and recreate it (which loses accumulated Ad Strength history/serving data). Only pass the fields you want changed; each provided field REPLACES the full list, it does not append. |
| `create_responsive_display_ad(customer_id, ad_group_id, headlines[], long_headline, descriptions[], business_name, final_urls[], marketing_image_urls?, logo_image_urls?)` | 1-5 headlines (≤30 chars), 1 long headline (≤90 chars), 1-5 descriptions (≤90 chars). Downloads and uploads any image URLs given. Created PAUSED. |
| `create_video_ad(customer_id, ad_group_id, youtube_video_id, headline, final_urls[], description1?, description2?, companion_banner_asset_resource_name?)` | In-stream YouTube ad, referencing an already-uploaded public/unlisted video by ID. `headline` ≤15 chars. Created PAUSED. |
| `get_ad_strength(customer_id, ad_group_id?, campaign_id?)` | Read-only. Lists RSAs with their Ad Strength rating (PENDING/NO_ADS/POOR/AVERAGE/GOOD/EXCELLENT) and policy approval status — the fastest way to find ads that need better headline/description variety. |
| `create_call_ad(customer_id, ad_group_id, country_code, phone_number, business_name, headlines[], descriptions[], final_urls?, call_tracking_enabled?)` | Phone-only ad, no landing page — just a "Call" button, shown only on call-capable devices. 2-15 headlines (≤30 chars), 2-4 descriptions (≤90 chars). Created PAUSED. |
| `create_demand_gen_campaign(customer_id, name, campaign_budget_resource_name, target_cpa?)` | Demand Gen (formerly Discovery) campaign shell — runs on Discover feed, Gmail, and YouTube in-feed/Shorts. Creative-led, not fully automated like PMax. Created PAUSED. |
| `create_demand_gen_ad(customer_id, ad_group_id, headlines[], descriptions[], business_name, final_urls[], marketing_image_urls?, logo_image_urls?, call_to_action_text?)` | Multi-asset ad for a Demand Gen campaign. 1-5 headlines (≤40 chars), 1-5 descriptions (≤90 chars). Downloads/uploads any image URLs given. Created PAUSED. |
| `update_ad_status(customer_id, ad_group_id, ad_id, status)` | |
| `remove_ad(customer_id, ad_group_id, ad_id)` | |

## Keywords **[write]**
| Tool | Description |
|---|---|
| `add_keywords(customer_id, ad_group_id, keywords[], cpc_bid?)` | `keywords`: `[{"text": "...", "match_type": "EXACT\|PHRASE\|BROAD"}]`. |
| `update_keyword_status(customer_id, ad_group_id, criterion_id, status)` | |
| `update_keyword_bid(customer_id, ad_group_id, criterion_id, cpc_bid)` | Change an existing keyword's max CPC in place. |
| `update_keyword_match_type(customer_id, ad_group_id, criterion_id, match_type)` | Change match type (EXACT/PHRASE/BROAD). `match_type` is immutable on an existing criterion in the API, so this recreates the keyword with the new match type (preserving text and cpc_bid) and removes the old one as a single atomic batch — no gap where neither variant is active. |
| `remove_keyword(customer_id, ad_group_id, criterion_id)` | |
| `add_negative_keywords(customer_id, keywords[], campaign_id? \| ad_group_id?)` | Exactly one scope. |

## Keyword research
| Tool | Description |
|---|---|
| `generate_keyword_ideas(customer_id, keywords?, page_url?, language?, geo_target_ids?, limit?, include_adult_keywords?)` | Call `KeywordPlanIdeaService.GenerateKeywordIdeas`. Returns search volume, competition, competition index, and low/high CPC bid ranges for each idea. Provide at least one of `keywords` or `page_url`. `language` defaults to `"en"`; geo target IDs like `["2840"]` (US) restrict the forecast. |
| `get_keyword_historical_metrics(customer_id, keywords[], language?, geo_target_ids?)` | Look up historical metrics for a known keyword list without expanding into new suggestions. |

## Assets **[write]**
| Tool | Description |
|---|---|
| `create_sitelink_asset(customer_id, campaign_id, link_text, final_url, description1?, description2?)` | Creates the asset and attaches it to the campaign in one call. `link_text` ≤25 chars, descriptions ≤35 chars each. |
| `create_call_asset(customer_id, campaign_id, phone_number, country_code?)` | Click-to-call extension. `country_code` defaults to "AR". |
| `create_message_asset(customer_id, campaign_id, phone_number, country_code, business_name, message_text, call_to_action_text?)` | Click-to-message (WhatsApp/SMS) extension — opens a chat directly from the ad. `message_text` ≤35 chars. |
| `create_image_asset(customer_id, campaign_id, image_url, name)` | Downloads an image from a public HTTPS URL and uploads it as a campaign asset (image extension / PMax marketing image). Fetched at confirm time. |
| `create_promotion_asset(customer_id, campaign_id, promotion_target, discount_percent? \| money_amount_off?, currency_code?, promotion_code?, final_url?)` | Promotion extension (e.g. "20% OFF"). Exactly one of `discount_percent` / `money_amount_off`. |
| `create_callout_asset(customer_id, campaign_id, callout_texts[])` | One or more short trust-signal callouts (≤25 chars each, e.g. "Envío gratis"), attached in a single call. |
| `create_structured_snippet_asset(customer_id, campaign_id, header, values[])` | A labeled list under a fixed Google header (e.g. "Service catalog"). 3-10 values, ≤25 chars each. |
| `list_campaign_assets(customer_id, campaign_id)` | Read-only: every asset attached to a campaign, with status. |
| `remove_campaign_asset(customer_id, campaign_id, asset_id, field_type)` | Detach an asset (SITELINK/CALL/MESSAGE/IMAGE/PROMOTION/CALLOUT/STRUCTURED_SNIPPET/etc.) from a campaign. |

## Bulk operations **[write]**
| Tool | Description |
|---|---|
| `bulk_update_keyword_status(customer_id, updates[], status)` | Pause/enable/remove many existing keywords — possibly across different ad groups — in a single API call. `updates`: `[{"ad_group_id", "criterion_id"}]`. |
| `bulk_add_negative_keywords_multi_scope(customer_id, campaign_negatives?, ad_group_negatives?)` | Roll the same (or different) negative-keyword lists out across many campaigns/ad groups at once, e.g. one negative list applied to every active campaign in one shot. |
| `bulk_update_ad_status(customer_id, updates[], status)` | Pause/enable/remove many ads in a single call. `updates`: `[{"ad_group_id", "ad_id"}]`. |
| `bulk_update_campaign_status(customer_id, campaign_ids[], status)` | Pause/enable/remove many campaigns in a single call. |

## Audiences **[write]**
| Tool | Description |
|---|---|
| `list_user_lists(customer_id)` | Read-only. |
| `create_remarketing_list(customer_id, name, membership_days?, description?)` | Website-visitor list. Requires the account's Google Ads tag to already be installed and firing — does not backfill past traffic. |
| `create_customer_match_list(customer_id, name, description?)` | Empty contact-based list container; follow with `upload_customer_match_members`. Subject to Google's Customer Match policy approval, checked at upload time. |
| `upload_customer_match_members(customer_id, user_list_resource_name, emails?, phone_numbers?)` | Uploads contacts, hashed (SHA-256) locally before sending — raw PII is never transmitted by this tool. |
| `attach_audience_to_ad_group(customer_id, ad_group_id, user_list_resource_name, bid_modifier?)` | |
| `remove_audience_from_ad_group(customer_id, ad_group_id, criterion_id)` | Detach an audience from an ad group. |
| `search_user_interests(customer_id, name_query)` | Read-only: look up Affinity/In-Market/Custom-Intent segment IDs by name (Google's predefined categories, distinct from your own lists). |
| `add_in_market_or_affinity_audience(customer_id, ad_group_id, user_interest_id, bid_modifier?)` | Attach a predefined interest/purchase-intent segment (from `search_user_interests`) to an ad group. |
| `add_topic_targeting(customer_id, ad_group_id, topic_id, negative?)` | Target or exclude a Display/YouTube topic on an ad group — e.g. brand-safety exclusions like "Sensitive Subjects". `topic_id` via GAQL on `topic_constant`. |

## Conversions **[write]**
| Tool | Description |
|---|---|
| `list_conversion_actions(customer_id)` | Read-only. Includes `primary_for_goal` and `include_in_conversions_metric`. |
| `upload_offline_conversion(customer_id, conversion_action_id, gclid, conversion_date_time, conversion_value, currency_code?)` | For CRM/WhatsApp-driven funnels where the sale closes after the click. |
| `update_conversion_action_status(customer_id, conversion_action_id, status)` | ENABLED / REMOVED / HIDDEN. Prefer over deleting when you just want to stop counting a soft signal. |
| `set_conversion_action_counting(customer_id, conversion_action_id, include_in_conversions_metric)` | Include/exclude an action from the primary Conversions column and automated bidding, without touching whether it still records data. Use this to stop Smart Bidding from optimizing toward a vanity metric (e.g. a quiz/page_view) while keeping the historical data. |
| `create_conversion_action(customer_id, name, category, counting_type?, value?, currency_code?)` | Create a new WEBSITE conversion action (e.g. "WhatsApp Click", "Compra"). Created ENABLED and included in bidding by default. `category`: PURCHASE/LEAD/SIGNUP/PAGE_VIEW/DOWNLOAD/CONTACT/SUBMIT_LEAD_FORM/BOOK_APPOINTMENT/REQUEST_QUOTE/GET_DIRECTIONS/OUTBOUND_CLICK/PHONE_CALL_LEAD/OTHER. `counting_type`: ONE_PER_CLICK (leads) or MANY_PER_CLICK (repeat purchases). |
| `upload_enhanced_conversion(customer_id, conversion_action_id, gclid, conversion_date_time, email?, phone_number?, conversion_value?, currency_code?)` | Like `upload_offline_conversion` but with Enhanced Conversions user identifiers (hashed email/phone), improving match rate as cookie/click-ID-only tracking gets less reliable. Hashes locally (SHA-256) — never send pre-hashed values. Requires at least one of `email` / `phone_number`. |
| `create_conversion_value_rule(customer_id, action, action_value, geo_target_ids?, audience_condition?, device_type?)` | Adjust reported conversion value by geography/audience/device (`action`: MULTIPLY or SET) — so value-based bidding optimizes toward segments that actually matter, without touching the underlying conversion action. |
| `list_conversion_value_rules(customer_id)` | Read-only. |

## Performance Max **[write]**
| Tool | Description |
|---|---|
| `create_performance_max_campaign(customer_id, name, campaign_budget_resource_name, target_cpa?, target_roas?)` | Created PAUSED. At most one of `target_cpa` / `target_roas`; if neither, uses Maximize Conversions with no target. Needs at least one asset group before it can serve. |
| `create_asset_group(customer_id, campaign_id, name, final_urls[], headlines[], long_headline, descriptions[], business_name)` | Text-only asset group (3-5 headlines ≤30 chars, 1 long headline ≤90 chars, 1-5 descriptions ≤90 chars). Created PAUSED. |
| `update_asset_group_final_urls(customer_id, asset_group_id, final_urls[])` | Replace an existing asset group's landing page URL(s) — e.g. after a site migration. |
| `add_asset_group_text_asset(customer_id, asset_group_id, text, field_type)` | Add a single HEADLINE / LONG_HEADLINE / DESCRIPTION / BUSINESS_NAME to an existing asset group. |
| `add_asset_group_image_asset(customer_id, asset_group_id, image_url, field_type)` | Download an image from a public HTTPS URL and attach it to an asset group. `field_type`: MARKETING_IMAGE / SQUARE_MARKETING_IMAGE / PORTRAIT_MARKETING_IMAGE / LOGO / LANDSCAPE_LOGO. Closes the gap that used to require attaching PMax images via the UI. |
| `add_asset_group_video_asset(customer_id, asset_group_id, youtube_video_id)` | Link an already-public/unlisted YouTube video into an asset group as a VIDEO asset. |
| `remove_asset_group_asset(customer_id, asset_group_id, asset_id, field_type)` | Unlink a text/image/video asset from an asset group (does not delete the underlying Asset resource). |
| `update_asset_group_status(customer_id, asset_group_id, status)` | Pause/enable a single asset group without touching the campaign or other asset groups. |
| `add_asset_group_listing_filter(customer_id, asset_group_id, campaign_id, product_condition? \| product_brand? \| product_item_id? \| product_type_l1?)` | Scope which products from the linked Shopping feed an asset group can advertise — e.g. limit one asset group to a single brand or product line. Exactly one dimension per call; builds a root subdivision + one filtered unit under it. |
| `list_asset_group_listing_filters(customer_id, asset_group_id?)` | Read-only: the listing group filter tree(s) for PMax asset groups. |
| `add_asset_group_signal(customer_id, asset_group_id, signal_type, audience_resource_name?, search_theme_text?)` | Steer PMax's automated targeting with an AUDIENCE (user list / custom audience / affinity-in-market segment) or SEARCH_THEME (short intent phrase) signal. A hint, not a hard restriction — PMax can still serve beyond it. |
| `list_asset_group_signals(customer_id, asset_group_id?)` | Read-only. |
| `list_asset_groups(customer_id, campaign_id?)` | Read-only. |

## Experiments (A/B trials) **[write]**
| Tool | Description |
|---|---|
| `create_experiment(customer_id, base_campaign_id, name, traffic_split_percent?, experiment_type?)` | Branch a trial arm off an existing campaign with a traffic split (default 50/50). Edit the trial arm afterward with the normal campaign/bidding/ads tools, targeting its own campaign_id. Created in SETUP status. |
| `list_experiments(customer_id)` | Read-only: status and traffic split of each experiment. |
| `promote_experiment(customer_id, experiment_resource_name)` | Apply the trial arm's changes to the base campaign permanently and end the experiment. **Irreversible.** |
| `end_experiment(customer_id, experiment_resource_name)` | Discard the trial arm without promoting; base campaign is unaffected. |

## Recommendations **[write]**
| Tool | Description |
|---|---|
| `get_recommendations(customer_id, type_filter?)` | List active Google Ads recommendations for the account. Optional `type_filter` e.g. `KEYWORD`, `SITELINK_ASSET`, `TARGET_ROAS_OPT_IN`. |
| `apply_recommendation(customer_id, resource_name)` | Apply a recommendation by its `resource_name`. Proposed, must be confirmed. |
| `dismiss_recommendation(customer_id, resource_name)` | Dismiss a recommendation by its `resource_name`. Proposed, must be confirmed. |

## Not supported — by design
Google Ads' web-UI "Automated Rules" (e.g. "pause this keyword if CPA > X")
have **no corresponding resource in the Google Ads API**. There is no
`AutomatedRuleService`. Anything resembling scheduled/conditional automation
has to be built as your own polling logic that calls the existing report +
write tools here (e.g. a scheduled task that runs `get_keyword_performance`
and calls `bulk_update_keyword_status` when a threshold is crossed) — this
MCP intentionally does not pretend to wrap a native "rules" API that doesn't
exist.

## Safety
| Tool | Description |
|---|---|
| `list_pending_actions()` | Everything awaiting confirmation right now. |
| `confirm_pending_action(action_id)` | Execute it. |
| `cancel_pending_action(action_id)` | Discard it. |
| `get_recent_audit_log(limit?)` | Recently executed mutations (from `audit.db`). |
