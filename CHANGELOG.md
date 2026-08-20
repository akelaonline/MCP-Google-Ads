# Changelog

Google Ads MCP follows Semantic Versioning. Detailed release notes for production releases live in `docs/RELEASE_X.Y.Z.md`.

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
