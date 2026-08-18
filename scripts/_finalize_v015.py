from pathlib import Path


def replace_once(path: str, old: str, new: str) -> None:
    file = Path(path)
    text = file.read_text(encoding="utf-8")
    if old not in text:
        raise SystemExit(f"Expected text not found in {path}: {old[:80]!r}")
    file.write_text(text.replace(old, new, 1), encoding="utf-8")


# README version/navigation.
replace_once(
    "README.md",
    "version-0.14.0-informational.svg",
    "version-0.15.0-informational.svg",
)
replace_once(
    "README.md",
    "[v0.14 agency coverage](#v014-agency-coverage)",
    "[v0.15 batch & Smart Bidding](#v015-batch--smart-bidding-operations)",
)

v015_readme = """## v0.15 batch & Smart Bidding operations

v0.15 adds controlled agency-scale asynchronous writes and Smart Bidding event controls without weakening the v0.13/v0.14 production policy.

- **Batch Jobs:** submit a reviewed manifest of campaign/ad-group/ad/keyword status changes, budget changes, keyword bids and campaign negatives; then inspect asynchronous row-level results.
- Batch manifests are validated and confirmation-gated **before** Google creates or runs a job. Arbitrary raw protobuf mutations are intentionally not exposed.
- **Seasonality Adjustments:** create/list/remove short expected conversion-rate events for SEARCH, DISPLAY and SHOPPING.
- **Data Exclusions:** create/list/remove short measurement-incident windows that Smart Bidding should ignore.
- Smart Bidding event creation is spend-risk; removal is destructive. Batch submission is sensitive.
- **Recommendation generation:** generate fresh Search keyword recommendations from seed keywords and an optional URL without applying them.
- Real Google Ads API v25 contract tests cover all new protobuf-heavy paths.

Batch Jobs can partially succeed: successful rows are not rolled back when another row fails. Always inspect `get_batch_job_results` before treating a batch as completely successful.

See [`docs/BATCH_SMART_BIDDING.md`](docs/BATCH_SMART_BIDDING.md) and [`docs/RELEASE_0.15.0.md`](docs/RELEASE_0.15.0.md).

"""
replace_once(
    "README.md",
    "## v0.14 agency coverage\n",
    v015_readme + "## v0.14 agency coverage\n",
)
replace_once(
    "README.md",
    "| **Recommendations** | List active/dismissed recommendations, apply, dismiss |",
    "| **Recommendations** | List active/dismissed recommendations; generate Search keyword recommendations; apply/dismiss through safety policy |\n"
    "| **Batch operations** | Controlled asynchronous Batch Jobs with reviewed manifests, status/result inspection and row-level outcomes |\n"
    "| **Smart Bidding controls** | Seasonality adjustments and conversion-data exclusions with channel/campaign/device scoping |",
)

# Tool reference header and dedicated v0.15 index.
replace_once(
    "docs/TOOLS.md",
    "# Tool reference — v0.14 / Google Ads API v25",
    "# Tool reference — v0.15 / Google Ads API v25",
)
replace_once(
    "docs/TOOLS.md",
    "All normal write tools go through the shared safety layer. v0.14 agency-management additions are also indexed in [`AGENCY_TOOLS.md`](AGENCY_TOOLS.md).",
    "All normal write tools go through the shared safety layer. v0.14 agency-management additions are indexed in [`AGENCY_TOOLS.md`](AGENCY_TOOLS.md); v0.15 Batch/Smart Bidding operations are documented in [`BATCH_SMART_BIDDING.md`](BATCH_SMART_BIDDING.md).",
)

tools = Path("docs/TOOLS.md")
tools_text = tools.read_text(encoding="utf-8")
section = """

---

## Batch Jobs — v0.15

### `list_batch_jobs(customer_id, status_filter=None, limit=100)`
Read-only. Lists recent Batch Jobs. `status_filter` accepts `PENDING`, `RUNNING`, or `DONE`.

### `submit_batch_job(customer_id, operations)` `[write: sensitive]`
Validates and proposes one controlled mixed-resource Batch Job. The whole manifest is previewed/audited before Google creates the job. Supported kinds: `campaign_status`, `ad_group_status`, `ad_status`, `keyword_status`, `campaign_budget_amount`, `keyword_bid`, `add_campaign_negative_keyword`. Maximum 10,000 operations and 20 MiB JSON per MCP submission. Batch Jobs have partial-success semantics; confirm results afterward.

### `get_batch_job_results(customer_id, batch_job_resource_name, page_size=1000, page_token=None, return_mutable_resource=False)`
Read-only. Returns one result page for a Batch Job, including row-level errors/results exposed by Google.

## Smart Bidding controls — v0.15

### `list_seasonality_adjustments(customer_id, limit=100)`
Read-only.

### `create_seasonality_adjustment(customer_id, name, start_date_time, end_date_time, conversion_rate_modifier, scope="CHANNEL", advertising_channel_types=None, campaign_ids=None, devices=None, description=None)` `[write: spend]`
Creates a short expected conversion-rate event. Supports CHANNEL or CAMPAIGN scope, SEARCH/DISPLAY/SHOPPING, optional DESKTOP/MOBILE/TABLET, up to 2,000 campaigns, interval <=14 days, modifier 0.1–10.0.

### `remove_seasonality_adjustment(customer_id, adjustment_id)` `[write: destructive]`
Removes a seasonality adjustment.

### `list_data_exclusions(customer_id, limit=100)`
Read-only.

### `create_data_exclusion(customer_id, name, start_date_time, end_date_time, scope="CHANNEL", advertising_channel_types=None, campaign_ids=None, devices=None, description=None)` `[write: spend]`
Creates a conversion-data exclusion for a measurement incident. Same channel/campaign/device and interval limits as seasonality adjustments.

### `remove_data_exclusion(customer_id, data_exclusion_id)` `[write: destructive]`
Removes a data exclusion.

### `generate_keyword_recommendations(customer_id, seed_keywords, url_seed=None)`
Read-only. Calls `RecommendationService.GenerateRecommendations` for Search `KEYWORD` recommendations using 1–20 keyword seeds and an optional URL seed. Generation does not apply the recommendation.
"""
if "## Batch Jobs — v0.15" not in tools_text:
    tools.write_text(tools_text.rstrip() + section + "\n", encoding="utf-8")

# Changelog: prepend release only once.
changelog = Path("CHANGELOG.md")
changelog_text = changelog.read_text(encoding="utf-8")
entry = """## 0.15.0 — 2026-08-18

### Added
- Controlled Google Ads Batch Jobs with reviewed manifests, job listing and paginated result inspection.
- Seven supported batch operation kinds for common campaign/ad-group/ad/keyword/budget workflows without exposing arbitrary raw protobuf mutations.
- Smart Bidding seasonality adjustments: list/create/remove with channel/campaign/device scope.
- Smart Bidding data exclusions: list/create/remove for conversion-measurement incidents.
- Search keyword recommendation generation through `RecommendationService.GenerateRecommendations` with `seed_info`.
- `docs/BATCH_SMART_BIDDING.md` and real-v25 contract coverage for the new surfaces.

### Safety
- `submit_batch_job` is classified sensitive; the entire manifest is validated, previewed and audited before job creation/run.
- Smart Bidding event creation is spend-risk; removals are destructive.
- Existing v0.13 customer allowlists protect every new customer-scoped read/write.
- Batch partial-success semantics are explicit: successful rows are not silently described as rolled back when another row fails.

### Compatibility
- Existing v0.14 tool signatures and deployment-policy environment variables are unchanged.
- Continues to target Google Ads API v25 on the tested Google Ads Python 31.x client line.

See `docs/RELEASE_0.15.0.md` for release details.

"""
if "## 0.15.0 — 2026-08-18" not in changelog_text:
    if not changelog_text.startswith("# Changelog\n"):
        raise SystemExit("Unexpected CHANGELOG header")
    changelog.write_text(
        "# Changelog\n\n" + entry + changelog_text[len("# Changelog\n"):].lstrip("\n"),
        encoding="utf-8",
    )
