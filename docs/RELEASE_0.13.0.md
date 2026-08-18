# v0.13.0 — Multi-client production policy

v0.13.0 hardens Google Ads MCP for agencies and other deployments operating multiple live customer accounts. The release intentionally prioritizes isolation and bounded automation before expanding the Google Ads API surface further.

## Customer isolation

- Add `GOOGLE_ADS_MCP_ALLOWED_CUSTOMER_IDS` as an optional comma-separated deployment scope.
- When configured, GAQL reads, resource-specific mutations, atomic mutations and accessible-customer discovery are restricted to the allowed customer IDs.
- Add `GOOGLE_ADS_MCP_REQUIRE_CUSTOMER_ALLOWLIST=true` for strict deployments; startup fails when strict mode is enabled without at least one allowed customer ID.
- Write scope is enforced by both the client wrapper and `SafetyLayer` for defense in depth.
- Leaving the allowlist unset preserves the previous all-accessible-customers behavior for backward compatibility.

## Risk-aware approvals

Mutating actions now receive a central risk level:

- `standard`
- `spend`
- `destructive`
- `sensitive`

Production `GOOGLE_ADS_MCP_AUTO_APPROVE=true` only auto-executes standard writes by default. High-risk classes require their own explicit opt-ins:

```dotenv
GOOGLE_ADS_MCP_AUTO_APPROVE_SPEND=false
GOOGLE_ADS_MCP_AUTO_APPROVE_DESTRUCTIVE=false
GOOGLE_ADS_MCP_AUTO_APPROVE_SENSITIVE=false
```

Examples classified as spend include budgets, bidding, enable operations and recommendation application. Removal operations and `REMOVED` status are destructive. Customer Match, enhanced/offline conversion uploads and MCC/account access changes are sensitive.

Pending responses include `risk_level` and `confirmation_reason`; pending-action listings also expose the risk level.

## Compatibility

- Existing deployments without an allowlist continue to reach the accounts available to their Google Ads credentials.
- Existing deployments with global auto-approve enabled will see high-risk production actions become pending unless the corresponding new opt-in is enabled. This is an intentional safety change.
- Direct/internal `SafetyLayer(auto_approve=True)` callers that omit the new policy parameters retain legacy execution semantics so existing contract-test harnesses and integrations do not break. The production context always passes explicit policy values from Settings.

## Recommended agency deployment

For a customer-specific MCP instance:

```dotenv
GOOGLE_ADS_MCP_ALLOWED_CUSTOMER_IDS=123-456-7890
GOOGLE_ADS_MCP_REQUIRE_CUSTOMER_ALLOWLIST=true
GOOGLE_ADS_MCP_AUTO_APPROVE=false
GOOGLE_ADS_MCP_AUTO_APPROVE_SPEND=false
GOOGLE_ADS_MCP_AUTO_APPROVE_DESTRUCTIVE=false
GOOGLE_ADS_MCP_AUTO_APPROVE_SENSITIVE=false
```

If hierarchy queries are required, include the relevant MCC customer ID in the allowlist too.

For existing installations, the allowlist can be rolled out incrementally: deploy v0.13.0 first with the current account scope, verify the intended customer IDs, then enable strict allowlist mode per client instance. Do not copy a single customer's allowlist blindly across shared deployments.

## Validation

The release includes dedicated production-policy tests for customer-ID normalization, allowlist filtering, strict-mode startup, pre-execution cross-account blocking, risk classification, high-risk confirmation behavior and independent spend opt-in. The standard CI matrix validates Python 3.11, 3.12 and 3.13 with dependency checks, MCP smoke registration, Ruff and the complete pytest suite.
