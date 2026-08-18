# v0.14.0 — Agency Coverage

v0.14.0 expands Google Ads MCP beyond day-to-day campaign operation into common agency administration workflows while retaining the v0.13 customer isolation and risk-aware approval controls.

## Labels

Adds native Google Ads label management:

- list/create/update/remove labels;
- attach/detach labels on campaigns;
- attach/detach labels on ad groups.

The implementation uses v25 `LabelOperation`, `CampaignLabelOperation`, and `AdGroupLabelOperation` contracts.

## Shared negative keyword lists

Adds native account-level shared negative-list management using Google's `SharedSet(NEGATIVE_KEYWORDS)` model:

- list shared sets and their keyword criteria;
- create shared negative keyword lists;
- add BROAD/PHRASE/EXACT negatives;
- remove shared criteria;
- attach/detach shared sets on campaigns;
- remove shared sets.

## Account users and access

Adds customer access administration:

- list account users;
- list user-access invitations;
- invite ADMIN/STANDARD/READ_ONLY/EMAIL_ONLY users;
- update roles;
- remove users;
- revoke invitations.

Account-access writes are classified as sensitive or destructive by the v0.13 safety policy and therefore remain confirmation-gated unless the matching high-risk policy has been explicitly enabled.

The v25 customer-access services use singular mutate RPC names; the shared client wrapper now includes those exact irregular method mappings.

## Billing and invoices

Adds read-only agency billing visibility:

- list billing setups and payments-account metadata;
- list invoices by billing setup, year and month;
- optionally request granular invoice details.

Invoice requests are customer-allowlist checked before calling `InvoiceService`.

## Conversion adjustments

Adds sensitive conversion correction workflows:

- `retract_conversion` for conversion retractions;
- `restate_conversion_value` for value restatements.

Both use the v25 `ConversionAdjustmentUploadService`. Google's required `partial_failure=true` is preserved, while the MCP explicitly parses `partial_failure_error` and raises an MCP error on row-level rejection instead of returning false success.

## Safety and compatibility

- All new writes run through `SafetyLayer`.
- Customer allowlists from v0.13 continue to protect both read and write operations.
- User/access and conversion-adjustment writes are high-risk.
- Label and shared-list removal paths are destructive by central policy.
- Billing and invoice tools are read-only.
- Existing v0.13 tool signatures remain unchanged.

## Regression coverage

v0.14 adds real Google Ads v25 contract tests for:

- labels and campaign/ad-group label relationships;
- shared negative sets, criteria and campaign relationships;
- customer-user access operations and exact mutate RPC names;
- invoice request construction and customer scoping;
- conversion retractions/restatements and partial-failure handling.

The source guardrail allows `partial_failure=true` only in explicitly parsed conversion upload modules and requires those modules to contain `partial_failure_error` handling and `GoogleAdsMcpError` escalation.

## Agency reference

See `docs/AGENCY_TOOLS.md` for the v0.14 signatures and operational notes.
