# Google Ads MCP 0.16.2

**Release date:** 2026-08-20  
**Google Ads API:** v25  
**Release type:** corrective validation patch for 0.16.1

0.16.2 is the next deployment-validation target after a clean local clone of 0.16.1 successfully started the FastMCP server and collected 231 tests, but still reported 13 test failures and duplicate tool-registration warnings.

## Why 0.16.2 exists

The 0.16.1 runtime fixes were real: server startup was restored and recursive protobuf map/Struct customer isolation was repaired. The subsequent full local suite exposed two remaining release-quality problems:

1. several unit/contract test clients still implemented the pre-hardening client interface and therefore lacked `assert_customer_allowed()` and/or `assert_resource_name_customer()`;
2. five public MCP tool names had both a legacy implementation and a newer v25-complete implementation registered with FastMCP. FastMCP warned and overwrote by registration order instead of giving the public tool one deterministic owner.

0.16.2 addresses both classes before any production replacement is recommended.

## Test-fixture synchronization

Shared and real-protobuf test clients now model the same customer-scope contract used by the production client:

- normalize dashed customer IDs;
- reject invalid customer IDs;
- validate customer-scoped resource names against the request customer;
- reject cross-customer resource references in tests instead of silently accepting them.

The synchronization covers the shared `build_ctx()` fake and contract clients used by core v25, recommendations, conversions and agency-management tests. Recommendation fixtures that mixed customer `1234567890` with `customers/123/...` resource names were corrected to valid same-customer resources.

This is intentionally not a weakening of production checks to make tests pass. The test doubles were updated to match the production interface.

## Deterministic MCP tool ownership

The following public names had legacy and specialist implementations:

- `list_asset_group_signals`
- `add_asset_group_signal`
- `list_asset_group_listing_filters`
- `list_conversion_value_rules`
- `create_conversion_value_rule`

Their canonical owners are now explicit:

```text
PMax signal/listing tools -> google_ads_mcp.tools.pmax_signals_listing
ConversionValueRule tools -> google_ads_mcp.tools.remaining_core_services
```

The canonical PMax implementation supports the broader v25 signal/listing surface and customer isolation. The canonical ConversionValueRule implementation provides the full protobuf-JSON create/list/update/remove lifecycle.

Legacy definitions remain in their broader source modules temporarily for source-level compatibility/testing, but the FastMCP registration wrapper does not register them as public tools. There is therefore exactly one runtime owner for each public name.

Any *new, unexpected* duplicate public tool name now raises `RuntimeError` during server construction instead of being silently overwritten.

The replay registry is reset when a new FastMCP server instance is built in the same Python process, preventing false duplicate detection during repeated local server construction while preserving durable replay for the active instance.

## Smoke/validation hardening

The isolated smoke test now verifies canonical tool ownership after `build_server()` in addition to:

- complete tool-package import;
- `from_micros()` / `micros()` round trip;
- nested protobuf Struct/map/list MCC isolation;
- FastMCP construction in a temporary read-only runtime and temporary audit DB.

`python scripts/validate_local.py` remains the required one-command non-E2E validation gate and runs:

```text
isolated smoke -> Ruff -> full pytest
```

## Validation status

0.16.2 is a **re-test target**, not a claim that the suite has already passed in the environment that authored these fixes. GitHub Actions remains intentionally disabled for this repository.

Before replacing a running MCP, update a clean/local checkout and run:

```bash
source .venv/bin/activate
python -m pip install -e ".[dev]"
python scripts/validate_local.py
```

Do not proceed to live Google Ads mutation testing unless the command ends with:

```text
LOCAL VALIDATION GREEN
validated version: 0.16.2
```

After the local gate is green, continue with `VALIDATION_CHECKLIST.md` for read-only, MCC read/write isolation, propose/cancel, propose/confirm, durable restart replay, legitimate MCC linking, risk boundaries and live-account E2E.

## Compatibility

0.16.2 does not intentionally remove Google Ads capabilities. It makes public tool ownership deterministic and updates stale test infrastructure to the hardened client contract.
