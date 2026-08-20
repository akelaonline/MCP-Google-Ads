# Google Ads MCP 0.16.1

**Release date:** 2026-08-20  
**Google Ads API:** v25  
**Release type:** production hotfix for 0.16.0

0.16.1 is a corrective patch release. It does not add new Google Ads surface area; it fixes two regressions discovered when 0.16.0 was installed in a normal local Python environment and the full test suite was collected.

## Why 0.16.1 exists

0.16.0 should not be used as the deployment target.

A real local install found two blockers:

1. `src/google_ads_mcp/tools/reporting.py` imported `from_micros` from `client.py`, but the helper was missing. Because the tools package is imported when `build_server()` registers all MCP modules, this could prevent the server from starting and caused broad pytest collection failures.
2. The recursive cross-customer mutation guard did not descend correctly through protobuf map-backed values such as `google.protobuf.Struct`. Protobuf map iteration yields keys, so the previous walker could miss a nested resource name carried in a map value.

Both issues are fixed in 0.16.1.

## Fixes

### Reporting/server startup

`client.py` again exposes both currency helpers:

```python
micros(25.50) -> 25_500_000
from_micros(25_500_000) -> 25.5
```

`tests/test_client_helpers.py` already asserts this round trip. Restoring the helper removes the import failure that prevented `google_ads_mcp.tools` from loading cleanly.

### Recursive MCC/customer isolation

The resource-name walker now understands:

- proto-plus/protobuf messages;
- protobuf map fields;
- `google.protobuf.Struct` / `Value` nesting;
- repeated message fields;
- generic mappings;
- list/tuple/set/frozenset containers;
- repeated string values.

For protobuf maps, the walker explicitly traverses map **values**, not keys.

The guard therefore blocks cross-customer references such as:

```text
request customer: 1234567890
nested resource:   customers/9999999999/assets/2
```

before a Google Ads mutate RPC can execute.

## Regression coverage

0.16.1 includes or relies on tests for:

- micros -> currency round trip;
- same-customer nested create references;
- cross-customer resource inside a protobuf map/Struct;
- cross-customer resource inside a protobuf list;
- root `customers/<id>` references.

These are in:

- `tests/test_client_helpers.py`
- `tests/test_recursive_customer_isolation.py`

## Upgrade target

Update from GitHub `main`, then verify the local package reports `0.16.1`:

```bash
cd /path/to/MCP-Google-Ads
git fetch origin
git pull --ff-only origin main
source .venv/bin/activate
python -m pip install -e ".[dev]"
python -c "import google_ads_mcp; print(google_ads_mcp.__version__)"
```

Expected:

```text
0.16.1
```

Do not overwrite the existing `.env`, audit DB, or pending-action encryption key during an update.

## Required validation before production replacement

Run against the exact checked-out commit:

```bash
python scripts/smoke_test.py
ruff check src tests scripts
pytest -q
```

Also verify the real server build path:

```bash
python - <<'PY'
from google_ads_mcp.server import build_server
server = build_server()
print("OK build_server", server)
PY
```

If the full suite reveals additional failures, keep the currently running production MCP in place and fix forward from 0.16.1 rather than downgrading safety protections.

After the local suite is green, continue with `docs/VALIDATION_CHECKLIST.md` for read-only, MCC isolation, propose/confirm, durable restart replay, cross-customer blocking, and live E2E validation.

## Compatibility

0.16.1 is intended to be API-compatible with 0.16.0. The changes are limited to:

- restoring a missing public internal helper used by reporting;
- correcting recursive resource-name inspection;
- adding regression coverage;
- patch-version/documentation updates.

No Google Ads tool is intentionally removed by this patch.
