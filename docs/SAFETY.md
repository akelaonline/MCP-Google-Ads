# Safety model

Google Ads mutations can change live spend. The MCP therefore treats writes differently from reads.

## Default flow

Every write tool proposes a change through the shared `SafetyLayer`.

```text
write tool
   |
   v
SafetyLayer.propose(...)
   |
   +-- auto-approve=false --> pending_action_id --> explicit confirmation
   |
   +-- auto-approve=true  --> execute immediately
                                      |
                                      v
                                Google Ads API
                                      |
                                      v
                                  audit.db
```

The default is:

```dotenv
GOOGLE_ADS_MCP_AUTO_APPROVE=false
```

For accounts with real spend, keep it false.

## Pending actions

A proposed change returns a structure similar to:

```json
{
  "status": "pending_confirmation",
  "pending_action_id": "7f3a2c1e9abc",
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

## Retry behavior

v0.12 fixes an important failure mode from earlier versions.

A pending action is **not removed before execution**. If Google Ads or the network fails during confirmation:

- the same pending action remains available;
- its attempt count increments;
- the failure is written to the audit log;
- the same action ID may be retried after the problem is corrected.

Only a successful confirmation removes the action from the pending set.

## Stable action IDs

The pending ID, confirmation ID and audit ID are now the same identifier.

This makes a mutation traceable end-to-end:

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

Confirmed and auto-approved execution attempts are written to SQLite.

Default location:

```text
~/.google_ads_mcp/audit.db
```

Each row records:

- action ID;
- tool name;
- customer ID;
- human-readable description;
- proposed payload;
- execution result or error;
- status;
- timestamp.

The audit database uses WAL mode and serialized writes for safer concurrent access. The implementation also attempts to restrict the local DB file to owner-only permissions where supported.

Recent entries:

```text
get_recent_audit_log(limit=20)
```

One action across retries:

```text
get_audit_action(action_id)
```

The audit log is an execution trail, not a universal rollback engine. Google Ads resources have different reversibility rules; for destructive changes, prefer pause/disable when the API supports it.

## Atomic multi-resource mutations

Some tools need several Google Ads resources to exist together. Examples include:

- an Asset plus its CampaignAsset link;
- a legacy `create_call_ad` compatibility flow that creates RSA + Call Asset + AdGroupAsset;
- a complete Performance Max AssetGroup and its required assets;
- visual ads whose image assets should not remain orphaned if ad creation fails.

v0.12 uses the Google Ads atomic mutation path for these flows where appropriate. The intended behavior is all-or-nothing instead of “asset created, link failed”.

Bulk status/negative operations also default to all-or-nothing semantics instead of silently accepting partial failures.

## Image-fetch security

Image tools accept model/user-controlled URLs. Those requests are restricted before bytes reach Google Ads.

The fetch helper requires:

- HTTPS;
- standard HTTPS port;
- no embedded URL credentials;
- public DNS resolution;
- no loopback, private, link-local or other non-global IPs;
- safe redirects that remain public HTTPS;
- supported image MIME types;
- bounded response size;
- non-empty image data.

This is specifically intended to prevent an image URL from becoming an SSRF path into the machine or cloud environment running the MCP.

## HTTP transport

`stdio` is the safe default for local MCP clients.

Raw HTTP is blocked by default because the server exposes both mutation and confirmation tools and does not bundle a remote identity provider.

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

## Auto-approve

Auto-approve exists for controlled automation environments:

```dotenv
GOOGLE_ADS_MCP_AUTO_APPROVE=true
```

When enabled, a write executes immediately and is still audited.

Do not enable it casually on an MCC or account with real spend. The safer production pattern is to keep confirmation enabled and let the AI prepare batches for review.

## Rules for contributors

Every mutating tool must:

1. build/validate its operation;
2. call `ctx.safety.propose(...)`;
3. put the actual API mutation inside the supplied `execute` callable;
4. never bypass the safety layer;
5. use atomic mutation when related resources must succeed or fail together;
6. avoid placing raw secrets or raw Customer Match PII in the audit payload;
7. include a real v25 contract test for new/changed protobuf-heavy write paths.
