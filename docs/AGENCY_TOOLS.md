# Agency tools — v0.14 / Google Ads API v25

v0.14 adds agency-operations surfaces on top of the v0.13 customer isolation and risk-aware approval policy.

All writes below go through `SafetyLayer`. Customer IDs are subject to `GOOGLE_ADS_MCP_ALLOWED_CUSTOMER_IDS` when configured.

## Labels

### `list_labels(customer_id)`
Read-only. Lists customer labels, status, color, description and resource name.

### `create_label(customer_id, name, background_color=None, description=None)` `[write]`
Creates a label. Name: 1–80 characters. Optional color: `#RGB` or `#RRGGBB`. Optional description: up to 200 characters.

### `update_label(customer_id, label_id, name=None, background_color=None, description=None)` `[write]`
Updates supplied label fields using a field mask.

### `remove_label(customer_id, label_id)` `[destructive write]`
Permanently removes a label.

### `attach_label_to_campaign(customer_id, campaign_id, label_id)` `[write]`
Attaches an existing label to a campaign.

### `remove_label_from_campaign(customer_id, campaign_id, label_id)` `[destructive write]`
Removes the campaign-label relationship.

### `attach_label_to_ad_group(customer_id, ad_group_id, label_id)` `[write]`
Attaches an existing label to an ad group.

### `remove_label_from_ad_group(customer_id, ad_group_id, label_id)` `[destructive write]`
Removes the ad-group-label relationship.

## Shared negative keyword lists

These tools use the native Google Ads shared-set model: `SharedSet(NEGATIVE_KEYWORDS)` + `SharedCriterion` + `CampaignSharedSet`.

### `list_shared_negative_keyword_lists(customer_id)`
Read-only. Lists shared negative sets, member counts and campaign reference counts.

### `list_shared_negative_keywords(customer_id, shared_set_id)`
Read-only. Lists criteria inside one shared negative keyword set.

### `create_shared_negative_keyword_list(customer_id, name)` `[write]`
Creates an empty shared negative keyword list.

### `add_shared_negative_keywords(customer_id, shared_set_id, keywords)` `[write]`
Adds up to 10,000 keywords in one call. Each item is:

```json
{"text": "free", "match_type": "BROAD"}
```

Supported match types: `BROAD`, `PHRASE`, `EXACT`.

### `remove_shared_negative_keyword(customer_id, shared_set_id, criterion_id)` `[destructive write]`
Permanently removes one criterion from the shared list.

### `attach_shared_negative_keyword_list_to_campaign(customer_id, campaign_id, shared_set_id)` `[write]`
Attaches the shared negative list to a campaign.

### `remove_shared_negative_keyword_list_from_campaign(customer_id, campaign_id, shared_set_id)` `[destructive write]`
Detaches the shared list from a campaign.

### `remove_shared_negative_keyword_list(customer_id, shared_set_id)` `[destructive write]`
Permanently removes the whole shared negative keyword list.

## Account users & access

Account-access writes are treated as high-risk by the v0.13 safety policy.

### `list_account_users(customer_id)`
Read-only. Lists direct users, email addresses, roles, creation metadata and multi-party authorization state when exposed.

### `list_user_access_invitations(customer_id)`
Read-only. Lists invitations visible through GAQL. Google may omit invitations that are waiting for multi-party authorization review from Search/SearchStream.

### `invite_account_user(customer_id, email_address, access_role)` `[sensitive write]`
Invites a user. Supported roles: `ADMIN`, `STANDARD`, `READ_ONLY`, `EMAIL_ONLY`.

### `update_user_access_role(customer_id, user_id, access_role)` `[sensitive write]`
Changes an existing user's role.

### `remove_account_user(customer_id, user_id)` `[destructive write]`
Removes direct account access.

### `revoke_user_access_invitation(customer_id, invitation_id)` `[destructive write]`
Revokes a pending invitation.

## Billing & invoices

Billing tools in v0.14 are read-only.

### `list_billing_setups(customer_id)`
Lists billing setups and payments-account/profile metadata available through GAQL.

### `list_invoices(customer_id, billing_setup_id, issue_year, issue_month, include_granular_details=False)`
Calls `InvoiceService.ListInvoices` for one billing setup and month.

- `issue_year`: 2019 or later.
- `issue_month`: full English month name, for example `JULY`.
- `include_granular_details`: request granular invoice details when available.

## Conversion adjustments

Conversion adjustments are classified `sensitive` and stay confirmation-gated unless sensitive auto-approve is explicitly enabled.

Google requires `partial_failure=true` on the upload RPC. The MCP inspects `partial_failure_error` and raises an MCP error instead of reporting a row-level rejection as success.

### `retract_conversion(customer_id, conversion_action_id, order_id, adjustment_date_time)` `[sensitive write]`
Retracts a previously reported conversion using its order ID.

### `restate_conversion_value(customer_id, conversion_action_id, order_id, adjustment_date_time, adjusted_value, currency_code=None)` `[sensitive write]`
Restates a previously reported conversion value. `adjusted_value` must be zero or greater. Optional currency is a three-letter ISO 4217 code.

Adjustment timestamps use:

```text
yyyy-mm-dd hh:mm:ss+|-hh:mm
```

Example:

```text
2026-08-18 16:30:00-03:00
```

## Safety recommendation for agencies

For one MCP instance per customer:

```dotenv
GOOGLE_ADS_MCP_ALLOWED_CUSTOMER_IDS=123-456-7890
GOOGLE_ADS_MCP_REQUIRE_CUSTOMER_ALLOWLIST=true
GOOGLE_ADS_MCP_AUTO_APPROVE=false
GOOGLE_ADS_MCP_AUTO_APPROVE_SPEND=false
GOOGLE_ADS_MCP_AUTO_APPROVE_DESTRUCTIVE=false
GOOGLE_ADS_MCP_AUTO_APPROVE_SENSITIVE=false
```

For an intentional shared MCC deployment, include only the customer IDs that instance is supposed to operate, plus the MCC ID when hierarchy queries are needed.
