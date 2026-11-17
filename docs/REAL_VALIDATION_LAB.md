# Real validation lab

The runbook below describes the isolated read-only lab. Initial preparation was
followed by live Ads/MCC reads and a ChatGPT tunnel connection. See the dated
[evidence and limits](COMMUNITY_UPDATE_2026-11-17.md); a successful read does not
certify live writes.

## Isolation rules

* Lab home: `~/.google_ads_mcp_lab/` with its own `lab.env`, audit DB and key.
  Never point it at production config/DB/key paths. Credential provenance and
  account access must be documented; reusing a consented Ads identity does not
  make the configurations or pending storage shared.
* `GOOGLE_ADS_MCP_READ_ONLY=true`, auto-approvals OFF, explicit allowlists
  (`GOOGLE_ADS_MCP_ALLOWED_CUSTOMER_IDS`, `GOOGLE_ADS_MCP_ALLOWED_MERCHANT_IDS`).
* Authenticated calls need specific written authorization from the owner.
  A read-only approval does **not** authorize write tests.
* Tokenless runbook: `docs/TOKENLESS_AUTH_VALIDATION.md`.

## Preflight (no secrets, no network)

```bash
python scripts/lab_preflight.py [--lab-dir ~/.google_ads_mcp_lab] [--env-file <lab>/lab.env] [--repo-root <checkout>]
```

The env file defaults to `<lab>/lab.env` (the name used by the lab mission); pass
`--env-file` for any other name — a lone `.env` is **not** picked up. Exit code 0
only if every check passes. It prints variable names and PASS/FAIL, never values,
`--repo-root` selects the checkout inspected for a stray `.env` (default: the script's own; the preflight tests use a pristine fake checkout so an Owner `.env` never affects them). It makes no network call, does not import the server and never reads the production
installation. Checks:

* **Parsing**: python-dotenv (the server's parser: `export`, quotes, inline
  comments) and the server's boolean rule (`1/true/yes/on`, case-insensitive,
  trimmed). `GOOGLE_ADS_MCP_READ_ONLY` must be true; `AUTO_APPROVE`, `_SPEND`,
  `_DESTRUCTIVE`, `_SENSITIVE` must be off (so `1`, `yes`, `on`, `TRUE` fail).
* **Strict allowlist**: `GOOGLE_ADS_MCP_REQUIRE_CUSTOMER_ALLOWLIST` true, a
  non-empty `GOOGLE_ADS_MCP_ALLOWED_CUSTOMER_IDS` or `GOOGLE_ADS_MCP_ALLOWED_MANAGER_IDS` of valid 10-digit IDs; manager/login membership is checked; Merchant
  IDs valid positive numbers (and non-empty if the Merchant requirement is on).
* **Paths**: resolved, absolute, no symlink anywhere in the path, and *real*
  membership in the lab directory (not a name match) for the env file, the audit
  DB and its `.pending.key`; the DB path must be absolute (the server redirects
  relative paths to the production directory); the lab must be outside the
  production data directory and the repository.
* **Privacy**: lab directory and env file owned by you and without group/other
  access (`chmod 700` / `chmod 600`).
* **Shell overrides**: the process environment wins over the dotenv file at
  runtime, so a differing `GOOGLE_ADS_MCP_*` value exported in the shell fails.

Not checked (needs you): that the lab credentials differ from production ones —
the preflight deliberately never opens production files.

## Offline battery isolation

`scripts/validate_local.py`, `tests/conftest.py`, the smoke test and the lifecycle
test all run with an isolated environment (`scripts/validation_isolation.py`):
Google/Cloud variables dropped, `HOME` and XDG dirs in a throw-away directory, an
empty dotenv forced through `GOOGLE_ADS_MCP_ENV_FILE`, and a temporary audit DB
and key. Operator DBs, dotenv files and `<cwd>/.env` are never opened.
`tests/test_validation_isolation.py` proves it with decoy config and DBs, including a full `validate_local.py` run inside a copy of the checkout whose root holds a decoy `.env`.

## Status per capability

| Capability | Status | Blocker |
|---|---|---|
| Google Ads read-only | LIVE READS VERIFIED | MCC hierarchy, two clients and scope/exclusion checks; see dated evidence |
| Google Ads writes / validate_only against API | NOT RUN | Needs explicit write authorization on a test account |
| Merchant API v1 read-only | NOT RUN | Needs developer registration of the Cloud project (owner) + Merchant allowlist |
| Merchant writes | NOT RUN | Same + explicit write authorization |
| GTM / GA4 | SEPARATE DRAFT | [Status and remaining gates](MEASUREMENT_STATUS.md) |
