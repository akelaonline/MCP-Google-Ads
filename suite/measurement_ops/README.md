# MKT Measurement Ops

Measurement Ops is the orchestration layer for the Google Marketing suite.

It lives beside the Google Ads MCP instead of inside its runtime. The product is
one suite, while Ads, GTM, GA4, web audit and site deployment remain isolated
providers so one provider cannot destabilize the others.

## Current v0.1 architecture

```text
LLM / MCP client
       |
MKT Measurement Ops MCP
       |
+------+------+------+------+------+
| Ads  | GTM  | GA4  | Audit| Site |
+------+------+------+------+------+
                           |
                  +--------+--------+
                  |                 |
              WordPress            Astro
              Bridge               Git plan
```

The existing Google Ads MCP remains a separate provider. Measurement Ops does
not modify its runtime or safety model.

## Implemented now

### Durable Site Registry

A site record maps:

- domain and platform;
- deployment mode;
- GTM account/container;
- GA4 property;
- Google Ads customer;
- Astro/Git repository or WordPress endpoint.

The registry is stored in SQLite using `MEASUREMENT_OPS_DB`. It stores routing
metadata only, never Google/Git/WordPress credentials.

### Durable measurement jobs

The workflow is persisted in the same SQLite database:

```text
CREATED
  -> AUDITED
  -> PLANNED
  -> PREPARED
  -> PREVIEW_VERIFIED
  -> APPROVED
  -> PUBLISHED
  -> PRODUCTION_VERIFIED
```

A restart must not lose either the site record or the measurement job.

### Web Audit

The Playwright auditor is read-only toward the audited website. It currently
detects:

- forms;
- WhatsApp, phone and email links;
- file downloads;
- existing GTM / GA4 / Google Ads IDs;
- common form providers including Contact Form 7, Gravity Forms, WPForms,
  Elementor, HubSpot, Typeform, Marketo and Calendly.

SSRF controls reject private/loopback/link-local/special IPs and are applied to
the initial URL and browser subrequests.

### GTM API

Read-only coverage currently includes accounts, containers, workspaces, tags,
triggers, variables, built-in variables, workspace status and live version.

Capabilities are separated:

- `GTM_ENABLE_PREVIEW` — quick preview only;
- `GTM_ENABLE_WRITES` — workspace/entity mutations;
- `GTM_ENABLE_PUBLISH` — production publish.

All default to false. Production publish additionally requires `confirm=true`.

The public MCP surface does **not** expose raw create-tag/create-trigger JSON
tools and does not expose a low-level publish tool. Standard measurement uses
typed builders and an idempotent installer.

Implemented typed installs:

- base Google tag;
- `whatsapp_click`;
- `phone_click`;
- `email_click`;
- `file_download`;
- native form-submit tracking;
- existing dataLayer custom events;
- deterministic listener recipes for CF7, Gravity Forms, WPForms, Elementor,
  HubSpot, Typeform and Calendly.

Re-running an installer reuses its canonical resources. Same-name resources
with incompatible configuration fail as drift rather than being overwritten.

### GA4

The Admin API provider resolves a registered property's web data stream and
Measurement ID from the site's domain. Measurement IDs therefore do not need to
be entered manually during normal installation.

The Data API provider checks GA4 Realtime `eventName` / `eventCount` after
publish. A job is not complete until production verification passes.

### WordPress

`wordpress/mkt-measurement-bridge/` is a small WordPress 6.9+ companion
plugin using the WordPress Abilities API.

It exposes controlled abilities for reading/configuring the bridge-managed GTM
container, requires `manage_options` and `confirm=true` for changes, and does
not expose arbitrary PHP/theme editing.

It inserts GTM independently from the active theme.

### Astro

The Astro adapter emits a deterministic installation plan:

- GTM head component;
- GTM body/noscript component;
- typed dataLayer helper;
- `PUBLIC_GTM_ID` environment contract;
- build and duplicate-install verification requirements.

Actual repository mutation/deploy remains a separate provider step.

## Safety invariants

1. Audit before changing anything.
2. Prefer GTM workspaces and Git branches over direct production edits.
3. Never store provider credentials in the Site Registry or workflow evidence.
4. Raw arbitrary GTM entity mutation is not part of the public MCP surface.
5. GTM publish must go through a managed measurement job.
6. A published version ID must be one created and recorded by that same job.
7. Publish requires preview verification, explicit job approval, the publish
   environment gate and `confirm=true`.
8. Production success means runtime verification, not merely API success.

## Local validation

This PR must stay draft until this passes from a networked development machine:

```bash
cd suite/measurement_ops
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e ".[dev,web]"
python -m playwright install chromium
python scripts/validate_local.py
```

The current authoring runtime can write through the GitHub connector but cannot
resolve `github.com` from its shell, so no claim of a green local suite is made
from that environment.

## POC acceptance

The architecture is accepted only after two real end-to-end pilots:

1. one WordPress site;
2. one Astro site.

Each pilot must demonstrate:

```text
register site
  -> audit
  -> measurement plan
  -> isolated GTM workspace
  -> typed tracking install
  -> site-side change if required
  -> quick preview / conflict check
  -> preview verification
  -> saved GTM version
  -> explicit approval
  -> deploy / publish
  -> production browser verification
  -> GA4 Realtime verification
```

No pilot is complete at "tag created".
