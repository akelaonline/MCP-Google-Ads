# Batch Jobs & Smart Bidding controls

Operational reference for the v0.15 Google Ads MCP additions.

## Batch Jobs

### Why the MCP uses one reviewed submission

The Google Ads BatchJob API separates create, add-operations, run, and result retrieval. Uploaded operations are not exposed later as a convenient readable manifest. For production AI use, the MCP therefore accepts the complete manifest in `submit_batch_job`, validates it locally, and places it in the pending-action/audit payload before it calls Google.

This avoids a dangerous workflow where an operator approves an empty job and loses visibility into mutations added afterward.

### Supported operation kinds

```json
{"kind":"campaign_status","campaign_id":"111","status":"PAUSED"}
{"kind":"ad_group_status","ad_group_id":"222","status":"PAUSED"}
{"kind":"ad_status","ad_group_id":"222","ad_id":"333","status":"PAUSED"}
{"kind":"keyword_status","ad_group_id":"222","criterion_id":"444","status":"REMOVED"}
{"kind":"campaign_budget_amount","campaign_budget_id":"555","amount":75.0}
{"kind":"keyword_bid","ad_group_id":"222","criterion_id":"444","cpc_bid":1.25}
{"kind":"add_campaign_negative_keyword","campaign_id":"111","text":"free","match_type":"PHRASE"}
```

`REMOVED` keyword status creates a real remove operation; it is not represented as a fake status update.

### Example flow

1. Call `submit_batch_job(customer_id, operations)`.
2. Review the returned pending action. Nothing has changed yet under recommended production settings.
3. Confirm the pending action.
4. The MCP creates the BatchJob, uploads the validated operations, and starts it.
5. Use `list_batch_jobs` until Google reports `DONE`.
6. Read row-level outcomes with `get_batch_job_results`.

### Important: partial success

Batch Jobs do not have the same all-or-nothing behavior as the MCP's normal atomic mutate flows. Some operations can succeed while others fail, and successful rows are not rolled back. Always inspect the result set before treating a job as completely successful.

### Limits in this MCP

- at most 10,000 operations in one `submit_batch_job` call;
- at most 20 MiB serialized JSON manifest;
- no arbitrary raw protobuf operations;
- customer ID must pass the configured allowlist;
- submission is classified `sensitive`.

The 10,000-operation MCP limit is intentionally conservative and corresponds to a single add-operations request. Larger workflows should be split into explicit, reviewable jobs rather than silently chunked behind one approval.

## Seasonality adjustments

Use a seasonality adjustment for a short, expected conversion-rate change such as a major sale where Smart Bidding should anticipate behavior that historical data does not represent well.

Example:

```text
create_seasonality_adjustment(
  customer_id="1234567890",
  name="Cyber Monday",
  start_date_time="2026-11-30 00:00:00",
  end_date_time="2026-12-01 23:59:59",
  conversion_rate_modifier=1.8,
  scope="CHANNEL",
  advertising_channel_types=["SEARCH", "SHOPPING"],
  devices=["DESKTOP", "MOBILE"]
)
```

Creation is classified `spend` because it can alter bidding behavior. Removal is `destructive`.

## Data exclusions

Use a data exclusion when conversion tracking was wrong or unavailable and Smart Bidding should ignore the affected conversion data. Typical examples include broken checkout tracking, tag outages, duplicate conversion firing, or measurement incidents.

Example:

```text
create_data_exclusion(
  customer_id="1234567890",
  name="Checkout tracking outage",
  start_date_time="2026-08-17 10:00:00",
  end_date_time="2026-08-17 13:00:00",
  scope="CAMPAIGN",
  campaign_ids=["111", "222"]
)
```

Creation is classified `spend` because it changes Smart Bidding's learning inputs. Removal is `destructive`.

## Scope rules

Both Smart Bidding event types support:

- `scope="CHANNEL"` with SEARCH, DISPLAY, and/or SHOPPING;
- `scope="CAMPAIGN"` with 1–2,000 campaign IDs;
- optional DESKTOP, MOBILE, and TABLET filters;
- intervals no longer than 14 days.

Do not send both campaign IDs and channel types for the same event. The MCP rejects ambiguous scopes before Google is called.

Google interprets event date-times in the Google Ads account time zone. The MCP preserves the strings exactly as supplied.

## Generated keyword recommendations

`generate_keyword_recommendations` asks Google to generate fresh Search keyword recommendations from 1–20 seed keywords and an optional URL seed. It is read-only and may legitimately return zero recommendations.

Example:

```text
generate_keyword_recommendations(
  customer_id="1234567890",
  seed_keywords=["google ads agency", "ppc management"],
  url_seed="https://example.com/google-ads"
)
```

Generating a recommendation does not apply it. Any later `apply_recommendation` call still goes through the spend-risk confirmation policy.
