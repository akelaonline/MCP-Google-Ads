# Google Ads MCP 0.16.8

**Release date:** 2026-08-21
**Google Ads API:** v25
**Release type:** registry-hardening — fix silent duplicate-tool registration, correct Conversion Value Rules ownership

0.16.8 fixes a real registration bug found in an independent local gate review of the assembled server: canonical-tool bookkeeping could silently drop a *new* implementation that competed for an already-canonicalized public name, because any non-canonical module was treated as "known legacy" without checking that it actually was the legacy source.

## The bug

`_candidate_should_register()` in `invocation.py` returned `False` for every module whose name was not the canonical owner for a tool in `_CANONICAL_TOOL_MODULES`. The smoke test reports "canonical tool owners verified" because the canonical module still wins — but a competing module that is **not** the original legacy (for example a newer, better implementation) is discarded silently, and nothing fails.

Concrete victim: `conversions.py::create_conversion_value_rule` — the typed implementation with `geo_target_ids` / `audience_condition` / `device_type` — was never registered as a public MCP tool, because `remaining_core_services.py` held the canonical slot from 0.16.2. Anyone calling the tool via MCP got the generic protobuf-JSON variant, and the typed one was dead code reachable only from tests that register modules in isolation.

## The fix

### Declared legacy only (`invocation.py`)
- New `_LEGACY_TOOL_MODULES: dict[str, frozenset[str]]` — the set of modules that may be skipped silently for each canonical tool name (the actual superseded sources: `performance_max` for the asset-group signals, `remaining_core_services` for the typed CVR create, `conversions` for the rich CVR read).
- `_candidate_should_register()` now:
  - registers the canonical module;
  - silently skips only declared legacy modules;
  - raises `RuntimeError` for any other module competing for the same public name ("Unexpected duplicate MCP tool registration…").

### Conversion Value Rules ownership corrected
- `create_conversion_value_rule` canonical owner → **`google_ads_mcp.tools.conversions`** (typed conditions; the ergonomic path).
- The generic protobuf-JSON variant is renamed and remains public as **`create_conversion_value_rule_from_json`** (full v25 payload, `validate_only`).
- `list_conversion_value_rules` keeps **`remaining_core_services`** as owner — its read is richer (`owner_customer`, audience/device/geo/itinerary condition objects).

## Regression guard

New `tests/test_tool_registry_sweep.py`:

1. builds the **real assembled server** (all tool modules, exactly like `smoke_test.py`) and asserts every canonical tool is owned by its declared module;
2. sweeps the whole tools tree for tool names defined by more than one module and asserts every definer is either the canonical owner or a declared legacy — no undeclared duplicates anywhere;
3. asserts an undeclared duplicate raises `RuntimeError`;
4. asserts a declared legacy is skipped silently while the canonical owner stays registered.

## Validation

`python scripts/validate_local.py` green end-to-end:

```text
isolated smoke  -> SMOKE OK (55 tool modules, zero duplicate-tool warnings)
ruff check      -> All checks passed!
pytest -q       -> 346 passed
```

## Live-account E2E (post-release)

Unlike earlier 0.16.x notes, 0.16.8 has also been exercised end-to-end against a real production Google Ads MCC, following `docs/VALIDATION_CHECKLIST.md`:

- **Read-only kill switch** — with `GOOGLE_ADS_MCP_READ_ONLY=true`, reads/GAQL kept working and a write attempt was rejected before any Google Ads mutation, with no pending action created.
- **Cross-customer isolation** — a deliberate cross-customer resource reference (`attach_audience_to_ad_group` pointing at another customer's user list) was blocked before contacting Google Ads: `"Cross-customer mutation was blocked before contacting Google Ads."`
- **Propose / cancel** — a proposed write returned `pending_confirmation`, the target account was confirmed unchanged, and `cancel_pending_action()` discarded it cleanly.
- **Propose / confirm** — a second proposal was confirmed for real; the mutation applied to the live account and the audit log recorded a matching `status: "success"` entry under the same `action_id`.
- **Durable restart replay** — a pending action was left unconfirmed, the MCP process was restarted, and the action was still listed (`loaded_in_memory: false`, reloaded from the durable store) and could still be confirmed afterward (`replayed_after_restart: true`).

No production campaign, budget, or delivery-affecting setting was altered by this pass — every mutation used was a trivially reversible metadata change on a disposable test account, and the account was restored to its original state at the end.
