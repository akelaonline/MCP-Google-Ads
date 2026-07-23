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

## Campaigns **[write]**
| Tool | Description |
|---|---|
| `list_campaigns(customer_id, status_filter?)` | Read-only list. |
| `create_campaign(customer_id, name, campaign_budget_resource_name, channel_type, bidding_strategy, target_cpa?, target_roas?, start_date?, end_date?)` | Always created PAUSED. |
| `update_campaign_status(customer_id, campaign_id, status)` | ENABLED / PAUSED / REMOVED. |
| `update_campaign_name(customer_id, campaign_id, new_name)` | Rename. |
| `remove_campaign(customer_id, campaign_id)` | Irreversible — prefer PAUSED. |

## Budgets **[write]**
| Tool | Description |
|---|---|
| `create_campaign_budget(customer_id, name, daily_amount, delivery_method?, shared?)` | Returns a resource name to pass into `create_campaign`. |
| `update_campaign_budget(customer_id, budget_id, new_daily_amount)` | Change daily spend cap. |

## Bidding **[write]**
| Tool | Description |
|---|---|
| `set_manual_cpc(customer_id, campaign_id, enhanced_cpc?)` | |
| `set_maximize_conversions(customer_id, campaign_id, target_cpa?)` | |
| `set_target_cpa(customer_id, campaign_id, target_cpa)` | |
| `set_target_roas(customer_id, campaign_id, target_roas)` | e.g. `4.0` = 400%. |

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
| `update_ad_status(customer_id, ad_group_id, ad_id, status)` | |
| `remove_ad(customer_id, ad_group_id, ad_id)` | |

## Keywords **[write]**
| Tool | Description |
|---|---|
| `add_keywords(customer_id, ad_group_id, keywords[], cpc_bid?)` | `keywords`: `[{"text": "...", "match_type": "EXACT\|PHRASE\|BROAD"}]`. |
| `update_keyword_status(customer_id, ad_group_id, criterion_id, status)` | |
| `remove_keyword(customer_id, ad_group_id, criterion_id)` | |
| `add_negative_keywords(customer_id, keywords[], campaign_id? \| ad_group_id?)` | Exactly one scope. |

## Audiences **[write]**
| Tool | Description |
|---|---|
| `list_user_lists(customer_id)` | Read-only. |
| `attach_audience_to_ad_group(customer_id, ad_group_id, user_list_resource_name, bid_modifier?)` | |

## Conversions **[write]**
| Tool | Description |
|---|---|
| `list_conversion_actions(customer_id)` | Read-only. |
| `upload_offline_conversion(customer_id, conversion_action_id, gclid, conversion_date_time, conversion_value, currency_code?)` | For CRM/WhatsApp-driven funnels where the sale closes after the click. |

## Safety
| Tool | Description |
|---|---|
| `list_pending_actions()` | Everything awaiting confirmation right now. |
| `confirm_pending_action(action_id)` | Execute it. |
| `cancel_pending_action(action_id)` | Discard it. |
| `get_recent_audit_log(limit?)` | Recently executed mutations (from `audit.db`). |
