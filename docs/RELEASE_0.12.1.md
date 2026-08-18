# v0.12.1 — Production video hotfix

v0.12.1 closes a production-safety gap discovered after the v0.12 API-contract audit.

## Fixed

- Legacy Google Ads `VIDEO` campaigns are fetch/report-only through Google Ads API v25.
- `create_video_ad` is retained for client compatibility but performs no mutation and returns an explicit migration response.
- Added a source/contract regression guard that fails if the unsupported `ad.video_ad` write path returns.

## Added

- `create_demand_gen_video_ad` creates supported Demand Gen video responsive ads.
- The tool accepts 1-5 existing YouTube video IDs, 1-5 headlines, long headlines, descriptions and square logos.
- YouTube assets, logo assets and the PAUSED ad are created atomically with `GoogleAdsService.Mutate`.

## Operational impact

Existing clients can continue to discover/call `create_video_ad` without causing an unsupported Google Ads write. They receive a structured `unsupported` response and the replacement tool name. New video automation should use Demand Gen.
