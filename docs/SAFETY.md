# Safety model

## Why two-phase mutations

An LLM with direct write access to a Google Ads account is one misread instruction away from pausing the wrong campaign or 10x-ing a budget. This server assumes that risk is real and designs around it, rather than trusting prompt discipline alone.

Every tool whose name starts with `create_`, `update_`, `remove_`, `set_`, `add_`, or `upload_` follows the same shape internally:

```python
def execute():
    return ctx.client.mutate(service_name, customer_id, [operation])

return ctx.safety.propose(
    tool_name=...,
    customer_id=...,
    description=...,   # human-readable summary of exactly what will change
    payload=...,        # the raw arguments, for the audit trail
    execute=execute,
)
```

`SafetyLayer.propose()` does **not** call `execute()`. It stores the callable, generates a short `pending_action_id`, and returns a preview. The Google Ads API is only touched when:

- `confirm_pending_action(action_id)` is called explicitly, or
- `GOOGLE_ADS_MCP_AUTO_APPROVE=true` is set (execution happens immediately, still logged).

## Expiry

Pending actions expire after `GOOGLE_ADS_MCP_PENDING_TTL_MINUTES` (default 30). This prevents a stale, half-forgotten proposal from being confirmed hours later against a since-changed account state. `list_pending_actions()` shows age in seconds for anything still live.

## Audit trail

Every **executed** mutation (confirmed or auto-approved) is written to `audit.db` (SQLite, path configurable via `GOOGLE_ADS_MCP_AUDIT_DB`) with:

- the tool name and full input payload
- a human-readable description
- the API result (resource names created/changed) or the error, if it failed
- a timestamp

Query it directly for compliance/reporting:

```bash
sqlite3 audit.db "SELECT created_at, tool_name, customer_id, description, status FROM audit_log ORDER BY id DESC LIMIT 20;"
```

Or from Claude: `get_recent_audit_log(limit=20)`.

## What's intentionally NOT protected

- **Reporting tools** (`list_*`, `get_*`, `run_gaql_query`) execute immediately — they're read-only, nothing to confirm.
- **`remove_*` tools still go through the same single-confirmation flow as everything else.** If you want a stricter policy (e.g. requiring a second, separate confirmation for `remove_campaign`), that's a good first contribution — see `CONTRIBUTING.md`.

## Recommended operating mode

Keep `GOOGLE_ADS_MCP_AUTO_APPROVE=false` for any account with real client spend. Only enable auto-approve for a narrowly scoped, well-tested automation (e.g. a nightly negative-keyword sync from a fixed search-terms query) — and even then, prefer running that specific flow as its own script rather than opening auto-approve for the whole conversational agent.
