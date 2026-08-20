# Google Ads MCP 0.16.1

**Release date:** 2026-08-20  
**Google Ads API:** v25  
**Release type:** production hotfix for 0.16.0

0.16.1 is a corrective patch release. It does not add new Google Ads surface area; it fixes regressions discovered when 0.16.0 was installed in a normal local Python environment and the full test suite was collected.

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

`tests/test_client_helpers.py` and `tests/test_tool_package_imports.py` assert the helper/import path so a future rename cannot silently break `build_server()` collection again.

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

### Isolated smoke validation

`scripts/smoke_test.py` is now an offline startup/safety smoke rather than a loose registration check. It:

- uses a temporary SQLite audit database;
- forces `GOOGLE_ADS_MCP_READ_ONLY=true`;
- does not send Google Ads requests;
- imports every module in `ALL_MODULES`;
- verifies `micros` / `from_micros`;
- exercises same-customer and cross-customer nested protobuf `Struct` references;
- builds the real FastMCP server path.

The smoke does not write to the production installation's configured audit/pending database.

### One-command local validation

`scripts/validate_local.py` is the preferred non-E2E gate. It prints the exact Git SHA and dependency versions, then runs:

1. isolated smoke;
2. Ruff over `src`, `tests`, `scripts`;
3. the complete pytest suite.

A successful run ends with `LOCAL VALIDATION GREEN` plus the validated SHA and MCP version.

## Regression coverage

0.16.1 includes or relies on tests for:

- complete tool-package importability;
- `micros` -> currency round trip;
- same-customer nested create references;
- cross-customer resource inside a protobuf map/Struct;
- cross-customer resource inside a protobuf list;
- root `customers/<id>` references.

Primary regression files:

- `tests/test_client_helpers.py`
- `tests/test_tool_package_imports.py`
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

Preferred gate:

```bash
.venv/bin/python scripts/validate_local.py
```

Equivalent diagnostic commands:

```bash
.venv/bin/python scripts/smoke_test.py
.venv/bin/python -m ruff check src tests scripts
.venv/bin/python -m pytest -q
```

Do not replace the currently running MCP if this gate exits non-zero.

After the local suite is green, continue with `docs/VALIDATION_CHECKLIST.md` for read-only, MCC isolation, propose/confirm, durable restart replay, cross-customer blocking, and live E2E validation.

## Compatibility

0.16.1 is intended to remain tool/API-compatible with the v0.16 line. The changes are limited to startup/safety bug fixes, validation hardening, regression coverage, and patch-version/documentation updates.

No Google Ads tool is intentionally removed by this patch.
