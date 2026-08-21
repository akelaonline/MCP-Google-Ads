# Google Ads MCP 0.16.3

**Release date:** 2026-08-21  
**Google Ads API:** v25  
**Release type:** corrective validation patch for 0.16.2 — first fully green local gate in the 0.16.x line

0.16.3 closes out the local validation gate that 0.16.2 opened. A clean local checkout of 0.16.2 built the server successfully (smoke green, zero duplicate-tool warnings) but still reported 3 pytest failures and 22 Ruff findings. 0.16.3 resolves all of them without weakening any safety or isolation behavior.

## Why 0.16.3 exists

0.16.2 fixed the two release-blocking issues from 0.16.1 (stale test-client contracts, ambiguous duplicate tool registration) and added smoke coverage for canonical tool ownership. A subsequent clean local run of `scripts/validate_local.py` against 0.16.2 exposed two remaining classes of problem:

1. Ruff reported 22 findings across `src/` and `tests/` — the local validation gate had never actually reached a Ruff pass before, so this was the first time the full lint surface had been checked in one run.
2. 3 pytest failures remained after the fixture synchronization in 0.16.2: a missing `ConsentStatusEnum` on the shared fake enums object, a stale error-message regex, a stale fake service signature, and a stale expectation about `proto.Message.to_dict()`'s default output shape.

## Ruff: 0 errors

All 22 findings from the 0.16.2 checkout are resolved. Roughly half were mechanical (`ruff check --fix`: import sorting, `Callable` moved to `collections.abc`, redundant `getattr()`, dict-membership-then-index simplified to `.get()`, nested `if` statements combined, unused `noqa: N802` directives removed, `validate_local.py` marked executable).

The remaining findings needed a judgment call rather than a blind fix, and were resolved as follows:

- **Two `except Exception` handlers narrowed to the specific exceptions each call site can raise**, instead of silencing the Ruff warning with a blanket `noqa`. `AuditLog`'s pending-action decrypt path now catches `(InvalidToken, json.JSONDecodeError, UnicodeDecodeError)` — the three ways a corrupt/missing key or corrupt payload actually fail — and still fails closed exactly as before. `client.py`'s protobuf field-walker, which backs the recursive MCC/customer-isolation guard, now catches `(ValueError, TypeError)` from `ListFields()` instead of masking any unrelated bug as "no scoped resources found."
- **One `ValueError` changed to `TypeError`** in `asset_generation_optional._generate()` for a wrong-type (not wrong-value) input, matching the convention already used by `batch_jobs.py`, `bulk.py`, and `keywords.py` elsewhere in this codebase.
- **Two `datetime.strptime()` calls left as naive datetimes on purpose**, with an explanatory `# noqa: DTZ007` rather than a forced (and incorrect) UTC-aware conversion. Both `billing.py` and `experiments.py` use `strptime()` only to validate that a string matches `YYYY-MM-DD` (or `YYYY-MM-DD HH:MM:SS`) in the Google Ads customer's own local calendar — there is no real-time clock semantics to make timezone-aware.
- **One RFC 3339 parse simplified** in `data_manager.py` to rely on `datetime.fromisoformat()`'s native `Z`-suffix support (available since Python 3.11, which is this project's floor) instead of a manual `"Z" -> "+00:00"` string replace.
- **A Ruff auto-fix that collapsed an `if/elif` into a single-line `A or B and C` condition was reformatted**, not reverted. The collapsed form in `client.py`'s mutation-isolation gate — the check that decides whether a write is allowed to touch more than one Google Ads customer — was verified boolean-equivalent to the original `if/elif` by explicit truth-table check, but relied on unstated `and`/`or` precedence in the single most security-sensitive branch of the codebase. It is now an explicitly named, parenthesized `is_scoped_manager_link_create` boolean.

None of the above change what the server accepts, rejects, or isolates. They are readability and specificity fixes on top of previously-correct behavior.

## Pytest: 232/232 passed

- Added `ConsentStatusEnum` (`UNSPECIFIED`/`UNKNOWN`/`GRANTED`/`DENIED`) to `tests/conftest.py`'s shared `FakeEnums`, matching the real v25 `ConsentStatusEnum.ConsentStatus` contract. This was the root cause of the two remaining `test_audiences_tools.py` failures: production code in `audiences.py` already called `client.enums.ConsentStatusEnum.<VALUE>` for Customer Match consent handling, but the fake client used by tests had never defined it.
- `test_upload_customer_match_members_requires_at_least_one_field` now matches production's current, more specific error message ("No non-empty email or phone identifiers were supplied.") instead of a stale generic "at least one" substring.
- `test_upload_customer_match_members_hashes_pii_and_runs_job`'s fake `OfflineUserDataJobService.create_offline_user_data_job()` now accepts `enable_match_rate_range_preview`, a real v25 `CreateOfflineUserDataJobRequest` field that production already passes.
- `test_asset_generation_v25_contracts_are_registered_and_customer_scoped` now expects `{"generated_text": []}` / `{"generated_images": []}` rather than `{}`. `proto.Message.to_dict(response, preserving_proto_field_name=True)` — the same call convention used by every other tool in this codebase — includes empty repeated fields by default; verified against the real v25 `GenerateTextResponse`/`GenerateImagesResponse` message definitions. The test's expectation was wrong, not the production code.

In every case above, the fix direction (test vs. production code) was decided by checking which side matched the real v25 protobuf contract or the codebase's own established convention, not by loosening an assertion to make it pass.

## Validation status

`python scripts/validate_local.py` is green end-to-end against this commit:

```text
isolated smoke  -> SMOKE OK (50 tool modules, zero duplicate-tool warnings, canonical owners verified)
ruff check      -> All checks passed!
pytest -q       -> 232 passed
```

This is the first version in the 0.16.x line to satisfy all four locally-defined release gates simultaneously: full pytest pass, clean Ruff, clean smoke, and zero duplicate-tool-registration warnings.

Before replacing a running MCP, update a clean/local checkout and run:

```bash
git fetch origin
git pull --ff-only origin main
source .venv/bin/activate
python -m pip install -e ".[dev]"
git rev-parse HEAD
python -c "import google_ads_mcp; print(google_ads_mcp.__version__)"
python scripts/validate_local.py
```

Confirm the run ends with:

```text
LOCAL VALIDATION GREEN
validated version: 0.16.3
```

## What 0.16.3 does not cover

This release, like every 0.16.x patch before it, was validated with offline/mocked tests and the isolated smoke test only. No live Google Ads API credentials or real account were exercised. Live-account E2E — read-only mode, MCC read/write isolation, propose/cancel, propose/confirm, durable restart replay, legitimate MCC linking, and risk-classification boundaries against a real test account — remains a required separate step via `VALIDATION_CHECKLIST.md` before this replaces a production MCP.

## Compatibility

0.16.3 does not remove or change any Google Ads capability, tool signature, or safety behavior. It is a pure quality/hardening pass: lint cleanliness, exception specificity, one readability fix in the isolation gate, and test-fixture accuracy.
