# v0.15.0 — Batch & Smart Bidding Operations

v0.15.0 adds agency-scale asynchronous mutation support and Smart Bidding event controls while retaining the v0.13/v0.14 customer-isolation and risk-policy layers.

## Batch Jobs

Adds three Batch Job tools:

- `list_batch_jobs` — read recent jobs and execution metadata.
- `submit_batch_job` — submit a controlled mixed-resource manifest.
- `get_batch_job_results` — read paginated row-level results after execution.

The MCP intentionally does **not** expose arbitrary raw `MutateOperation` protobufs. `submit_batch_job` accepts a reviewed DSL for common agency operations:

- campaign status;
- ad-group status;
- ad status;
- keyword status/remove;
- campaign-budget amount;
- keyword CPC bid;
- campaign negative keyword creation.

A single MCP submission is capped at 10,000 operations and a 20 MiB JSON manifest. The entire manifest is validated and placed into the SafetyLayer preview/audit record **before any BatchJob is created, populated, or run**.

Batch submissions are classified `sensitive`, so global auto-approve alone does not execute them in the production context.

### Partial-success behavior

Google Batch Jobs are asynchronous and can partially succeed. A successful row is not rolled back because another row fails. Operators must inspect `get_batch_job_results` after completion. This semantic difference from the MCP's normal atomic write paths is deliberate and documented rather than hidden.

## Smart Bidding controls

Adds:

- `list_seasonality_adjustments`
- `create_seasonality_adjustment`
- `remove_seasonality_adjustment`
- `list_data_exclusions`
- `create_data_exclusion`
- `remove_data_exclusion`

Controls support CHANNEL or CAMPAIGN scope, SEARCH/DISPLAY/SHOPPING channels, optional DESKTOP/MOBILE/TABLET device filters, up to 2,000 campaign IDs for campaign-scoped events, and intervals of at most 14 days.

Seasonality adjustments validate `conversion_rate_modifier` from 0.1 through 10.0. Create operations are classified `spend`; removal operations are classified `destructive`.

Date-time strings are sent to Google unchanged and are interpreted in the Google Ads account time zone. Internal parsing only makes interval validation deterministic.

## Recommendation generation

Adds `generate_keyword_recommendations` using `RecommendationService.GenerateRecommendations` for Search `KEYWORD` recommendations with `seed_info` keyword seeds and an optional URL seed.

The MCP intentionally starts with this documented recommendation contract rather than exposing a generic generator that could omit type-specific required inputs.

## Safety

- v0.13 customer allowlists apply to all new tools.
- Batch submission is `sensitive`.
- Smart Bidding event creation is `spend`.
- Smart Bidding event removal is `destructive`.
- Read-only Batch/Smart Bidding/recommendation-generation tools do not mutate accounts.
- Batch manifests are auditable before submission.

## Google Ads API compatibility

v0.15.0 continues to target Google Ads API v25 through the tested Google Ads Python 31.x client line. New contract tests instantiate real v25 proto-plus messages for Batch Jobs, Smart Bidding controls, and recommendation generation.

## Upgrade compatibility

v0.15.0 is additive. Existing v0.14 tool signatures and production-policy environment variables are unchanged.

See `docs/BATCH_SMART_BIDDING.md` for operational examples and cautions.
