# Merchant API v1 — onboarding, scope and migration (0.18.1)

Authors: Alejandro José / Akela. Nothing here registers anything for you: every
step below is performed by the owner in Google's consoles.

## What changed in 0.18.1

* Products and DataSources moved from `v1beta` to **`v1`** (Accounts and Reports
  were already `v1`). `v1beta` is no longer used by this server.
* Product IDs follow `contentLanguage~feedLabel~offerId`. If a part contains
  `/`, `%` or `~` the whole ID is sent as unpadded base64url. The old `online~`
  (v1beta) prefix is converted; `local~` is kept as Google defines it.
* `ProductInput` no longer has `channel`; attributes are sent as
  `productAttributes`, GTINs as `gtins`; `taxes`/`taxCategory` were removed.
* MCQL: `product_view.language_code` (the old `content_language` never existed).

## One-time Google Cloud developer registration

Merchant API v1 requires the Google Cloud project that owns the OAuth client to
be registered once per Merchant Center account
(`accounts.developerRegistration.registerGcp`, or Merchant Center → Settings →
API). Until then v1 calls fail; the server turns that error into a hint pointing
here. This repository does **not** create registrations and no tool does.

Checklist (owner): Merchant API enabled in the Cloud project → OAuth refresh token
with the `https://www.googleapis.com/auth/content` scope → registration done in
Merchant Center → run read-only checks first.

## Scope isolation (new, fail closed)

Merchant account IDs and Google Ads customer IDs are different identifier
spaces. A Google Ads allowlist never authorizes a Merchant account.

| Setting | Effect |
|---|---|
| `GOOGLE_ADS_MCP_ALLOWED_MERCHANT_IDS=111,222` | Only those accounts (and sub-accounts) are reachable. |
| `GOOGLE_ADS_MCP_REQUIRE_MERCHANT_ALLOWLIST=true` | Startup fails if the list is empty. |
| Ads allowlist configured, Merchant list empty | **Merchant access refused** with an explicit message. |
| Nothing configured | Unscoped (development setups behave as before). |

Enforced at: every Merchant tool (explicit ID and default ID), the REST client
(account in the request path), `propose` / `confirm` / durable replay of pending
actions, discovery results (`list_merchant_center_accounts`, sub-accounts are
filtered), and the Ads-side tools that name a Merchant account:
`create_shopping_campaign`, `create_merchant_center_link`, `create_asset_set`
(MERCHANT_CENTER_FEED). A rejected target makes zero calls.

### Migration note (possible surprise)

A deployment that already has `GOOGLE_ADS_MCP_ALLOWED_CUSTOMER_IDS` and uses
Merchant tools **stops working for Merchant until you add
`GOOGLE_ADS_MCP_ALLOWED_MERCHANT_IDS`**. This is deliberate: the previous
behaviour silently allowed any Merchant account. Nothing is widened
automatically; add only the Merchant IDs you intend to expose.

## Status

Verified against Google's published v1 discovery documents and with offline
tests. **Live Merchant validation: NOT RUN** (see `docs/REAL_VALIDATION_LAB.md`).
