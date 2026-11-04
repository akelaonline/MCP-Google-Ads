# Release 0.18.0 — Google Ads API v26 + tokenless auth

**Status:** release candidate — validated offline; pending authorized live read-only check.

## Highlights

- **Google Ads API v26.** `google-ads` Python client pinned to `>=34.0.0,<36.0.0`
  (validated on 35.0.0). `GOOGLE_ADS_API_VERSION = "v26"`. The library still
  ships v23–v25, so downgrade paths remain possible.
- **Tokenless auth.** `GOOGLE_ADS_DEVELOPER_TOKEN` is optional — Google sunset
  developer tokens on 2026-09-09 (header ignored server-side; access levels now
  live on the Google Cloud project). Legacy installs with a token keep working
  unchanged; `google-ads>=32` no longer requires the field.
- **Validation hygiene.** Ruff pinned (`ruff==0.17.3`); stale doc targets fixed;
  gate runs green on modern toolchains.

## v26 migration notes

- **YouTube uploads**: `YouTubeVideoUploadService.create` no longer accepts a
  `stream=` kwarg in v26 — it returns a `ResumableUploadSession`
  (`session.upload(stream, size=...)`). The tool signature-checks the stub so
  the same code path works on ≤v25 and v26. Proposal→confirm now also
  re-verifies the video file's (size, mtime_ns, inode) fingerprint so a swapped
  file is never uploaded after approval.
- **Video metadata updates**: `video_title` and `video_description` are
  immutable after creation (Google-documented). The public tool signature is
  unchanged, but supplying either field now raises a clear `ValueError` at
  proposal time instead of failing later against the API. Only
  `video_privacy` remains updatable.
- **New tool (463rd)**: `check_local_services_eligibility` — read-only v26
  `LocalServicesEligibilityService.CheckLocalServicesEligibility` RPC.
- **Not exposed yet**: `CustomerBudgetNetworkSettingService` (new v26,
  write-only `mutate_*` RPC) — deferred pending a use-case review.
- Contract tests now build real protobufs at the pinned API version instead of
  a hardcoded `v25`.

## Pending v26.1

The `google-ads` 35.x library ships only `v23`–`v26` directories; **no v26.1
endpoint exists yet**. Any v26.1 capabilities land when Google publishes them —
nothing in this release invents unsupported services.

## Validation

- `scripts/validate_local.py`: **LOCAL VALIDATION GREEN** on google-ads 35.0.0
  — smoke OK, ruff 0.17.3 clean, **382/382 pytest**.
- MCP stdio lifecycle: initialize → tools/list (**463 tools**) → ping → clean
  exit 0.
- Tokenless + legacy-token contracts: green on the upgraded SDK.
- New coverage: resumable YouTube upload execute() path (propose→confirm,
  stream closure, swapped-file rejection), immutable-field guard, v26
  eligibility RPC contract.

## Known limitations

- No live Google Ads calls certified yet — see
  `docs/TOKENLESS_AUTH_VALIDATION.md` for the authorized read-only runbook.
- `CustomerBudgetNetworkSettingService` exposure decision deferred.
- `pyproject.toml` still uses the deprecated `license` table form (setuptools
  warning; removal window ends 2027-02).
