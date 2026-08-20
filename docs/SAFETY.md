# Safety model

Google Ads mutations can change live spend, account access, billing, audiences and
conversion data. Google Ads MCP therefore treats safety as a central platform
property rather than a convention individual tools are expected to remember.

## Default write flow

Every normal mutating tool goes through the shared `SafetyLayer`:

```text
MCP tool
  |
  v
validate customer + resource ownership
  |
  v
SafetyLayer.propose(...)
  |
  +-- policy blocks request --> no Google RPC
  |
  +-- confirmation required --> durable pending_action_id
  |                               |
  |                               v
  |                         confirm / cancel
  |
  +-- explicitly auto-approved by risk class
                                  |
                                  v
                           Google Ads API
                                  |
                                  v
                       SQLite audit history
```

Recommended production default:

```dotenv
GOOGLE_ADS_MCP_AUTO_APPROVE=false
GOOGLE_ADS_MCP_AUTO_APPROVE_SPEND=false
GOOGLE_ADS_MCP_AUTO_APPROVE_DESTRUCTIVE=false
GOOGLE_ADS_MCP_AUTO_APPROVE_SENSITIVE=false
```

## Customer isolation

### Deployment allowlist

For a known set of customers:

```dotenv
GOOGLE_ADS_MCP_ALLOWED_CUSTOMER_IDS=123-456-7890,987-654-3210
GOOGLE_ADS_MCP_REQUIRE_CUSTOMER_ALLOWLIST=true
```

With an allowlist, scoped reads and writes for any other customer are rejected
before the account is contacted. Account discovery is filtered to allowed IDs.
Strict mode refuses startup when the required allowlist is empty.

### MCC read isolation

An allowed manager customer can describe child customers through GAQL even when
the child is not itself inside this deployment's scope. v0.16 therefore applies
row-level filtering to the MCC hierarchy surfaces that can enumerate other
customers:

- `customer_client` rows are filtered by `customer_client.id`;
- `customer_client_link` rows are filtered by the referenced `client_customer`.

This protection is implemented inside the shared client `search()` path, so it
also applies to `run_gaql_query()`, not only to the pre-built account helpers.

When an allowlist is configured, a raw hierarchy query that omits the ownership
field needed to filter safely fails closed. For example, a `customer_client`
query must select `customer_client.id`; otherwise the MCP cannot prove which
tenant owns each row and returns an error instead of the data.

### Recursive mutation guard

An MCC credential can access several child accounts. Validating only the request
`customer_id` is therefore insufficient: a malformed or buggy CREATE operation
for customer A could otherwise contain a nested `asset`, `campaign`, `ad_group`,
`shared_set`, or other resource name owned by customer B.

0.16 recursively inspects populated protobuf fields for customer-scoped resource
names before resource-specific and atomic mutations. This covers references in:

- CREATE operations;
- UPDATE operations;
- REMOVE operations;
- nested `GoogleAdsService.MutateOperation` messages;
- repeated resource-name fields.

A mixed-customer resource reference is blocked before the Google mutate RPC.

### Narrow MCC linking exception

Manager/client linking legitimately needs two Google Ads customers in one
operation. `CustomerClientLinkService` CREATE is therefore a deliberately narrow
exception to same-customer resource ownership.

The exception does **not** mean arbitrary cross-account references are accepted:
all referenced customer IDs must still pass `GOOGLE_ADS_MCP_ALLOWED_CUSTOMER_IDS`
when an allowlist is configured. Campaign/ad/asset/criterion mutations keep strict
same-customer isolation.

## Risk classes

Writes are classified centrally as:

- `standard` — ordinary writes that do not directly alter spend/access/sensitive data;
- `spend` — budgets, bids and changes that can materially affect live delivery or
  bidding inputs, including enabled keywords, match changes, negatives,
  location/language/placement targeting, audience/topic attachment, live goals,
  experiment launch/splits, PMax listing/signals and recommendation application;
- `destructive` — removals, terminal statuses, unlinking access, ending experiments;
- `sensitive` — Customer Match/first-party data, conversion uploads, billing,
  identity, SKAd, account access, manager links and external product/data links.

Normal creative/resource preparation such as creating callouts or sitelinks remains
`standard` by design. The delivery-changing list is deliberately more conservative
because a deployment may enable automatic execution for standard writes.

Global auto-approve is not a master bypass. Even with:

```dotenv
GOOGLE_ADS_MCP_AUTO_APPROVE=true
```

high-risk classes remain gated unless separately enabled:

```dotenv
GOOGLE_ADS_MCP_AUTO_APPROVE_SPEND=false
GOOGLE_ADS_MCP_AUTO_APPROVE_DESTRUCTIVE=false
GOOGLE_ADS_MCP_AUTO_APPROVE_SENSITIVE=false
```

## Pending actions

A write that requires confirmation returns data similar to:

```json
{
  "status": "pending_confirmation",
  "pending_action_id": "7f3a2c1e9abc",
  "risk_level": "spend",
  "durable": true,
  "description": "Update campaign budget ...",
  "expires_in_minutes": 30
}
```

Nothing has changed yet.

Use:

```text
confirm_pending_action("7f3a2c1e9abc")
cancel_pending_action("7f3a2c1e9abc")
list_pending_actions()
```

### Confirm/cancel serialization

FastMCP may dispatch synchronous tool calls concurrently. v0.16 serializes
`confirm_pending_action`, `cancel_pending_action`, and pending-list snapshots
through one process-local control lock. Two simultaneous confirmations in the
same server process therefore cannot both execute one pending action before it is
removed, and cancel cannot race a confirmation that is entering execution.

This is a **process-local** guarantee. The SQLite pending table is not a distributed
lease/claim system. One simultaneously running MCP process should own one
`audit.db`. Do not point multiple workers/processes at the same pending DB unless
an external single-writer/claim mechanism is provided.

## Durable restart-safe confirmations

With the built-in `AuditLog`, pending actions are persisted in the same SQLite
store used for execution audit.

The original public MCP tool invocation is needed to reconstruct the proposal
after a process restart. Those invocation arguments are **encrypted before they
are stored in SQLite**.

### Encryption key

Preferred for containers and VMs where the generated sibling key may not persist:

```dotenv
GOOGLE_ADS_MCP_PENDING_ENCRYPTION_KEY=<stable-fernet-key>
```

Generate one once:

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

If the environment variable is omitted, the MCP creates:

```text
<audit-db>.pending.key
```

and attempts to set owner-only permissions on supported systems.

**Persist the audit DB and key together.** If the key is unavailable after a
restart, the encrypted invocation cannot be replayed. The MCP fails closed and
does not execute the Google Ads mutation.

### Public tool name vs safety alias

Some public tools share an internal safety category. For example, specialized
wrappers may classify under an existing risk alias.

0.16 stores the exact public MCP tool name inside encrypted replay metadata, so a
pending action can be reconstructed after restart even when its risk/audit alias
is different from the public function name.

### Backward compatibility

Custom audit backends that only implement `record()` remain supported. They keep
the previous process-local pending behavior and simply report `durable=false`.

## Retry behavior and stable action IDs

A pending action is not deleted before execution. If Google Ads or the network
fails during confirmation:

- the proposal remains pending;
- the attempt counter increments;
- the error is recorded;
- the same `action_id` can be retried.

Only successful execution removes the pending record.

The proposal, replay, retry and audit rows use the same ID:

```text
7f3a2c1e9abc
  -> attempt 1: error
  -> attempt 2: success
```

Inspect it with:

```text
get_audit_action("7f3a2c1e9abc")
```

## Expiration

```dotenv
GOOGLE_ADS_MCP_PENDING_TTL_MINUTES=30
```

Expired pending actions are removed from process memory and the durable pending
store. They must be proposed again.

## Audit log

Default location:

```text
~/.google_ads_mcp/audit.db
```

Execution rows contain:

- action ID;
- safety tool/category;
- customer ID;
- human-readable description;
- sanitized proposed payload;
- result or error;
- status;
- timestamp.

The DB uses WAL mode and serialized writes. It is an execution trail, not a
universal rollback engine.

### PII rule

Raw Customer Match identifiers and similar first-party data must not be placed in
normal audit payloads. Customer-data tools log counts, consent and operational
metadata instead. Where restart replay genuinely requires original MCP arguments,
those arguments are kept in the separately encrypted pending blob and deleted
after success/cancel/expiry.

## Atomic mutations

Related resources that must succeed together use `GoogleAdsService.Mutate` or
multi-operation resource-specific calls with `partial_failure=false` where the
API supports it.

Examples include:

- complete PMax AssetGroups;
- PMax listing-filter tree replacement;
- supported multi-resource ad creation;
- Smart Campaign creation;
- experiment-arm traffic split updates;
- keyword match-type replacement.

Batch Jobs are different: Google batch execution has partial-success semantics.
The MCP documents that behavior and requires callers to inspect row results.

## Image-fetch security

Remote image tools require public HTTPS and reject:

- loopback/private/link-local/non-global destinations;
- embedded URL credentials;
- non-standard unsafe schemes/ports;
- redirects to private networks;
- unsupported MIME types;
- oversized/empty responses.

This prevents common SSRF paths into the MCP host or cloud metadata networks.

## HTTP transport

`stdio` is the recommended transport.

HTTP is blocked by default because this server exposes both write and confirmation
tools but does not bundle a remote identity provider:

```dotenv
GOOGLE_ADS_MCP_TRANSPORT=stdio
GOOGLE_ADS_MCP_ALLOW_INSECURE_HTTP=false
```

To run HTTP behind your own authenticated/restricted proxy:

```dotenv
GOOGLE_ADS_MCP_TRANSPORT=http
GOOGLE_ADS_MCP_ALLOW_INSECURE_HTTP=true
```

That flag **does not add authentication**. It only removes the startup block.

## Contributor invariants

Every new mutating tool must:

1. validate its input and target customer;
2. validate direct resource names before special/custom RPCs;
3. use the central client wrapper for resource-specific/atomic mutations;
4. call `ctx.safety.propose(...)` before live execution;
5. keep the actual API call inside the supplied `execute` callable;
6. choose a conservative risk category/payload;
7. avoid raw secrets/PII in normal audit payloads;
8. use atomic behavior when several related resources must move together;
9. add real v25 protobuf contract/regression coverage for complex write paths;
10. preserve MCC read isolation when adding hierarchy/link reports;
11. never weaken cross-customer isolation to make one special workflow easier —
    use a narrow validated exception instead.

See also [`V25_SERVICE_COVERAGE.md`](V25_SERVICE_COVERAGE.md).
