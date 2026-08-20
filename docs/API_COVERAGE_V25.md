# Google Ads API v25 coverage — v0.16.0

This document is the source of truth for service-level coverage in Google Ads MCP.

The objective for v0.16 is **zero missing stable-public Google Ads API v25 services**. A service is not counted as complete merely because its resource can be queried with GAQL: when Google exposes a distinct action or mutation RPC, the MCP must expose the material workflow or explicitly classify the service as restricted/beta/not public.

## Coverage result

Google Ads API v25 exposes **110 service classes** in the public reference inventory. v0.16 classifies them as follows:

- **102 stable-public services: SUPPORTED**
- **5 Google-restricted / allowlisted services: RESTRICTED**
- **2 beta / closed-beta services: BETA**
- **1 service documented as not publicly available: NOT_PUBLIC**
- **0 stable-public services: MISSING**

`RESTRICTED`, `BETA`, and `NOT_PUBLIC` are capability boundaries imposed by Google, not implementation gaps. Restricted wrappers surface a clear Google-access explanation instead of reporting the condition as an MCP defect.

## Google-restricted / allowlisted

| Service | Status | MCP behavior |
|---|---|---|
| AudienceInsightsService | RESTRICTED | Capability is tracked; availability depends on Google allowlisting. |
| BenchmarksService | RESTRICTED | Capability is tracked; availability depends on Google allowlisting. |
| ContentCreatorInsightsService | RESTRICTED | Capability is tracked; availability depends on Google allowlisting. |
| IncentiveService | RESTRICTED | `fetch_incentive` / `apply_incentive`; errors explain allowlist requirements. |
| ReachPlanService | RESTRICTED | All six v25 RPC families are wrapped: conversion rates, reach forecast, locations, products, user interests, and user lists. |

## Beta / non-public

| Service | Status | Reason |
|---|---|---|
| AssetGenerationService | BETA | Google closed-beta capability; not universal production coverage. |
| MultiPartyAuthReviewService | BETA | Google beta capability; not treated as universal stable coverage. |
| ReservationService | NOT_PUBLIC | Google documents the service as not publicly available. |

## Stable-public coverage families

All remaining v25 services are represented by first-class MCP workflows and/or the shared mutation/reporting layer. Major families include:

- **Account, MCC, access and billing:** Customer, CustomerClientLink, CustomerManagerLink, CustomerUserAccess, CustomerUserAccessInvitation, AccountBudgetProposal, BillingSetup, PaymentsAccount, Invoice, ProductLink and invitations.
- **Campaign administration:** Campaign, CampaignBudget, CampaignGroup, CampaignDraft, criteria, shared sets, labels, assets, asset sets, automatically-created asset removal, experiments and bidding controls.
- **Ads and ad groups:** AdGroup, AdGroupAd, Ad, criteria, labels, customizers, assets, asset sets, bid modifiers and ad parameters.
- **Assets / Performance Max / Demand Gen:** Asset, AssetGroup, AssetGroupAsset, AssetGroupSignal, listing filters, campaign/ad-group/customer asset links, PMax brand guidelines and shareable previews.
- **Audiences and first-party data:** Audience, CustomAudience, CustomInterest, UserList, OfflineUserDataJob, UserDataService direct uploads and UserListCustomerType relationships.
- **Conversions and goals:** ConversionAction, ConversionUpload, ConversionAdjustmentUpload, custom variables, custom goals, campaign/customer goals, goal configs, value rules/value-rule sets, lifecycle Goal/CampaignGoalConfig and SKAdNetwork schema management.
- **Planning and recommendations:** Keyword Plan services, KeywordPlanIdeaService forecasts, recommendation list/apply/dismiss/auto-apply, and all ten documented `GenerateRecommendations` campaign-construction types.
- **Specialized public services:** GoogleAdsField, GeoTargetConstant, BrandSuggestion, Smart Campaign setting/suggestion, KeywordThemeConstant, DataLink, ThirdPartyAppAnalyticsLink, TravelAssetSuggestion, LocalServicesLead, IdentityVerification, RemarketingAction and YouTubeVideoUpload.
- **Core transport:** GoogleAdsService GAQL/search and atomic cross-resource mutate remain the universal low-level primitives underneath dedicated workflows.

## v0.16 completion additions

The final closure pass adds or completes:

- `IdentityVerificationService` — read progress and start advertiser verification.
- `CustomerSkAdNetworkConversionValueSchemaService` — schema read/update with warnings and singular-operation contract.
- `UserDataService` — direct Customer Match add/remove uploads with local SHA-256 hashing and no raw PII in audit payloads.
- `UserListCustomerTypeService` — list/assign/remove lifecycle categories.
- `BrandSuggestionService` — verified brand suggestions.
- `RecommendationService.GenerateRecommendations` — all ten v25 campaign-construction recommendation types, while preserving the simple keyword helper.
- `ReachPlanService` — all six v25 RPC families, explicitly marked Google-allowlisted.
- `IncentiveService` — fetch/apply wrapper, explicitly marked Google-allowlisted.

## Safety semantics

New identity, first-party-data and measurement-schema writes are confirmation-gated as `sensitive`:

- `upload_customer_match_user_data_direct`
- `start_advertiser_identity_verification`
- `update_skadnetwork_conversion_schema`
- `apply_incentive`

Existing customer isolation still applies before Google is contacted. Restricted read-only planning/suggestion calls do not weaken the write policy.

## Validation note

`tests/test_v16_final_coverage_contracts.py` instantiates the generated Google Ads v25 client and asserts the new services, request/operation types and RPC names. This repository snapshot was finalized without consuming GitHub Actions. The environment used for the final documentation pass did not have the `google-ads` Python package installed, so no claim is made here that the suite was executed in that environment.
