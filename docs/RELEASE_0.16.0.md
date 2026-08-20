# v0.16.0 — Coverage Completion

v0.16.0 closes the Google Ads API v25 service-coverage pass while preserving the multi-client safety policy introduced in v0.13 and expanded through v0.15.

## Coverage result

The audited Google Ads API v25 inventory contains 110 service classes. This release records:

- 102 stable-public services: **SUPPORTED**
- 5 Google-restricted / allowlisted services: **RESTRICTED**
- 2 beta / closed-beta services: **BETA**
- 1 service documented as not public: **NOT_PUBLIC**
- 0 stable-public services: **MISSING**

See `docs/API_COVERAGE_V25.md` for the classification and methodology.

## Final closure additions

### Identity verification

- `get_identity_verification`
- `start_advertiser_identity_verification`

Uses `IdentityVerificationService` and keeps starting verification behind the sensitive-action confirmation policy.

### SKAdNetwork conversion-value schema

- `list_skadnetwork_conversion_schemas`
- `update_skadnetwork_conversion_schema`

Uses the v25 singular `MutateCustomerSkAdNetworkConversionValueSchemaRequest.operation` contract, supports `validate_only` and Google warnings, and blocks cross-customer resource names.

### Direct UserDataService

- `upload_customer_match_user_data_direct`

Supports direct CREATE/REMOVE Customer Match operations. Email/phone identifiers are normalized and SHA-256 hashed locally; raw PII is not placed in the audit payload. Classified `sensitive`.

### User-list lifecycle customer types

- `list_user_list_customer_types`
- `assign_user_list_customer_type`
- `remove_user_list_customer_type`

Adds the v25 `UserListCustomerTypeService` relationship lifecycle.

### Brand suggestions

- `suggest_brands`

Adds the stable read-only `BrandSuggestionService` surface.

### Recommendation generation completion

- `generate_campaign_construction_recommendations`

Completes all ten v25 recommendation types documented for `GenerateRecommendations` during campaign construction while preserving the existing simple `generate_keyword_recommendations` helper.

### Restricted services represented honestly

`ReachPlanService` is wrapped across all six v25 RPC families:

- conversion-rate generation
- reach forecasting
- plannable locations
- plannable products
- plannable user interests
- plannable user lists

`IncentiveService` adds fetch/apply workflows.

Both services surface explicit Google allowlist notes instead of treating access restrictions as MCP implementation failures.

## Safety

The following new writes are centrally classified `sensitive`:

- `upload_customer_match_user_data_direct`
- `start_advertiser_identity_verification`
- `update_skadnetwork_conversion_schema`
- `apply_incentive`

Existing customer allowlists and cross-customer resource/mutation guards remain in force.

## Validation

`tests/test_v16_final_coverage_contracts.py` locks the generated v25 service, RPC, request and operation names for the final closure surfaces and verifies their risk classification.

The finalization pass intentionally did not consume GitHub Actions. The final editing environment did not have the `google-ads` package installed and could not install dependencies, so this release note does not falsely claim a local pytest run from that environment. The contract tests are committed for execution in a normal development environment with the declared dependencies installed.

## Compatibility

- Google Ads API remains fixed to `v25`.
- Google Ads Python client remains on the tested `31.x` dependency line.
- Existing v0.15 tool names and deployment-policy environment variables remain available.
- `generate_keyword_recommendations` remains available; the new campaign-construction generator is additive.
- Google-side account eligibility, product enrollment and allowlists remain external capability constraints.
