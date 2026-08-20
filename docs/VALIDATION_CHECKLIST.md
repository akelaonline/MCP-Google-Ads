# Google Ads MCP 0.16.1 production validation checklist

Use this checklist after updating the local server from GitHub and before treating a specific deployment as production-validated.

The purpose is to verify both functionality and the safety boundaries added in the v0.16 series, including the 0.16.1 startup/isolation hotfix.

## 1. Install and static validation

```bash
cd /path/to/MCP-Google-Ads
source .venv/bin/activate
pip install -e ".[dev]"
python scripts/smoke_test.py
ruff check src tests scripts
pytest -q
```

Also exercise the real server-construction path:

```bash
python - <<'PY'
from google_ads_mcp.server import build_server
server = build_server()
print("OK build_server", server)
PY
```

Record:

```bash
git rev-parse HEAD
python -c "import google_ads_mcp; print(google_ads_mcp.__version__)"
```

Expected release version: `0.16.1`.

Do not continue to live mutation testing if the local suite, smoke test, or `build_server()` check fails.

## 2. Read-only kill switch

Start with:

```dotenv
GOOGLE_ADS_MCP_READ_ONLY=true
```

Verify:

- `list_accessible_customers()` works;
- a normal report works;
- raw GAQL works for an allowed customer;
- audit inspection works;
- a write tool is rejected before a pending proposal is created;
- an existing pending action cannot be confirmed while read-only is enabled;
- pending actions can still be listed/cancelled.

## 3. Customer allowlist

Recommended test configuration:

```dotenv
GOOGLE_ADS_MCP_ALLOWED_CUSTOMER_IDS=<test-manager>,<test-client-a>,<test-client-b>
GOOGLE_ADS_MCP_REQUIRE_CUSTOMER_ALLOWLIST=true
```

Verify a customer outside the allowlist is rejected before the MCP contacts that account.

## 4. MCC hierarchy read isolation

Using an allowed manager/client structure, verify the three hierarchy/link surfaces:

- `customer_client`
- `customer_client_link`
- `customer_manager_link`

Rows referencing a customer outside the allowlist must not be returned.

For raw GAQL, deliberately omit the ownership field once and confirm the MCP fails closed:

- `customer_client` requires `customer_client.id`;
- `customer_client_link` requires `customer_client_link.client_customer`;
- `customer_manager_link` requires `customer_manager_link.manager_customer`.

## 5. Propose and cancel

Switch to normal confirmation mode:

```dotenv
GOOGLE_ADS_MCP_READ_ONLY=false
GOOGLE_ADS_MCP_AUTO_APPROVE=false
GOOGLE_ADS_MCP_AUTO_APPROVE_SPEND=false
GOOGLE_ADS_MCP_AUTO_APPROVE_DESTRUCTIVE=false
GOOGLE_ADS_MCP_AUTO_APPROVE_SENSITIVE=false
```

Choose a harmless reversible operation in a dedicated test customer.

Verify:

1. the write returns `pending_confirmation`;
2. the response contains `pending_action_id`;
3. the account is unchanged before confirmation;
4. `cancel_pending_action()` removes the proposal;
5. the cancelled mutation never reaches Google Ads.

## 6. Propose and confirm

Create another harmless reversible proposal and confirm it.

Verify:

- exactly one mutation occurs;
- audit status is success;
- `get_audit_action(action_id)` contains the same action ID;
- the pending action disappears after success.

Return the test resource to its original state through a separately reviewed proposal.

## 7. Durable restart replay

Create a pending action but do not confirm it.

Restart the MCP process/client while preserving:

- the same audit DB;
- the same `GOOGLE_ADS_MCP_PENDING_ENCRYPTION_KEY`, or generated `.pending.key` file.

Verify:

- the action still appears in `list_pending_actions()`;
- the same action ID can be confirmed after restart;
- audit/retry history stays correlated to that action ID.

Then test fail-closed behavior in a disposable environment by making the persisted invocation undecryptable/unavailable; confirmation must fail without a Google Ads mutation.

## 8. Cross-customer mutation isolation

With two allowlisted child customers, deliberately construct/test a write for customer A that references a customer-B resource where a normal operation must remain same-customer.

Expected result: the MCP rejects the operation before the Google mutate RPC.

Do not use a production campaign for this test.

The local unit suite must also pass the protobuf map/list isolation regressions in `tests/test_recursive_customer_isolation.py`.

## 9. Legitimate manager/client link exception

Only if the deployment uses MCC link administration, test the explicit manager/client link workflow with two intended allowlisted accounts.

Verify the legitimate two-customer relationship is permitted while arbitrary mixed-customer campaign/ad/asset operations remain blocked.

## 10. Risk classification / auto-approve boundary

With global standard auto-approve enabled only in a dedicated test environment:

```dotenv
GOOGLE_ADS_MCP_AUTO_APPROVE=true
GOOGLE_ADS_MCP_AUTO_APPROVE_SPEND=false
GOOGLE_ADS_MCP_AUTO_APPROVE_DESTRUCTIVE=false
GOOGLE_ADS_MCP_AUTO_APPROVE_SENSITIVE=false
```

Verify:

- resource-only/PAUSED creative preparation may auto-execute when classified `standard`;
- live asset create+attach helpers return `spend` and remain pending;
- editing an existing RSA returns `spend` and remains pending;
- budget/bid/keyword/targeting changes remain pending;
- destructive and sensitive operations remain pending.

Restore all auto-approve values to the intended production policy afterward.

## 11. Double-confirm race

Create one pending action. Trigger two confirmation requests as close together as the test client permits.

Expected result within one MCP process: only one execution reaches Google Ads. The second call must not execute the same mutation again.

Do not run several MCP processes against the same `audit.db`; the current lock is process-local, not distributed.

## 12. HTTP boundary — only when used

If the deployment uses HTTP instead of stdio:

- verify the MCP is not directly reachable from the public Internet;
- verify the external boundary authenticates callers;
- verify network access is restricted to intended clients;
- confirm `GOOGLE_ADS_MCP_ALLOW_INSECURE_HTTP=true` is understood as a startup opt-in only, not authentication.

If HTTP is not required, keep stdio.

## Sign-off record

For each validated deployment record:

- Git commit SHA;
- MCP version;
- Python version;
- Google Ads Python client version;
- date/time;
- test customer IDs in sanitized form;
- local suite result;
- E2E checklist result;
- operator who performed the test.

A repository release can be code-complete while a particular installation remains unvalidated. Treat this checklist as the deployment-level sign-off.
