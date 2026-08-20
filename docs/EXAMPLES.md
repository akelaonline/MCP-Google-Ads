# Examples — Google Ads MCP v0.16

These examples show the intended operator flow. Normal writes are proposals by default; confirm them explicitly before live execution.

## 1. Search terms → negative keywords

```text
User:
Pull the search terms for customer 123-456-7890 for the last 7 days.
Show terms with meaningful spend and zero conversions, then propose sensible
campaign negatives. Do not change the account yet.

AI:
-> get_search_terms_report(...)
-> add_negative_keywords(...)
<- pending_confirmation + pending_action_id

User:
Confirm that action.

AI:
-> confirm_pending_action(action_id)
<- executed + audit record
```

## 2. Create a Search campaign safely

```text
User:
Create a $50/day Search campaign called "Brand AR" with Maximize Conversions.
Leave it paused.

AI:
-> create_campaign_budget(... daily_amount=50)
<- pending action

User:
Confirm the budget.

AI:
-> confirm_pending_action(...)
<- budget created

AI:
-> create_campaign(..., campaign_budget_resource_name=..., status=PAUSED)
<- pending action
```

The MCP does not silently enable the campaign.

## 3. Change a live budget

```text
User:
Raise campaign 123's daily budget from $50 to $65.

AI:
-> update_campaign_budget(...)
<- pending_confirmation
   risk_level: spend
```

Budget changes are spend-risk even if global standard auto-approve is enabled.

## 4. Restart between proposal and confirmation

```text
User:
Propose pausing ad 456.

AI:
-> update_ad_status(... status="PAUSED")
<- pending_action_id: abc123
   durable: true

[the MCP process restarts]

User:
Confirm abc123.

AI:
-> confirm_pending_action("abc123")
<- replayed_after_restart: true
   executed
```

With the built-in SQLite backend, the original invocation is encrypted at rest and can be replayed after restart using the same action ID.

## 5. Multi-client MCC isolation

Assume the deployment allowlist contains customers `1111111111` and `2222222222`.

```text
User:
Update customer 111's campaign, but pass a campaign resource belonging to 222.

AI:
-> mutation validation
<- Cross-customer mutation blocked before Google Ads
```

A legitimate MCC link is different:

```text
User:
From manager 111, invite client 222.

AI:
-> invite_manager_link(manager_customer_id="111...", client_customer_id="222...")
<- pending_confirmation
```

That path is permitted because the cross-account reference is intentional and both customers are explicitly inside the deployment scope.

## 6. Performance Max signal

```text
User:
Add the search theme "emergency plumber" to asset group 987.

AI:
-> add_asset_group_signal(
     customer_id=...,
     asset_group_id="987",
     signal_type="SEARCH_THEME",
     value="emergency plumber"
   )
<- pending_confirmation
```

PMax signal/listing changes are treated conservatively because they can affect delivery.

## 7. Performance Max retail listing tree

```text
User:
Replace asset group 987's listing filters so it advertises only our Product Tag
shared set plus an explicit everything-else branch.

AI:
-> replace_asset_group_listing_filter_tree(...)
<- pending_confirmation
```

The v0.16 implementation supports Shopping dimensions, RETAIL Product Tags via `retail_filter_bundle`, explicit other nodes and WEBPAGE root semantics from v25.

## 8. Atomic experiment traffic split

```text
User:
Move my two experiment arms from 50/50 to 70/30.

AI:
-> update_experiment_traffic_split(
     customer_id=...,
     arm_splits=[
       {"experiment_arm_resource_name":".../experimentArms/1", "traffic_split":70},
       {"experiment_arm_resource_name":".../experimentArms/2", "traffic_split":30}
     ]
   )
<- pending_confirmation
```

Both arms are updated in one request so the total=100 invariant is preserved.

## 9. Customer Match without putting identifiers in the normal audit payload

```text
User:
Upload these eligible Customer Match members to list X.

AI:
-> upload_customer_match_members(...)
<- pending_confirmation
   risk_level: sensitive
```

Normal audit metadata records counts and destination information, not the raw identifiers. Durable replay arguments are encrypted at rest.

## 10. Batch Job

```text
User:
Pause these 25 campaign/ad-group/ad rows after I review the manifest.

AI:
-> submit_batch_job(... reviewed manifest ...)
<- pending_confirmation
   risk_level: sensitive

User:
Confirm.

AI:
-> confirm_pending_action(...)
<- submitted

AI:
-> get_batch_job_results(...)
<- row-level outcomes
```

Batch Jobs can partially succeed. Always inspect results rather than assuming rollback.

## 11. Specialist Google-controlled service

```text
User:
Generate ad image ideas using Google's Asset Generation service.

AI:
-> generate_asset_images(...)
```

If the account is not enabled for the upstream closed-beta/allowlisted service, Google returns the entitlement error. The MCP does not return a fake success.

## 12. Inspect one action's audit history

```text
User:
Show me what happened with action abc123.

AI:
-> get_audit_action("abc123")
<- attempt 1: error
   attempt 2: success
```

The proposal ID, confirmation ID and audit correlation ID are the same identifier.

## Recommended production prompt pattern

When operating live accounts, prompts should make scope and intent explicit:

```text
Use only customer 123-456-7890.
Read current state first.
Propose the changes and show me the pending actions.
Do not confirm or enable spend-changing actions unless I explicitly tell you to.
```

The server enforces its own safety policy regardless of prompt wording, but explicit operator intent makes the workflow easier to review.

See also:

- [`TOOLS.md`](TOOLS.md)
- [`SAFETY.md`](SAFETY.md)
- [`SETUP.md`](SETUP.md)
- [`V25_SERVICE_COVERAGE.md`](V25_SERVICE_COVERAGE.md)
- [`RELEASE_0.16.0.md`](RELEASE_0.16.0.md)