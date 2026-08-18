# v0.12.0 — Google Ads API v25 compatibility & hardening

v0.12.0 is a repair release. It deliberately prioritizes correctness, current Google Ads API contracts, transaction safety, and regression coverage over adding new product features.

## Compatibility

- Explicit Google Ads API version: `v25`.
- Google Ads Python client constrained to the tested 31.x line.
- Campaign date inputs map to v25 `start_date_time` / `end_date_time` fields.
- Campaign creation supplies the required EU political-advertising declaration.
- Proto-plus compatibility pass removes native-protobuf-only `SetInParent()` calls.

## Removed/legacy API migrations

- Legacy Call Ad protobufs are no longer used. `create_call_ad` now builds RSA + Call Asset + AdGroupAsset atomically.
- Legacy Message Asset protobufs are no longer used. `create_message_asset` now builds Business Message / WhatsApp assets.
- Legacy Local campaign creation is refused safely; use Performance Max.
- Legacy Smart Shopping creation is refused; use Performance Max.
- RSA creative updates use `AdService` / `AdOperation`.

## Performance Max

- PMax uses current Maximize Conversions / Maximize Conversion Value strategy shapes.
- Campaigns are created PAUSED with brand-guideline behavior matching the AssetGroup branding flow.
- Complete non-retail AssetGroups and their required assets are created in one atomic Google Ads mutation.
- Text/image/video additions use atomic create+link flows.
- Retail listing filters build a complete included + excluded-Other partition.

## Write safety

- Pending IDs and audit IDs are now the same stable ID.
- Failed confirmations stay pending and can be retried.
- Retry attempts are recorded under the same action ID.
- SQLite audit writes use locking/WAL behavior and expose per-action history.
- Multi-resource mutations use `GoogleAdsService.Mutate` where all related resources must succeed together.
- Bulk status/negative operations default to all-or-nothing instead of silent partial success.

## Network safety

- Image URLs must use public HTTPS.
- Private, loopback, link-local and otherwise non-global destinations are rejected.
- Redirects are revalidated.
- Image content type and response size are bounded.
- Unauthenticated HTTP MCP transport is blocked by default; stdio remains recommended.

## Targeting & audiences

- Text locations are resolved live through Google's geo-target suggestion service instead of stale hard-coded mappings.
- `set_language_targeting` replaces the existing language set instead of accumulating duplicates.
- `set_device_bid_modifier` updates an existing device criterion when present and creates it only when missing.
- Device modifier validation matches current API behavior: `0` to opt out or `0.1–10.0` otherwise.
- Website remarketing now requires/builds a real URL rule; an empty flexible rule is no longer treated as “all visitors”.
- Demand Gen ad-group creation leaves type unset when using automatic campaign-aware resolution.

## Conversions

- `create_conversion_action` uses current conversion action types and supports explicit `UPLOAD_CLICKS` actions.
- Offline/enhanced click uploads verify the target action is enabled and type `UPLOAD_CLICKS` before proposal.
- Enhanced conversion email/phone normalization and hashing are performed locally.
- Primary/secondary conversion behavior uses mutable `primary_for_goal` rather than the immutable old include-in-conversions field.
- Conversion value rules use current v25 fields/enums.

## Recommendations & experiments

- Recommendations use the current `dismissed` field instead of a removed/nonexistent status field.
- Apply/dismiss use current v25 operation types.
- Experiment setup uses current system-managed control/treatment arm structure and exposes `in_design_campaigns` for the treatment draft.

## Regression coverage

CI continues across Python 3.11, 3.12 and 3.13 and now includes:

- installation smoke test;
- existing behavior/unit tests;
- source guardrails for removed API patterns;
- real Google Ads v25 generated protobuf contract tests for campaign, ad, asset, PMax, conversion, recommendation, bidding, budget, ad-group, targeting, audience, keyword and experiment write paths.

The purpose of the real-protobuf tests is to prevent permissive test fakes from accepting fields/enums/types that the actual Google client has removed.
