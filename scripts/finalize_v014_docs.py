from pathlib import Path


readme = Path("README.md")
r = readme.read_text()
r = r.replace("version-0.13.0", "version-0.14.0", 1)
r = r.replace(
    "[Quick start](#quick-start) · [Capabilities](#capabilities) · [Safety](#safety-by-default) · [v0.13 production policy](#v013-production-policy) · [Documentation](#documentation)",
    "[Quick start](#quick-start) · [Capabilities](#capabilities) · [Safety](#safety-by-default) · [v0.14 agency coverage](#v014-agency-coverage) · [Documentation](#documentation)",
    1,
)
if "## v0.14 agency coverage" not in r:
    section = '''## v0.14 agency coverage

v0.14 expands the MCP into common agency administration workflows while keeping the v0.13 customer-isolation and risk policy underneath every operation.

- Native customer labels plus campaign/ad-group label relationships.
- Native shared negative keyword lists (`SharedSet` + `SharedCriterion` + `CampaignSharedSet`).
- Account users and invitations: list, invite, change roles, remove access, revoke invitations.
- Read-only billing setup and invoice retrieval.
- Conversion retractions and value restatements with explicit partial-failure parsing.
- Real Google Ads API v25 contract tests for every new protobuf-heavy write path.

See [`docs/AGENCY_TOOLS.md`](docs/AGENCY_TOOLS.md) for signatures and operational notes.

'''
    r = r.replace("## v0.13 production policy\n", section + "## v0.13 production policy\n", 1)
r = r.replace(
    "| **Accounts & MCC** | Accessible customers, account hierarchy, summaries, create client accounts, manager-link acceptance |",
    "| **Accounts & MCC** | Accessible customers, account hierarchy, summaries, create client accounts, manager-link acceptance, users, roles and invitations |",
    1,
)
r = r.replace(
    "| **Keywords** | Add, bid updates, match-type recreation, pause/enable/remove, campaign/ad-group negatives, bulk operations |",
    "| **Keywords** | Add, bid updates, match-type recreation, pause/enable/remove, campaign/ad-group negatives, native shared negative lists, bulk operations |",
    1,
)
r = r.replace(
    "| **Conversions** | List/create actions, offline click uploads, enhanced conversions, primary/secondary behavior, value rules |",
    "| **Conversions** | List/create actions, offline click uploads, enhanced conversions, retractions/restatements, primary/secondary behavior, value rules |",
    1,
)
needle = "| **Experiments** | System-managed experiment setup, arm inspection, promotion and ending |\n"
if "| **Labels** |" not in r:
    r = r.replace(
        needle,
        needle
        + "| **Labels** | Create/update/remove labels; attach/detach on campaigns and ad groups |\n"
        + "| **Billing** | Billing setup visibility and invoice retrieval by month/year |\n",
        1,
    )
if "[`docs/AGENCY_TOOLS.md`]" not in r:
    r = r.replace(
        "| [`docs/TOOLS.md`](docs/TOOLS.md) | Tool signatures and operational notes |",
        "| [`docs/TOOLS.md`](docs/TOOLS.md) | Core tool signatures and operational notes |\n"
        "| [`docs/AGENCY_TOOLS.md`](docs/AGENCY_TOOLS.md) | v0.14 labels, shared negatives, access, billing and conversion adjustments |",
        1,
    )
readme.write_text(r)


tools = Path("docs/TOOLS.md")
t = tools.read_text()
t = t.replace(
    "# Tool reference — v0.12 / Google Ads API v25",
    "# Tool reference — v0.14 / Google Ads API v25",
    1,
)
t = t.replace(
    "`GOOGLE_ADS_MCP_AUTO_APPROVE=true` is an explicit opt-in that executes writes immediately.",
    "`GOOGLE_ADS_MCP_AUTO_APPROVE=true` auto-executes standard-risk writes in the production context; spend, destructive, and sensitive actions remain separately gated. See `docs/SAFETY.md`.",
    1,
)
if "AGENCY_TOOLS.md" not in t[:1200]:
    t = t.replace(
        "All normal write tools go through the shared safety layer.\n",
        "All normal write tools go through the shared safety layer. v0.14 agency-management additions are also indexed in [`AGENCY_TOOLS.md`](AGENCY_TOOLS.md).\n",
        1,
    )
tools.write_text(t)


changelog = Path("CHANGELOG.md")
c = changelog.read_text()
entry = '''## 0.14.0 — 2026-08-18

### Added
- Native customer labels with campaign/ad-group label relationships.
- Native shared negative keyword lists using `SharedSet`, `SharedCriterion`, and `CampaignSharedSet`.
- Account user/invitation administration with ADMIN, STANDARD, READ_ONLY, and EMAIL_ONLY roles.
- Read-only billing setup and monthly invoice retrieval.
- Conversion retractions and value restatements through `ConversionAdjustmentUploadService`.
- `docs/AGENCY_TOOLS.md` and real-v25 agency contract tests.

### Safety
- Account-access writes are classified sensitive/destructive by the v0.13 policy layer.
- Conversion adjustments are classified sensitive.
- Required conversion-adjustment `partial_failure=true` responses are explicitly parsed; row-level failures raise `GoogleAdsMcpError` instead of returning false success.
- Existing customer allowlists apply to all new scoped reads and writes.

### Compatibility
- Adds exact v25 irregular/singular mutate RPC mappings for shared criteria and customer user-access services.
- Existing v0.13 tool signatures and deployment policy remain unchanged.

See `docs/RELEASE_0.14.0.md` for full release notes.

'''
if "## 0.14.0 — 2026-08-18" not in c:
    marker = "# Changelog\n\n"
    if not c.startswith(marker):
        raise SystemExit("Unexpected CHANGELOG header")
    c = marker + entry + c[len(marker):]
changelog.write_text(c)
