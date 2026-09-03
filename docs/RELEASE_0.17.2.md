# Google Ads MCP 0.17.2

**Release date:** 2026-09-03
**Google Ads API:** v25
**Release type:** patch — follow-up fix, `mutate_atomic()` crashed on `validate_only` after 0.17.1 fixed `partial_failure`

0.17.2 fixes a second, near-identical bug in `mutate_atomic()` that surfaced immediately when re-testing `create_call_asset` against a live account right after deploying 0.17.1.

## What was broken

0.17.1 fixed `mutate_atomic()` crashing on `partial_failure` by adding an `inspect.signature()` guard before including that kwarg. But the fix left `validate_only` hard-coded into the initial `kwargs` dict, unconditionally, without the same guard. Re-testing `create_call_asset` against a real client campaign immediately after 0.17.1 landed, the call progressed past the `partial_failure` error — confirming that fix worked — and immediately hit:

```
GoogleAdsServiceClient.mutate() got an unexpected keyword argument 'validate_only'
```

Same root cause as 0.17.1, same fix pattern, just the other kwarg on the same call.

## Fix

`validate_only` is now added to `kwargs` conditionally, behind the same `inspect.signature(service.mutate).parameters` check already used for `partial_failure`. Both kwargs now go through identical defensive handling, matching `GoogleAdsClientWrapper.mutate()`'s existing (correct, unchanged) pattern for both parameters.

## Validation

Found live: re-tested `create_call_asset` against a real client campaign immediately after deploying 0.17.1, confirming `partial_failure` was fixed and catching `validate_only` failing next in the same call.

**Not run through `pytest` / `scripts/validate_local.py` in this pass** — same environment constraint as 0.17.1 (no Python 3.11+ interpreter available where the fix was authored). Per this project's normal release process, run before merging:

```bash
python scripts/validate_local.py
```

And re-test `create_call_asset` (or any other tool routed through `mutate_atomic`: `create_sitelink_asset`, `create_message_asset`, etc.) against a real account to confirm both kwargs are now handled correctly end to end — this bug specifically only surfaces at runtime against the real Google Ads client library, not in a code read.
