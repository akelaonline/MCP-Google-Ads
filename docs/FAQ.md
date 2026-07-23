# FAQ — Integrating Claude with Google Ads

40 questions a marketer, developer, or agency owner would actually ask before and while using this server. Organized by stage: getting credentials, day-to-day use, safety, troubleshooting, and advanced setups.

---

## Getting credentials

**1. What do I actually need before I can start?**
Four things: a Google Cloud project, an OAuth 2.0 client (Desktop app type), a Google Ads Developer Token, and a refresh token. All four map directly to the four variables in `.env`. See [`SETUP.md`](SETUP.md) for the click-by-click version.

**2. Where do I get the Developer Token?**
Google Ads → Tools & Settings (wrench icon) → Setup → **API Center** → "Apply for token". You'll get **Test access** immediately (works only against test accounts, no real spend). For real accounts you need **Standard access**, which you apply for from the same screen — Google typically reviews it in 1-3 business days.

**3. What do I write in the "describe your use case" box when applying for Standard access?**
Be literal and specific: "Internal tool for managing our own and client Google Ads accounts through an AI assistant (Claude) — campaign/budget/keyword management and reporting." Google is checking you're not building spam/abuse tooling, not judging the idea.

**4. What's the difference between Test access and Standard access?**
Test access can only read/write **test accounts** (accounts explicitly marked as test in Google Ads) — zero real spend risk, but also zero real data. Standard access unlocks production accounts with real budgets. Build and test everything on Test access first.

**5. Where do I create the OAuth Client ID?**
[Google Cloud Console](https://console.cloud.google.com/) → APIs & Services → Credentials → Create Credentials → OAuth client ID → **Desktop app** type. This gives you `GOOGLE_ADS_CLIENT_ID` and `GOOGLE_ADS_CLIENT_SECRET`.

**6. Do I need to publish the OAuth consent screen?**
No. "Testing" mode is enough as long as you add your own Google account as a test user on that screen. Publishing is only needed if unrelated third parties will authorize through it.

**7. How do I get the refresh token?**
Run `python -m google_ads_mcp.auth --generate-refresh-token` after setting `GOOGLE_ADS_CLIENT_ID`/`GOOGLE_ADS_CLIENT_SECRET`. It opens a browser OAuth flow and prints the refresh token to paste into `.env` as `GOOGLE_ADS_REFRESH_TOKEN`.

**8. Does the refresh token expire?**
Not on a fixed schedule — it stays valid until you revoke it, the OAuth client is deleted, or Google flags unusual activity. If it stops working, just regenerate it with the same command.

**9. What is `GOOGLE_ADS_LOGIN_CUSTOMER_ID` and do I need it?**
Only if you access accounts through an MCC (manager) account. Set it to the **manager's** customer ID (digits only). If you're authenticating directly against a single non-MCC account, leave it blank.

**10. I manage accounts for multiple clients under one MCC — does this handle that?**
Yes. Authenticate once against the MCC with `GOOGLE_ADS_LOGIN_CUSTOMER_ID` set, then pass each client's `customer_id` per tool call. Use `get_account_hierarchy(login_customer_id)` to list every client account under the MCC.

---

## What Claude can actually do

**11. Can Claude create a campaign from scratch?**
Yes — `create_campaign_budget` then `create_campaign`, specifying channel type (Search, Display, Shopping, Video, Performance Max) and bidding strategy. New campaigns are always created **PAUSED** so you review before anything goes live.

**12. Can it pause/enable campaigns, ad groups, or ads?**
Yes, at all three levels: `update_campaign_status`, `update_ad_group_status`, `update_ad_status`.

**13. Can it change budgets?**
Yes — `create_campaign_budget` for a new one, `update_campaign_budget` to change an existing one's daily amount.

**14. Can it switch bidding strategies?**
Yes: Manual CPC, Maximize Conversions (with optional target CPA cap), Target CPA, and Target ROAS.

**15. Can it write ad copy and publish it?**
It can create Responsive Search Ads (`create_responsive_search_ad`) with your headlines/descriptions/URLs — Claude can draft the copy in the same conversation. The ad is created PAUSED, so you approve before it serves.

**16. Can it manage keywords?**
Yes — add keywords with match type and bid, pause/enable/remove them, and add negative keywords at either campaign or ad-group level.

**17. Can it pull reports?**
Yes, both pre-built (`get_campaign_performance`, `get_keyword_performance`, `get_search_terms_report`, `get_ad_performance`, `get_ad_group_performance`) and fully custom via `run_gaql_query` for anything the pre-built tools don't cover.

**18. Can it upload offline conversions?**
Yes — `upload_offline_conversion` takes a gclid, the conversion action, a value, and a timestamp. This is the tool for a "lead closes three days later via WhatsApp/CRM" workflow: you feed the sale back to Google Ads so Smart Bidding learns from real outcomes.

**19. Can it manage audiences?**
It can list existing user lists and attach one to an ad group with an optional bid modifier. It does not currently build new Customer Match lists from scratch.

**20. Can it see what changed in the account recently, even changes I made manually?**
Yes — `get_change_history` reads Google's native `change_event` resource, up to 30 days back, including who made the change and from where.

**21. Does it support Performance Max?**
`create_campaign` accepts `channel_type=PERFORMANCE_MAX`, but full PMax asset-group management (images, videos, listing groups) isn't built yet — that's the next roadmap item. Track it in `CHANGELOG.md`.

**22. Can Claude analyze performance and suggest what to change, not just execute?**
Yes — that's most of what you'll actually use day to day. Ask it to pull a report, reason about it, and propose specific changes; it'll only touch the account once you say go.

**23. Can it manage Display or Video campaigns, not just Search?**
Campaign creation supports any `advertising_channel_type` the API accepts. Ad-creative tools currently focus on Responsive Search Ads; Display/Video ad-creative tools aren't built yet.

**24. Can it A/B test ad copy?**
Not as a dedicated "experiment" object yet (Google Ads Drafts & Experiments API isn't wired up). You can approximate it by creating multiple RSAs in the same ad group and comparing performance manually.

---

## Safety and control

**25. Will Claude ever spend my money without asking?**
Not by default. Every write tool proposes a change and returns a `pending_action_id` — nothing executes until you (or Claude, on your instruction) calls `confirm_pending_action`. See [`SAFETY.md`](SAFETY.md).

**26. What if I want it to act fully autonomously, no confirmations?**
Set `GOOGLE_ADS_MCP_AUTO_APPROVE=true` in `.env`. Every action still gets logged to the audit trail, but nothing waits for confirmation. Only do this for a narrowly scoped, well-tested automation — not for open-ended conversational use on an account with real spend.

**27. Is there a record of what Claude actually changed?**
Yes — every executed mutation is written to a local SQLite file (`audit.db`) with the full payload, result, and timestamp. Query it directly or ask Claude: `get_recent_audit_log()`.

**28. What happens if I propose a change and then forget about it?**
It expires after `GOOGLE_ADS_MCP_PENDING_TTL_MINUTES` (30 minutes by default) so a stale proposal can't be confirmed hours later against a since-changed account.

**29. Can I undo something Claude changed?**
Not automatically — this server doesn't implement rollback. The audit log tells you exactly what changed and to what value, so you can manually reverse it (e.g. `update_campaign_budget` back to the old amount).

**30. Can Claude delete a campaign permanently?**
Yes, `remove_campaign` exists and works, but it's irreversible in Google Ads (removed campaigns can't be un-removed). Prefer `update_campaign_status(..., 'PAUSED')` unless you specifically need it gone.

---

## Troubleshooting

**31. I get `PERMISSION_DENIED` or a developer-token error.**
Your token is likely still on Test access — apply for Standard, or point the tool at a test account in the meantime.

**32. I get `USER_PERMISSION_DENIED` on a specific customer_id.**
The OAuth account behind your refresh token doesn't have access to that account, or you need `GOOGLE_ADS_LOGIN_CUSTOMER_ID` set to the parent MCC.

**33. I get `AUTHENTICATION_ERROR`.**
The refresh token expired or was revoked (e.g. you changed your Google account password, or revoked app access). Regenerate it with the auth helper.

**34. A write tool returned a preview but nothing happened in Google Ads — is it broken?**
No, that's the intended behavior. Check `list_pending_actions()` and call `confirm_pending_action(action_id)`.

**35. GAQL query errors with "unknown field."**
Field names are resource-specific and case-sensitive (e.g. `campaign.id`, not `campaign_id`). The error message from the API includes the exact valid field names for that resource — read it, it's usually a typo or wrong resource.

**36. Reports come back empty even though the account has activity.**
Check the `date_range` — `LAST_7_DAYS` excludes today by Google's convention. Also confirm you're querying the right `customer_id` (easy to mix up client vs. manager account).

---

## Advanced / architecture

**37. Does this run locally or in the cloud?**
Both. Default is `stdio` transport for Claude Desktop/Code running locally. For shared/remote use, run `python -m google_ads_mcp.server --transport http --port 8080` and deploy it (Cloud Run, a VPS, etc.) — see the deployment notes in the official Google server's README for the general pattern; this repo uses the same FastMCP HTTP transport.

**38. Can I restrict which tools are exposed (e.g. read-only for some users)?**
Not via config toggle yet (the official `googleads/google-ads-mcp` server has a `tools_config.yaml` for that — worth porting here, see `CONTRIBUTING.md` if you want to take it on). For now, the safety layer's confirmation requirement is the main control point.

**39. Is this affiliated with Google?**
No — it's an independent, unofficial project built on Google's official `google-ads` Python client library. It follows the same API terms as any other client of the Google Ads API.

**40. Why build this instead of using an existing Google Ads MCP server?**
Most existing servers on GitHub are read-only (reporting/GAQL only). This one was built specifically for active account management — creating and modifying campaigns, budgets, bidding, ads, and keywords — with a safety model appropriate for accounts with real client spend, which the read-only servers don't need and the few write-capable ones on GitHub generally don't have.
