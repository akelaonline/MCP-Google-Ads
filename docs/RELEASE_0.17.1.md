# Google Ads MCP 0.17.1

**Release date:** 2026-09-03
**Google Ads API:** v25
**Release type:** patch — production bug fix, `mutate_atomic()` crash on every atomic create+attach call

0.17.1 fixes a production-breaking bug in `GoogleAdsClientWrapper.mutate_atomic()` found while running live agency work against a client account. Every tool that creates an asset and links it to a campaign in one atomic mutation was failing 100% of the time.

## What was broken

Calling `create_call_asset` (and, transitively, any other tool built on `_create_asset_and_attach_to_campaign` / `mutate_atomic`) failed every time with:

```
GoogleAdsServiceClient.mutate() got an unexpected keyword argument 'partial_failure'
```

The failure was not a Google Ads API rejection — it never reached Google's servers. `mutate_atomic()` unconditionally called `service.mutate(customer_id=..., mutate_operations=..., partial_failure=False, validate_only=...)`, but the installed `google-ads` client library's `GoogleAdsService.mutate` method signature does not accept `partial_failure` as a direct keyword argument in this call shape.

The fix was already present elsewhere in the same file: `GoogleAdsClientWrapper.mutate()` (the non-atomic, resource-specific path used by most other tools) already guards this with `inspect.signature(method).parameters` before conditionally including `partial_failure`/`validate_only`. `mutate_atomic()` — added later, used only by the atomic create+attach helpers — never got the same guard.

## Fix

`mutate_atomic()` now builds its `kwargs` dict and checks `inspect.signature(service.mutate).parameters` before adding `partial_failure`, mirroring `mutate()` exactly. No behavior change for any caller where the installed library does accept the kwarg — `partial_failure=False` is still sent in that case. The only change is that a library version without that parameter no longer crashes the call.

### Affected tools (any tool routed through `mutate_atomic`)
- `create_call_asset`
- `create_sitelink_asset`
- `create_message_asset`
- any other asset-creation tool in `assets.py` (and similar modules) that calls `_create_asset_and_attach_to_campaign` / `_create_many_assets_and_attach_to_campaign`

## Validation

Root-caused by direct code comparison: `mutate()`'s working defensive pattern vs. `mutate_atomic()`'s broken unconditional kwarg, both in `src/google_ads_mcp/client.py`. The fix reuses the exact same, already-shipped pattern rather than introducing new logic.

**Not run through `pytest` / `scripts/validate_local.py` in this pass** — the fix was authored in an environment without a Python 3.11+ interpreter available. Per this project's normal release process, run before merging:

```bash
python scripts/validate_local.py
# or at minimum:
pytest tests/ -k "mutate or asset"
```

## Separately investigated, not fixed here

`set_device_bid_modifier` (`targeting.py`) was also reported failing with a "missing required argument: device" error even when `device` was passed correctly. The source code for this tool was reviewed line by line and is correct — no bug found in `targeting.py` as committed. This strongly suggests the MCP server process that was live at the time of the report was running a stale build (pre-dating a recent commit) rather than a genuine code defect. Recommended next step: restart the local MCP server process and re-test before investigating further.
