# Usage examples

## Conversational flows

**Weekly cleanup:**
> "Pull the search terms report for the last 7 days on customer 123-456-7890, and show me anything with cost over $20 and zero conversions."
> "Add the worst 5 as negative keywords on that campaign."
> — Claude calls `get_search_terms_report`, then `add_negative_keywords`, returns a preview, you say "confirm", Claude calls `confirm_pending_action`.

**Budget response to a good week:**
> "Campaign 111222333 has ROAS over 5 the last 7 days — bump its budget 20%."
> — Claude calls `get_campaign_performance`, computes the new amount, calls `update_campaign_budget`, shows you the before/after, waits for confirmation.

**New campaign from scratch:**
> "Create a $30/day Search campaign called 'Q3 Promo' with Maximize Conversions bidding, paused for now — I'll review before enabling."
> — Claude calls `create_campaign_budget` → `create_campaign` (both proposed, both need confirmation, or confirm both at once).

**Offline conversion sync (WhatsApp/CRM close):**
> "This lead closed for $450, gclid was `Cj0KCQjw...`, closed today at 3pm Buenos Aires time, upload it against the 'Lead - WhatsApp' conversion action."
> — Claude calls `list_conversion_actions` to find the ID, then `upload_offline_conversion`.

## Useful raw GAQL queries

**Campaigns with no impressions in 30 days (dead weight):**
```sql
SELECT campaign.id, campaign.name, campaign.status
FROM campaign
WHERE campaign.status = 'ENABLED'
  AND metrics.impressions = 0
  AND segments.date DURING LAST_30_DAYS
```

**Keywords with quality score below 5:**
```sql
SELECT
    campaign.name, ad_group.name,
    ad_group_criterion.keyword.text,
    ad_group_criterion.quality_info.quality_score
FROM keyword_view
WHERE ad_group_criterion.quality_info.quality_score <= 5
  AND ad_group_criterion.status = 'ENABLED'
```

**Device performance split:**
```sql
SELECT
    segments.device,
    metrics.clicks, metrics.cost_micros, metrics.conversions
FROM campaign
WHERE segments.date DURING LAST_30_DAYS
```

**Budget-limited campaigns (Google flags these directly):**
```sql
SELECT campaign.name, campaign_budget.amount_micros
FROM campaign
WHERE campaign.status = 'ENABLED'
  AND campaign_budget.recommended_budget_amount_micros IS NOT NULL
```

For the full field/resource reference, ask Claude to call `run_gaql_query` with `SELECT` on any resource — errors from the API come back with the exact valid field names when you get one wrong.
