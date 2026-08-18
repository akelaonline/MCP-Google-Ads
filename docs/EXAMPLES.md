# Examples — v0.12

These examples show the intended conversation flow. Write calls are proposals by default; confirm them explicitly before live execution.

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
It is not EU political advertising. Leave it paused.

AI:
-> create_campaign_budget(... daily_amount=50)
<- pending action

User:
Confirm.

AI:
-> confirm_pending_action(...)
<- campaign budget resource name

AI:
-> create_campaign(
     name="Brand AR",
     campaign_budget_resource_name="customers/.../campaignBudgets/...",
     channel_type="SEARCH",
     bidding_strategy="MAXIMIZE_CONVERSIONS",
     contains_eu_political_advertising="DOES_NOT_CONTAIN_EU_POLITICAL_ADVERTISING"
   )
<- pending action
```

New campaigns are created PAUSED by the MCP.

## 3. Current Call Ad replacement

Google removed the old Call Ad resource. Keep the same high-intent behavior with an RSA plus a Call Asset:

```text
User:
Create a phone-focused Search ad in ad group 222 using +54 11 1234 5678.
Use these headlines/descriptions and https://example.com as final URL.

AI:
-> create_call_ad(...)
<- proposes one atomic RSA + Call Asset + AdGroupAsset change
```

The public tool name is retained for compatibility, but it does not send a removed `CallAd` protobuf.

## 4. WhatsApp Business Message asset

```text
User:
Add a WhatsApp message asset to campaign 333 for Argentina, phone 1112345678.
Starter message: "Hola, quiero información".

AI:
-> create_message_asset(
     campaign_id="333",
     country_code="AR",
     phone_number="1112345678",
     business_name="Example",
     message_text="Hola, quiero información",
     call_to_action_text="Contactanos"
   )
<- proposes Business Message / WhatsApp + CampaignAsset atomically
```

`create_message_asset` is a compatibility name for the current Business Message resource.

## 5. Complete Performance Max asset group

```text
User:
Create a PMax campaign and a complete asset group for this landing page.
Use these 3 headlines, long headline, 2 descriptions, business name,
1 landscape image, 1 square image and 1 logo. Leave everything paused.

AI:
-> create_performance_max_campaign(...)
<- pending

User:
Confirm.

AI:
-> confirm_pending_action(...)

AI:
-> create_asset_group(
     campaign_id="...",
     name="Core",
     final_urls=["https://example.com"],
     headlines=[...],
     long_headline="...",
     descriptions=[...],
     business_name="Example",
     marketing_image_urls=["https://cdn.example.com/landscape.jpg"],
     square_marketing_image_urls=["https://cdn.example.com/square.jpg"],
     logo_image_urls=["https://cdn.example.com/logo.jpg"]
   )
<- one atomic Asset + AssetGroup + AssetGroupAsset proposal
```

The image URLs must be public HTTPS and pass the MCP's SSRF/content/size checks.

## 6. Offline conversion upload

First create the correct immutable conversion-action type:

```text
User:
Create an offline Qualified Lead conversion action called "CRM Qualified Lead".

AI:
-> create_conversion_action(
     name="CRM Qualified Lead",
     category="QUALIFIED_LEAD",
     conversion_action_type="UPLOAD_CLICKS"
   )
```

Later:

```text
User:
Upload this GCLID conversion against action 777, value USD 500,
conversion time 2026-08-18 12:00:00-03:00.

AI:
-> upload_offline_conversion(...)
```

Before proposing the upload, v0.12 verifies that action 777 exists, is ENABLED and has type `UPLOAD_CLICKS`.

## 7. Enhanced offline conversion

```text
User:
Same conversion, with email Jane.Doe+Lead@gmail.com and phone +54 9 11 1234-5678.

AI:
-> upload_enhanced_conversion(...)
```

Email/phone normalization and SHA-256 happen locally; raw PII is not placed in the audit payload.

## 8. Website remarketing

```text
User:
Create a 30-day all-pages remarketing audience for example.com.

AI:
-> create_remarketing_list(
     name="All visitors 30d",
     membership_days=30,
     url_contains="example.com"
   )
```

An empty rule is not used. v0.12 creates a real `url__ CONTAINS example.com` rule.

## 9. Replace campaign language targeting

```text
User:
Make campaign 444 target only English and Spanish.

AI:
-> set_language_targeting(
     campaign_id="444",
     language_codes=["1000", "1003"]
   )
```

The setter removes existing language criteria and creates exactly the supplied set in one mutation.

## 10. Device modifier

```text
User:
Exclude tablets from campaign 444.

AI:
-> set_device_bid_modifier(
     campaign_id="444",
     device="TABLET",
     bid_modifier=0
   )
```

If the device criterion already exists, it is updated; otherwise it is created.

## 11. Google recommendations

```text
User:
Show active recommendations only.

AI:
-> get_recommendations(customer_id="...")
```

To apply one:

```text
AI:
-> apply_recommendation(resource_name="customers/.../recommendations/...")
<- pending_confirmation
```

To dismiss one:

```text
AI:
-> dismiss_recommendation(resource_name="customers/.../recommendations/...")
<- pending_confirmation
```

## 12. Experiment workflow

```text
User:
Set up a 50/50 Search experiment from campaign 555 called "tCPA test".

AI:
-> create_experiment(
     base_campaign_id="555",
     name="tCPA test",
     traffic_split_percent=50
   )
```

After creation:

```text
AI:
-> list_experiments(...)
```

Use the treatment arm's `in_design_campaigns` result to identify the system-created draft and modify it before scheduling/running the test.

## 13. Raw GAQL fallback

Prefer specialized reporting tools where possible. For custom analysis:

```text
User:
Run this GAQL against customer 123-456-7890:

SELECT campaign.id, campaign.name, metrics.cost_micros
FROM campaign
WHERE segments.date DURING LAST_30_DAYS
ORDER BY metrics.cost_micros DESC
```

```text
AI:
-> run_gaql_query(...)
```

## 14. Retry a failed confirmation

```text
AI:
-> confirm_pending_action("abc123")
<- transient Google/network error
```

v0.12 keeps the action pending. After fixing the underlying problem:

```text
AI:
-> confirm_pending_action("abc123")
<- success
```

Both attempts are recorded under the same action ID:

```text
AI:
-> get_audit_action("abc123")
```
