# Changelog

Google Ads MCP follows Semantic Versioning. Detailed release notes for production releases live in `docs/RELEASE_X.Y.Z.md`.

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
