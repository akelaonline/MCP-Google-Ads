# Setup guide (step by step)

## 1. Google Cloud project + OAuth client

1. Go to [Google Cloud Console](https://console.cloud.google.com/) → create a new project (or reuse one).
2. Enable the **Google Ads API**: APIs & Services → Library → search "Google Ads API" → Enable.
3. APIs & Services → Credentials → **Create Credentials → OAuth client ID**.
   - Application type: **Desktop app**.
   - Save the generated Client ID and Client Secret — these are `GOOGLE_ADS_CLIENT_ID` / `GOOGLE_ADS_CLIENT_SECRET`.
4. If prompted, configure the OAuth consent screen (External is fine for personal/agency use; you don't need to publish it, "Testing" mode works as long as your Google account is added as a test user).

## 2. Developer token

1. Sign in to [Google Ads](https://ads.google.com) with the account you'll manage from (ideally your MCC/manager account).
2. Tools & Settings → Setup → **API Center**.
3. Accept the Terms of Service, then "Apply for token".
4. You'll first get **Test access** — can only touch test accounts, no real spend. Fine for building/testing this server.
5. Once you're ready for production, apply for **Standard access** from the same API Center screen (needed to read/write real client accounts). Google's review typically takes 1-3 business days; you'll be asked to describe the use case — "internal agency tool for managing our own and client Google Ads accounts via AI assistant" is an accurate, straightforward answer.

## 3. Refresh token

With `GOOGLE_ADS_CLIENT_ID` and `GOOGLE_ADS_CLIENT_SECRET` set in your `.env` (or exported as env vars):

```bash
pip install -e ".[auth]"
python -m google_ads_mcp.auth --generate-refresh-token
```

This opens a browser, you log in with the Google account tied to your Ads access, and the refresh token prints to your terminal. Paste it into `.env` as `GOOGLE_ADS_REFRESH_TOKEN`.

## 4. Login customer ID (only if using an MCC)

If you access client accounts through a manager account, set `GOOGLE_ADS_LOGIN_CUSTOMER_ID` to the **manager account's** ID (digits only, no dashes). This tells the API "act on behalf of this manager account."

If you're managing a single, non-MCC account directly, leave this blank.

## 5. Install & smoke test

```bash
python -m venv .venv && source .venv/bin/activate
pip install -e .
cp .env.example .env   # fill in the values from steps 1-4
python -c "
from google_ads_mcp.context import build_context
ctx = build_context()
print(ctx.client.service('CustomerService').list_accessible_customers())
"
```

If that prints a list of `customers/XXXXXXXXXX` resource names, your credentials work end to end.

## 6. Connect to Claude

Add to `~/.claude/settings.json` (Claude Code) or `claude_desktop_config.json` (Claude Desktop):

```json
{
  "mcpServers": {
    "google-ads": {
      "command": "python",
      "args": ["-m", "google_ads_mcp.server"],
      "env": { "GOOGLE_ADS_MCP_ENV_FILE": "/absolute/path/to/.env" }
    }
  }
}
```

Restart Claude. Ask it: *"List my accessible Google Ads customer IDs."*

## Troubleshooting

| Symptom | Likely cause |
|---|---|
| `PERMISSION_DENIED` / developer token errors | Token still in Test access — apply for Standard, or point at a test account. |
| `USER_PERMISSION_DENIED` | The OAuth account doesn't have access to that customer ID, or you need `GOOGLE_ADS_LOGIN_CUSTOMER_ID` set to the MCC. |
| `AUTHENTICATION_ERROR` | Refresh token expired/revoked — regenerate with the auth helper. |
| Nothing happens after a write tool | That's by design — check `list_pending_actions()` and call `confirm_pending_action(id)`. |
