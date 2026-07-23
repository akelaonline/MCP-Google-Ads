# Changelog

## 0.1.0 — Initial release
Created by Akela (https://github.com/akelaonline).

- Full read/write Google Ads MCP server on the official `google-ads` Python client (API v20).
- ~40 tools across accounts, reporting (GAQL + pre-built reports), campaigns, budgets, bidding
  strategies, ad groups, responsive search ads, keywords/negatives, audiences, and offline
  conversion upload.
- Human-in-the-loop safety layer: every write proposes a change and requires
  `confirm_pending_action` before it executes, with an opt-in `GOOGLE_ADS_MCP_AUTO_APPROVE`
  for automated pipelines.
- SQLite audit log of every executed mutation.
- stdio and HTTP transports (FastMCP).
- OAuth refresh-token helper (`python -m google_ads_mcp.auth --generate-refresh-token`).
