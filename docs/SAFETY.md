# Safety model

Google Ads mutations can change live spend, account access, audiences and conversion data. The MCP therefore applies central customer isolation and risk-aware approval policy in addition to per-tool validation.

## Default write flow

Every mutating tool proposes a change through the shared `SafetyLayer`.

```text
write tool
   |
   v
SafetyLayer.propose(...)
   |
   +-- customer outside allowlist --> BLOCKED
   |
   +-- auto-approve=false --> pending_action_id --> explicit confirmation
   |
   +-- auto-approve=true
          |
          +-- standard --> execute
          +-- spend/destructive/sensitive --> explicit high-risk opt-in OR pending
                                                        |
                                                        v
                                                  Google Ads API
                                                        |
                                                        v
                                                    audit.db
```

The safest production default remains:

```dotenv
GOOGLE_ADS_MCP_AUTO_APPROVE=false
```

## Customer isolation

For deployments serving one client or a known group of accounts, configure an allowlist:

```dotenv
GOOGLE_ADS_MCP_ALLOWED_CUSTOMER_IDS=123-456-7890,987-654-3210
```

When the list is non-empty, scoped reads and writes for any other customer ID are rejected centrally. Account discovery is filtered to the allowed IDs as well.

For strict deployments, make the allowlist mandatory:

```dotenv
GOOGLE_ADS_MCP_REQUIRE_CUSTOMER_ALLOWLIST=true
```

With this flag enabled, the MCP refuses to start if the allowlist is empty. This is recommended for one-MCP-per-client and other multi-tenant production patterns.

The allowlist is enforced twice for writes: by the Google Ads client wrapper and by the `SafetyLayer`. This provides defense in depth for tools that need to construct Google Ads resources through the raw client before executing through the shared mutation path.

## Risk-aware auto-approve

`GOOGLE_ADS_MCP_AUTO_APPROVE=true` no longer means every write can execute immediately.

Writes are centrally classified as:

- `standard` — ordinary non-spend writes such as creating a paused creative or attaching a normal asset;
- `spend` — budgets, bidding, enabling delivery, bid modifiers, recommendation application and similar actions that can change delivery/spend;
- `destructive` — removals, `REMOVED` status changes and ending experiments;
- `sensitive` — Customer Match, enhanced/offline conversion uploads, manager-link acceptance and client-account creation.

High-risk categories remain confirmation-gated unless separately enabled:

```dotenv
GOOGLE_ADS_MCP_AUTO_APPROVE=true
GOOGLE_ADS_MCP_AUTO_APPROVE_SPEND=false
GOOGLE_ADS_MCP_AUTO_APPROVE_DESTRUCTIVE=false
GOOGLE_ADS_MCP_AUTO_APPROVE_SENSITIVE=false
```

This preserves controlled automation for standard writes while preventing one global flag from silently authorizing spend, deletion or sensitive-data/account-access operations.

If a deployment deliberately needs unattended high-risk automation, each class has its own explicit opt-in. Keep those flags false unless the surrounding system provides its own strong policy controls.

## Pending actions

A proposed change returns a structure similar to:

```json
{
  "status": "pending_confirmation",
  "pending_action_id": "7f3a2c1e9abc",
  "risk_level": "spend",
  "confirmation_reason": "Spend-changing action requires separate auto-approve opt-in.",
  "description": "Set campaign 123 budget ...",
  "expires_in_minutes": 30
}
```

Nothing has changed yet.

Execute it with:

```text
confirm_pending_action("7f3a2c1e9abc")
```

Discard it with:

```text
cancel_pending_action("7f3a2c1e9abc")
```

Inspect all open proposals with:

```text
list_pending_actions()
```

Pending-action listings include the risk level.

## Retry behavior

A pending action is **not removed before execution**. If Google Ads or the network fails during confirmation:

- the same pending action remains available;
- its attempt count increments;
- the failure is written to the audit log;
- the same action ID may be retried after the problem is corrected.

Only a successful confirmation removes the action from the pending set.

## Stable action IDs

The pending ID, confirmation ID and audit ID are the same identifier.

```text
proposal 7f3a2c1e9abc
  -> attempt 1: error
  -> attempt 2: success
```

Use:

```text
get_audit_action("7f3a2c1e9abc")
```

to inspect all recorded attempts for an action.

## Expiration

Pending actions expire after:

```dotenv
GOOGLE_ADS_MCP_PENDING_TTL_MINUTES=30
```

Expired proposals cannot be confirmed and must be proposed again.

## Audit log

Confirmed and auto-approved execution attempts are written to SQLite. The default location is:

```text
~/.google_ads_mcp/audit.db
```

Each row records the action ID, tool name, customer ID, description, proposed payload, execution result/error, status and timestamp. The audit database uses WAL mode and serialized writes for safer concurrent access and attempts to restrict the local DB file to owner-only permissions where supported.

The audit log is an execution trail, not a universal rollback engine. Google Ads resources have different reversibility rules; for destructive changes, prefer pause/disable when the API supports it.

## Atomic multi-resource mutations

Some tools need several Google Ads resources to exist together, such as an Asset plus its CampaignAsset link, the Call Ad compatibility flow, complete Performance Max AssetGroups, and visual/Demand Gen ads whose assets should not be orphaned.

These flows use the Google Ads atomic mutation path where appropriate. Bulk status/negative operations also default to all-or-nothing semantics instead of silently accepting partial failures.

## Image-fetch security

Image tools accept model/user-controlled URLs. The scoped fetch helper requires public HTTPS, standard port 443, no URL credentials, public DNS/IPs, safe redirects, supported image MIME types, bounded response size and non-empty image data. Loopback, private, link-local and otherwise non-global destinations are rejected to prevent SSRF into the MCP host or cloud environment.

## HTTP transport

`stdio` is the safe default for local MCP clients. Raw HTTP is blocked by default because the server exposes both mutation and confirmation tools and does not bundle a remote identity provider.

```dotenv
GOOGLE_ADS_MCP_TRANSPORT=stdio
GOOGLE_ADS_MCP_ALLOW_INSECURE_HTTP=false
```

If you deliberately place the server behind your own authenticated and network-restricted reverse proxy, explicit opt-in is required:

```dotenv
GOOGLE_ADS_MCP_TRANSPORT=http
GOOGLE_ADS_MCP_ALLOW_INSECURE_HTTP=true
```

That setting **does not provide authentication**. It only removes the startup block. The external security layer remains your responsibility.

## Rules for contributors

Every mutating tool must:

1. build and validate its operation;
2. call `ctx.safety.propose(...)` with the real customer ID and meaningful payload fields;
3. put the actual API mutation inside the supplied `execute` callable;
4. never bypass the safety layer;
5. use the central client wrapper for scoped reads/mutations wherever possible;
6. use atomic mutation when related resources must succeed or fail together;
7. avoid raw secrets or raw Customer Match PII in audit payloads;
8. add real v25 contract tests for new or changed protobuf-heavy write paths;
9. preserve enough payload metadata (`status`, budget/bid values, etc.) for the central risk classifier to make a conservative decision.
