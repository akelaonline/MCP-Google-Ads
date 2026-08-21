# Changelog

Google Ads MCP follows Semantic Versioning. Detailed release notes for production releases live in `docs/RELEASE_X.Y.Z.md`.

## 0.16.7 — 2026-08-21

### Added
- `set_campaign_excluded_asset_field_types` — control which account-level extensions a campaign inherits (v25 `excluded_parent_asset_field_types`; empty list re-enables inheritance).
- `update_campaign_dates` — change a campaign's `start_date`/`end_date` (mapped to v25 `start_date_time`/`end_date_time`).
- `get_change_history` filters — optional `resource_type`, `operation` (ADD/SET/REMOVE) and `user_email` (with injection-safe validation).
- `set_target_cpa` and `set_target_roas` now accept optional `cpc_bid_ceiling` / `cpc_bid_floor` (with floor ≤ ceiling validation), matching the v25 `TargetCpa`/`TargetRoas` fields.

### Validation
- `python scripts/validate_local.py` green end-to-end: isolated smoke (55 tool modules, zero duplicate-tool warnings), Ruff clean, pytest **341/341 passed** (11 new v25 contract tests).

See `docs/RELEASE_0.16.7.md`.

## 0.16.6 — 2026-08-21

### Added
- **Extended asset creators** (new `assets_extended` module): `create_lead_form_asset` (headline, description, business name, call-to-action, fields with single-choice answers, webhook delivery, desired intent), `create_price_asset` (PriceExtensionType, qualifier, offerings with Money prices in a currency), `create_location_asset` (Google Place ID, account-level — v25 has no LOCATION AssetFieldType so there is no campaign link), `create_mobile_app_asset` (app id, store, link text) and `create_app_deep_link_asset` (account-level, no APP_DEEP_LINK AssetFieldType).
- **Positive placement targeting**: `add_placement_target` (WEBSITE / YOUTUBE_CHANNEL / YOUTUBE_VIDEO / MOBILE_APPLICATION with optional bid modifier) — complements `add_placement_exclusion`.
- **Frequency caps**: `set_campaign_frequency_caps` (level AD_GROUP_AD/AD_GROUP/CAMPAIGN, event IMPRESSION/VIDEO_VIEW, time unit DAY/WEEK/MONTH, time length, cap; empty list clears).
- **Audience exclusions**: `exclude_audience_from_ad_group` (modern Audience + legacy UserList/CustomAudience/CustomInterest) and `exclude_audience_from_campaign` (legacy kinds only; v25 CampaignCriterion has no modern audience field).
- **Conversion custom variables on uploads**: `upload_offline_conversion`, `upload_enhanced_conversion` and `upload_call_conversion` accept `custom_variables` (`[{"name": ..., "value": ...}]`).

### Fixed
- **Latent production bug**: `create_image_asset` linked campaigns with AssetFieldType `"IMAGE"`, which does not exist in v25 — the real value is `MARKETING_IMAGE`. The fake enum had masked this; `tests/conftest.py`'s `AssetFieldTypeEnum` now mirrors real v25 values (SITELINK=13, CALL=16, PRICE=24, LEAD_FORM=9, MOBILE_APP=14, ...).
- Contract tests assert the real `WebhookDelivery.advertiser_webhook_url` field and the `Money` shape of `PriceOffering.price`.

### Validation
- `python scripts/validate_local.py` green end-to-end: isolated smoke (**55 tool modules**, zero duplicate-tool warnings), Ruff clean, pytest **330/330 passed** (25 new tests, including v25 contract tests for all new tools).

See `docs/RELEASE_0.16.6.md`.

## 0.16.5 — 2026-08-21

### Added
- **GDPR consent on conversion uploads**: `upload_offline_conversion` and `upload_enhanced_conversion` now accept `consent` (`GRANTED`/`DENIED`), written to both `ad_user_data` and `ad_personalization` of the v25 `Consent` message — required for EEA conversions.
- **Search impression share diagnostics**: `get_impression_share_report` returns `search_impression_share`, `search_absolute_top_impression_share`, `search_top_impression_share`, `search_exact_match_impression_share`, `search_budget_lost_impression_share` (top/absolute-top breakdowns) and `search_rank_lost_impression_share` (top/absolute-top breakdowns) per campaign — the lost-IS budget/rank metrics operators use daily.
- **Standard Shopping listing groups** (new `shopping_listing_groups` module): `add_shopping_listing_group` (SUBDIVISION root / UNIT leaves with dimensions PRODUCT_BRAND, PRODUCT_ITEM_ID, PRODUCT_GROUPING, PRODUCT_LABELS, PRODUCT_TYPE, PRODUCT_CATEGORY, PRODUCT_CONDITION, PRODUCT_CHANNEL, PRODUCT_CHANNEL_EXCLUSIVITY; parent links for tree structure; bid modifiers), `update_shopping_listing_group`, `remove_shopping_listing_group`, `list_shopping_listing_groups`.
- **Ad rotation**: `set_campaign_ad_rotation` (`OPTIMIZE`, `CONVERSION_OPTIMIZE`, `ROTATE`, `ROTATE_INDEFINITELY`) via `campaign.ad_serving_optimization_status`.

### Fixed
- `tests/conftest.py` gained the missing `UserIdentifierSourceEnum` fake (no test previously exercised `upload_enhanced_conversion`'s identifier path) and real v25 values for `ProductConditionEnum` (`NEW=3`, not 2).

### Validation
- `python scripts/validate_local.py` green end-to-end: isolated smoke (54 tool modules, zero duplicate-tool warnings), Ruff clean, pytest **305/305 passed** (22 new tests, including v25 contract tests for the consent message, listing-group case values, and the ad-rotation update mask).

See `docs/RELEASE_0.16.5.md`.

## 0.16.4 — 2026-08-21

### Added
- **Ad schedule update/remove**: `update_ad_schedule` and `remove_ad_schedule` complement the existing `add_ad_schedule` (daypart criteria can now be edited or deleted, not only created).
- **Tracking URL / URL options**: new `url_options` module with `set_campaign_tracking_url`, `set_ad_group_tracking_url` and `set_account_tracking_url` (v25 `tracking_url_template`, `final_url_suffix`, `url_custom_parameters`), plus matching read tools `get_campaign_tracking_url`, `get_ad_group_tracking_url` and `get_account_tracking_url`.
- **Call conversion uploads**: `upload_call_conversion` via `ConversionUploadService.upload_call_conversions` (UPLOAD_CALLS actions), with caller-id masking in payloads/descriptions, E.164 validation, optional consent (v25 `Consent` message with `ad_user_data`/`ad_personalization` flags) and partial-failure surfacing.
- **App campaigns**: new `app_campaigns` module with `create_app_campaign` (ACi/ACe) using v25 `MULTI_CHANNEL` channel + `APP_CAMPAIGN`/`APP_CAMPAIGN_FOR_ENGAGEMENT` sub-type, `app_campaign_setting` (app store, bidding strategy goal type) and goal-validated bidding (target CPA / target ROAS / Maximize Conversions / Maximize Conversion Value). `create_ad_group` with `ad_group_type='AUTO'` now handles app campaigns (no ad-group type, like Demand Gen).
- **Dynamic Search Ads**: new `dynamic_search_ads` module with `create_dsa_campaign` (SEARCH channel + `dynamic_search_ads_setting`, no longer relying on the removed SEARCH_DYNAMIC_ADS channel sub-type), `create_dsa_ad_group` (`AdGroupType.SEARCH_DYNAMIC_ADS`), `add_webpage_target` (URL/CATEGORY/PAGE_TITLE/PAGE_CONTENT/CUSTOM_LABEL conditions with EQUALS/CONTAINS) and `list_webpage_targets`.

### Fixed
- `create_shopping_campaign` no longer writes `advertising_channel_sub_type = STANDARD_SHOPPING`: v25 removed that enum value (verified against the v25 proto and field reference). Standard Shopping is identified by SHOPPING channel + `shopping_setting`; this was a latent production bug that only a live-account call would have surfaced.
- The fake `AdvertisingChannelSubTypeEnum` and `MinuteOfHourEnum` in `tests/conftest.py` now mirror real v25 values (APP_CAMPAIGN=12, APP_CAMPAIGN_FOR_ENGAGEMENT=13, `MinuteOfHour.ZERO=2`).

### Known boundary
- Standard ad previews (`AdService.generate_preview`) do not exist in v25 — the RPC was removed from the API (verified against the v25 service stubs: only `mutate_ads` remains). PMax shareable previews (`generate_pmax_shareable_previews`) and YouTube previews remain the supported preview surfaces. This is documented, not emulated.

### Validation
- `python scripts/validate_local.py` green end-to-end: isolated smoke (53 tool modules, zero duplicate-tool warnings), Ruff clean, pytest **277/277 passed** (45 new tests, including v25 contract tests that build real protobuf messages and update masks).
- Live Google Ads API credentials and a real account were still not exercised; live-account E2E remains a separate step.

See `docs/RELEASE_0.16.4.md`.

## 0.16.3 — 2026-08-21

### Fixed
- The final 3 pytest failures from the 0.16.2 clean local run are resolved: `tests/conftest.py`'s `FakeEnums` now defines `ConsentStatusEnum` (`UNSPECIFIED`/`UNKNOWN`/`GRANTED`/`DENIED`, matching the real v25 `ConsentStatusEnum.ConsentStatus` contract) so Customer Match consent tests exercise the real `audiences.py` code path instead of failing on a missing mock attribute.
- Updated `test_upload_customer_match_members_requires_at_least_one_field` to match the current, more specific production error message ("No non-empty email or phone identifiers were supplied.") instead of the stale generic "at least one" wording.
- Updated `test_upload_customer_match_members_hashes_pii_and_runs_job`'s fake `OfflineUserDataJobService` to accept `enable_match_rate_range_preview`, a real v25 `CreateOfflineUserDataJobRequest` field the production tool now passes.
- Updated `test_asset_generation_v25_contracts_are_registered_and_customer_scoped` to expect `{"generated_text": []}` / `{"generated_images": []}` instead of `{}` — `proto.Message.to_dict(..., preserving_proto_field_name=True)` (the same call convention used everywhere else in this codebase) includes empty repeated fields by default; the test's expectation, not the production code, was wrong.
- `asset_generation_optional._generate()` now raises `TypeError` (not `ValueError`) when `request` is not a dict, matching the `TypeError`-for-wrong-type / `ValueError`-for-invalid-value convention already used by `batch_jobs.py`, `bulk.py`, and `keywords.py`.

### Hardening
- Replaced two blanket `except Exception` handlers with the specific exceptions each call site can actually raise: `AuditLog` pending-action decryption now catches `(InvalidToken, json.JSONDecodeError, UnicodeDecodeError)` instead of swallowing every exception silently as decrypt failure; `client.py`'s protobuf field-walker (used by the recursive MCC/customer-isolation guard) now catches `(ValueError, TypeError)` from `ListFields()` instead of masking unrelated bugs as "no scoped resources found."
- Reformatted the `allow_cross_customer_references or service_name == "..." and _all_operations_are_creates(...)` condition in `client.py`'s mutation-isolation gate into an explicitly named, parenthesized boolean (`is_scoped_manager_link_create`) after a Ruff auto-fix collapsed the original `if/elif` into a single line relying on unstated `and`/`or` precedence. Verified boolean-equivalent to the prior `if/elif` before and after reformatting; this is a readability fix in Google Ads MCP's most security-sensitive gate, not a behavior change.
- Fixed two `datetime.strptime()` calls (`billing.py`, `experiments.py`) that Ruff flagged as producing naive datetimes (`DTZ007`): both are format-only validation of customer-local calendar dates/timestamps with no real timezone semantics, so they're annotated `# noqa: DTZ007` with an explanation rather than forced into an incorrect UTC-aware value.
- Simplified `data_manager.py`'s RFC 3339 parsing to rely on `datetime.fromisoformat()`'s native `Z`-suffix support (Python 3.11+) instead of a manual `"Z" -> "+00:00"` string replace.
- Minor Ruff cleanups with no behavior change: sorted imports, `Callable` import moved to `collections.abc`, redundant `getattr()` call and dict-membership-then-index pattern simplified, nested `if` statements combined, unused `noqa: N802` directives removed, `scripts/validate_local.py` marked executable.

### Validation
- `python scripts/validate_local.py` is green end-to-end against this commit: isolated smoke (currency helpers, recursive MCC/Struct isolation, 50 tool modules import, `build_server()` succeeds with zero duplicate-registration warnings, canonical tool owners verified), Ruff (`ruff check src tests scripts` — 0 errors), and pytest (232/232 passed).
- This is the first version in the 0.16.x line where all four of the user's stated release gates (231/231 — now 232/232 after the consent-enum fix added one path — Ruff, smoke, zero duplicate-tool warnings) are simultaneously green in a real local run.
- Live Google Ads API credentials and a real account were still not exercised in this validation; only offline/mocked tests and the isolated smoke test ran. Live-account E2E remains a separate step before this replaces a running production MCP.

See `docs/RELEASE_0.16.3.md`.

## 0.16.2 — 2026-08-20

### Fixed
- Synchronized shared and real-protobuf test clients with the hardened production client contract by adding `assert_customer_allowed()` and `assert_resource_name_customer()` behavior instead of weakening production isolation to satisfy stale mocks.
- Corrected recommendation test fixtures that mixed customer `1234567890` with `customers/123/...` resource names.
- Removed runtime ambiguity from five duplicate public MCP tool names. PMax signal/listing tools now have `pmax_signals_listing.py` as their explicit canonical runtime owner; ConversionValueRule create/list tools now have `remaining_core_services.py` as their explicit canonical runtime owner.
- Unexpected future duplicate public tool registrations now fail server construction instead of relying on FastMCP overwrite order.
- Reset the replay/ownership registry for each new FastMCP server instance so repeated `build_server()` calls in one Python process do not create false duplicate errors.

### Validation
- The isolated smoke test now verifies canonical public tool ownership after server construction in addition to imports, currency helpers, recursive MCC isolation and temp/read-only server construction.
- Added regression coverage locking the canonical owners for the five known legacy duplicate definitions.
- 0.16.2 is the re-test target after a real clean local 0.16.1 run successfully collected 231 tests but reported 13 stale-fixture failures plus duplicate-registration warnings.
- This changelog does **not** claim the full suite is green yet. Run `python scripts/validate_local.py` against the exact 0.16.2 checkout before replacing a running MCP.

See `docs/RELEASE_0.16.2.md`.

## 0.16.1 — 2026-08-20

### Fixed
- Restored the missing `from_micros()` helper in `client.py`. `reporting.py` imported this helper unconditionally, so 0.16.0 could fail while importing `google_ads_mcp.tools` and therefore fail during `build_server()` startup.
- Fixed recursive MCC/customer isolation for protobuf `map`/`Struct` values. The v0.16.0 walker treated protobuf maps as ordinary repeated fields and iterated map keys rather than nested values, which could miss customer-scoped resource names inside map-backed messages.
- Added explicit protobuf-list regression coverage so nested cross-customer resource references remain blocked.

### Validation
- `tests/test_client_helpers.py` already exercises the `micros()` / `from_micros()` round trip and now has its missing implementation restored.
- `tests/test_recursive_customer_isolation.py` covers same-customer nested creates, cross-customer protobuf-map values, protobuf-list values, and root customer resource references.
- 0.16.1 exists specifically because 0.16.0 was observed in a real local dependency environment to fail test collection/startup. Do not treat the 0.16.0 package/version as the deployment target.
- A subsequent clean local run successfully started the server and collected 231 tests, then exposed stale test doubles and duplicate public tool registration warnings. Those are addressed by 0.16.2.

See `docs/RELEASE_0.16.1.md`.

## 0.16.0 — 2026-08-20

### Added
- Audited Google Ads API v25 service coverage contract in `docs/V25_SERVICE_COVERAGE.md`, with zero stable-public services left without deliberate MCP treatment.
- Durable pending confirmations across process restart using encrypted invocation arguments in SQLite.
- Explicit deployment key support through `GOOGLE_ADS_MCP_PENDING_ENCRYPTION_KEY`.
- Central reporting-only/emergency-freeze mode through `GOOGLE_ADS_MCP_READ_ONLY=true`; reads/audit inspection remain available while new proposals and pending confirmations are blocked.
- Full manager/client link lifecycle with narrow, allowlist-aware cross-account linking support.
- ExperimentArm lifecycle and atomic two-arm `traffic_split` updates preserving Google's total=100 invariant.
- Compatibility alias `update_experiment_traffic_split` for the preferred `update_experiment_arm_traffic_splits` tool.
- Expanded Performance Max signal/listing support, including RETAIL Product Tags and WEBPAGE root filters.
- ProductLink / ProductLinkInvitation completion and stricter referenced-customer isolation.
- AssetGenerationService wrappers for Google closed-beta/allowlisted text and image generation.
- Static write-gate regression guard that detects public MCP tools reaching write-looking RPCs before `SafetyLayer.propose()`.
- Additional v25 specialist/platform surfaces documented in the coverage matrix.
- SKAdNetwork schema visibility plus an explicit capability tool describing the deliberately non-writable public-contract boundary.

### Fixed
- Recursive customer isolation now inspects nested customer-scoped references in CREATE, UPDATE and REMOVE operations.
- MCC hierarchy/link reads now honor the deployment allowlist at row level for `customer_client`, `customer_client_link`, and `customer_manager_link`, including raw GAQL; unfilterable hierarchy queries fail closed.
- Legitimate `CustomerClientLinkService` CREATE no longer gets incorrectly blocked by the recursive guard when both accounts are in scope.
- `CustomerManagerLinkService` now resolves to the real v25 singular `mutate_customer_manager_link` RPC while retaining the repeated `operations[]` request field.
- Durable replay now stores/replays the **public MCP tool name** separately from internal safety aliases, fixing restart confirmation for shared risk helpers.
- ProductLinkInvitation no longer permits an indirectly referenced Google Ads customer to bypass the deployment allowlist.
- Performance Max listing-filter validation now supports `retail_filter_bundle`, explicit “everything else” nodes and multiple WEBPAGE roots where v25 permits them.
- v25 compatibility cleanup for Reach Planner, Creator Insights, unified goal services and current generated enums/contracts.
- Audience metadata updates now enforce Google's CUSTOMER/ASSET_GROUP naming rules, including safe promotion requirements.
- Removed two generic SKAdNetwork schema writers that attempted to write fields documented as output-only in the public v25 resource contract; regression guards prevent their return.
- Delivery-changing tools that could previously fall through as `standard` are now conservatively classified as `spend`, including keyword creation/match changes/negatives, location/language/placement targeting, audience/topic attachment, conversion-biddability changes, live asset create+attach helpers, Call Ad compatibility attachment, and edits to existing RSAs.
- Pending `confirm`/`cancel` MCP operations are serialized within one server process so simultaneous requests cannot double-confirm the same action or cancel while confirmation is entering execution.

### Safety
- Existing `standard`, `spend`, `destructive` and `sensitive` risk classes remain in force.
- High-risk classes remain confirmation-gated unless separately opted into auto-approve.
- `GOOGLE_ADS_MCP_READ_ONLY=true` is a central fail-closed kill switch and also blocks confirmation of pending actions created before read-only was enabled.
- The delivery-risk classification is effect-based: resources/ads explicitly prepared `PAUSED` may remain `standard`, while helpers that create **and attach** creative to live delivery are `spend`.
- The new delivery-risk classifications only change unattended behavior for deployments that explicitly enabled global standard auto-approve; `GOOGLE_ADS_MCP_AUTO_APPROVE=false` behavior is unchanged.
- Pending invocation arguments required for restart replay are encrypted at rest.
- Missing/corrupt pending encryption state fails closed: no Google Ads mutation is attempted.
- MCC/account-link exceptions are deliberately per-call and remain constrained by the deployment allowlist.
- One server process should own one pending-action database. Do not share one `audit.db` between multiple simultaneously running MCP processes unless an external single-writer/claim mechanism is added.
- Reach Plan, Incentives and other Google-controlled surfaces are documented as access-controlled rather than being mistaken for universally available capabilities.

### Documentation
- Rebuilt `docs/TOOLS.md` as a living v0.16 operator index instead of a monolithic historical manual.
- Updated README, SETUP, SAFETY, FAQ, EXAMPLES and `.env.example` for v0.16 deployment behavior.
- Corrected `docs/V25_SERVICE_COVERAGE.md` and release notes to distinguish integrated, access-controlled, specialized and non-public services.
- GitHub Actions workflow remains removed; validation is intentionally local/manual for this repository.

### Validation note
- Source and contracts were reviewed against Google Ads API v25 and regression tests were added for customer isolation, all MCC link-read surfaces, durable alias replay, read-only blocking, confirm/cancel serialization, direct-write safety gating, atomic experiment splitting, Asset Generation registration/contracts, delivery-risk classification, CustomerManagerLink method resolution, Audience scope naming, and the SKAdNetwork no-fake-writer boundary.
- The final completion environment did not have a runnable Google Ads Python/FastMCP/Ruff dependency stack or live Google Ads credentials and outbound package installation was unavailable. Per repository policy GitHub Actions was not used, so the full local `pytest`/Ruff/smoke suite and live-account E2E remain deployment validation steps rather than claims of this completion run.

See `docs/RELEASE_0.16.0.md`.

## 0.15.0 — 2026-08-18

### Added
- Controlled Batch Jobs using reviewed manifests rather than arbitrary raw protobuf mutations.
- Smart Bidding seasonality adjustments and conversion-data exclusions.
- Search keyword recommendation generation.
- Row-level asynchronous Batch Job result inspection.

### Safety
- Batch submission classified sensitive.
- Smart Bidding event creation classified spend-risk; removals destructive.
- Batch partial-success semantics made explicit.

See `docs/RELEASE_0.15.0.md`.

## 0.14.0 — 2026-08-18

### Added
- Customer labels and campaign/ad-group label relationships.
- Shared negative keyword lists.
- Account users, roles and invitations.
- Billing/invoice reads.
- Conversion retractions/restatements.

See `docs/RELEASE_0.14.0.md`.

## 0.13.0 — 2026-08-18

### Added
- Deployment customer allowlists and strict allowlist mode.
- Central `standard` / `spend` / `destructive` / `sensitive` risk classification.
- Separate high-risk auto-approve controls.

See `docs/RELEASE_0.13.0.md`.

## 0.12.1 — 2026-08-18

### Fixed
- Legacy VIDEO mutation path fails safe instead of attempting unsupported writes.
- Added supported Demand Gen video workflow.

See `docs/RELEASE_0.12.1.md`.

## 0.12.0 — 2026-08-18

### Changed
- Moved core server contracts to Google Ads API v25.
- Hardened campaigns, ads, assets, PMax, conversions, targeting, atomic writes, SSRF protection and confirmation retry behavior.

See `docs/RELEASE_0.12.0.md`.

## 0.11.0 and earlier

Earlier incremental coverage releases remain available in repository history. They built the foundations now consolidated by the v0.12-v0.16 production series.
