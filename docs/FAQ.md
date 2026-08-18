# FAQ — Google Ads MCP v0.12

## What does this MCP do?

It gives an MCP client structured read/write access to Google Ads: reporting, campaigns, budgets, bidding, ad groups, ads, assets, keywords, audiences, targeting, conversions, Performance Max, experiments, recommendations and MCC workflows.

## Is it reporting-only?

No. Read tools return account data; write tools propose real Google Ads mutations through a confirmation layer.

## Which Google Ads API version does v0.12 target?

Google Ads API **v25**. The project explicitly requests `v25` and pins the Python client to the tested 31.x line instead of silently following a future default API version.

## Why did v0.12 need a compatibility pass?

Google Ads removes and replaces resources/fields regularly. Earlier versions contained several shapes that permissive unit-test fakes could accept even though the current generated Google client would reject them. v0.12 adds real generated-protobuf contract tests to prevent that class of regression.

## Does a write change the account immediately?

Not by default. With:

```dotenv
GOOGLE_ADS_MCP_AUTO_APPROVE=false
```

a write returns `pending_confirmation`. Execute it with `confirm_pending_action(action_id)`.

## What happens if confirmation fails?

The action remains pending and can be retried with the same ID. Failed and successful attempts are recorded under that stable action ID.

## Can I enable automatic writes?

Yes:

```dotenv
GOOGLE_ADS_MCP_AUTO_APPROVE=true
```

Use it only in a controlled environment. For accounts with real spend, the safer default is explicit confirmation.

## Where is the audit log?

By default:

```text
~/.google_ads_mcp/audit.db
```

Use `get_recent_audit_log()` for recent attempts and `get_audit_action(action_id)` for all attempts associated with one proposal.

## Does it support MCC accounts?

Yes. Set `GOOGLE_ADS_LOGIN_CUSTOMER_ID` when the authenticated identity operates client accounts through an MCC. The MCP can list hierarchies, create client accounts and accept manager links where your Google Ads permissions allow it.

## Can it create Call Ads?

Google removed the old Call Ad resource. The compatibility tool `create_call_ad` now creates the supported replacement: a **Responsive Search Ad + Call Asset + ad-group asset link**, atomically.

Because the replacement is an RSA, a final URL is required.

## Can it create WhatsApp/message assets?

The old Message Asset shape is not used. `create_message_asset` is retained as a compatibility name and now creates a current **Business Message Asset with WhatsApp provider**.

## Can it create Local Campaigns?

Not through the obsolete Local Campaign API shape. v0.12 intentionally refuses that mutation and directs the workflow to Performance Max plus the relevant location/business assets.

## Can it create Smart Shopping campaigns?

No new legacy Smart Shopping campaigns are created. Use Performance Max. Standard Shopping remains supported.

## Does it manage Merchant Center products or feeds?

No. Merchant Center feed/product administration is a separate API/product. Shopping and retail PMax workflows expect the necessary Merchant Center linkage/catalog to exist.

## Can it create Performance Max campaigns?

Yes. v0.12 uses current PMax bidding shapes and can build a complete non-retail AssetGroup with its required text/image/brand assets in one atomic mutation.

## Why does `create_asset_group` require images now?

Because current non-retail PMax AssetGroup creation must satisfy required asset structure. Creating a text-only shell first and hoping to attach mandatory assets later is not a reliable v25 workflow.

## Why are PMax campaign brand guidelines disabled in this flow?

The current MCP workflow keeps business name and logo assets inside the AssetGroup. Disabling campaign-level brand guidelines makes that structure explicit and consistent.

## Can it edit an existing RSA?

Yes. v0.12 edits the underlying Ad with `AdService` / `AdOperation`, which is the current API path for RSA creative fields.

## Can it change keyword match type?

Yes, but Google treats match type as immutable on an existing criterion. The MCP fetches the existing keyword, creates the replacement with the new match type and removes the old criterion atomically.

## Can it add negative keywords in bulk?

Yes. Bulk writes default to all-or-nothing behavior instead of accepting silent partial success.

## Why does website remarketing require `url_contains`?

An empty flexible-rule audience is not a safe “all visitors” wildcard. v0.12 creates a real website rule such as:

```text
url__ CONTAINS example.com
```

Use the site's hostname for a typical all-pages audience.

## Does it install the remarketing tag?

No. The Google Ads tag must already be installed and firing.

## Does Customer Match send raw email/phone values to the audit log?

No. Identifiers are normalized and SHA-256 hashed locally before Google upload, and the safety/audit payload contains counts rather than raw PII.

## Which conversion action should I create for GCLID offline uploads?

Use:

```text
conversion_action_type="UPLOAD_CLICKS"
```

v0.12 verifies the target action type and enabled state before an offline click upload is proposed.

## What happened to `include_in_conversions_metric`?

Google's resource field is immutable. The public compatibility argument remains, but v0.12 maps primary/secondary behavior to the mutable `primary_for_goal` field.

## Does enhanced conversion hashing normalize Gmail addresses?

Yes. v0.12 normalizes Gmail/Googlemail local parts before hashing and normalizes phone numbers to E.164.

## Can it target locations by name?

Yes. Text names are resolved live through Google's GeoTarget suggestion service rather than a stale hard-coded location map. Ambiguous names fail safely and ask for a numeric criterion ID.

## Does `set_language_targeting` really replace languages?

Yes in v0.12. Existing language criteria are removed and the supplied set is created together instead of accumulating duplicates.

## Does `set_device_bid_modifier` create duplicate criteria?

It first looks for the existing device criterion and updates it when present; otherwise it creates it.

## What device modifier values are allowed?

`0` is used to opt out of the device. Otherwise v0.12 validates the supported `0.1–10.0` range.

## Can it create Demand Gen campaigns?

Yes. The campaign creator uses the current campaign structure. `create_ad_group(..., ad_group_type="AUTO")` detects Demand Gen and leaves the ad-group type unset as required.

## Can it create Video ad groups automatically?

Video can have multiple valid ad-group types. `AUTO` therefore refuses to guess and requires an explicit current `AdGroupType` enum for ambiguous channels.

## Can it run experiments?

Yes. The MCP can set up a system-managed experiment, create control/treatment arms, list the treatment's `in_design_campaigns`, promote, and end experiments.

## Can it apply Google Ads recommendations?

Yes, through the safety layer. Recommendation listing uses the current `dismissed` field; apply/dismiss use current v25 operation types.

## Does it support raw GAQL?

Yes via `run_gaql_query`. Prefer specialized report tools when they already cover the request because they provide a more predictable contract for an agent.

## Is HTTP transport safe to expose publicly?

No. The raw MCP HTTP server does not bundle a remote authentication provider. v0.12 therefore blocks HTTP startup by default.

For local clients use `stdio`.

If you deliberately put it behind your own authenticated and network-restricted reverse proxy, explicit opt-in is required:

```dotenv
GOOGLE_ADS_MCP_TRANSPORT=http
GOOGLE_ADS_MCP_ALLOW_INSECURE_HTTP=true
```

That flag does not add authentication itself.

## Why are image URLs restricted?

They are model/user-controlled network inputs. v0.12 only fetches public HTTPS images and rejects private/loopback/link-local destinations, unsafe redirects, unsupported MIME types and oversized responses to reduce SSRF risk.

## Why does CI use real protobuf contract tests?

A generic fake that creates arbitrary nested attributes can accidentally make removed fields look valid. Contract tests instantiate Google's real generated v25 types, so an old field/enum/service path fails in CI immediately.

## Which Python versions are supported?

Python 3.11+; CI covers 3.11, 3.12 and 3.13.

## How do I generate a refresh token?

Install the optional auth dependency and run:

```bash
pip install -e ".[auth]"
python -m google_ads_mcp.auth --generate-refresh-token
```

## Why does the MCP work in my shell but fail inside Claude Desktop?

Usually the MCP host is launching a different Python. Configure the MCP with the **absolute path to the virtualenv Python**, not a bare `python` command.

## What should I test first after setup?

Start read-only:

```text
List my accessible Google Ads customer IDs.
```

Then pull a report. Only after those work should you propose a harmless write against a test account or a paused resource.

## Is every Google advertising product covered?

No. The project targets Google Ads API account operations. Merchant Center feed administration, Business Profile linking and other adjacent products remain separate boundaries.
