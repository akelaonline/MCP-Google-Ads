# Google Ads API v25 service coverage

This document is the coverage contract for **Google Ads MCP 0.16.0**.

The source of truth is the official Google Ads API v25 service reference. Coverage
is counted at the Google service surface, not by trying to reproduce the Google
Ads UI button-for-button. Standard resource reads are exposed through focused
MCP tools and/or the GAQL fallback; resource writes use typed service operations;
custom RPCs that cannot be represented by GAQL are exposed explicitly when the
public v25 contract documents a safe input shape.

## Status definitions

- **Integrated** — the stable public v25 service is available through focused MCP
  tools, constrained protobuf-JSON tools, GAQL, or a combination of those.
- **Integrated / access-controlled** — the RPC exists in this MCP, but Google
  requires allowlisting, beta access, product eligibility, billing eligibility,
  or another account-level capability.
- **Integrated / specialized** — the service is deliberately handled, but the
  public contract does not document a safe generic write surface for the relevant
  resource, so the MCP exposes only the defensible subset.
- **Not publicly callable** — Google documents the service but does not make it
  publicly available to third-party API clients. The MCP does not fake support.
- **Removed in v25** — legacy service intentionally does not exist in the v25 MCP.

**Stable-public services without deliberate MCP treatment: 0.**

All mutating paths remain subject to customer isolation and the shared
propose/confirm/audit safety layer.

## v25 services

| Google Ads API v25 service | MCP status | Primary MCP coverage |
|---|---|---|
| AccountBudgetProposalService | Integrated | billing/account-budget lifecycle |
| AccountLinkService | Integrated | legacy account links and status lifecycle |
| AdGroupAdLabelService | Integrated | ad label attach/detach |
| AdGroupAdService | Integrated | ad lifecycle + automatic-asset removal |
| AdGroupAssetService | Integrated | ad-group asset links |
| AdGroupAssetSetService | Integrated | asset-set links |
| AdGroupBidModifierService | Integrated | device modifiers + update/remove |
| AdGroupCriterionCustomizerService | Integrated | criterion customizers |
| AdGroupCriterionLabelService | Integrated | keyword/criterion labels |
| AdGroupCriterionService | Integrated | keywords, audiences, bids, negatives, Standard Shopping listing groups |
| AdGroupCustomizerService | Integrated | ad-group customizers |
| AdGroupLabelService | Integrated | ad-group labels |
| AdGroupService | Integrated | ad-group lifecycle, DSA ad groups, tracking URL options |
| AdParameterService | Integrated | `{param1}` / `{param2}` ad parameters |
| AdService | Integrated | RSA creative edits and supported ad operations. `generate_preview` does not exist in v25 (verified against the v25 stubs); previews are covered by ShareablePreviewService instead |
| AssetGenerationService | Integrated / access-controlled | GenerateText + GenerateImages; Google closed beta |
| AssetGroupAssetService | Integrated | Performance Max asset links |
| AssetGroupListingGroupFilterService | Integrated | SHOPPING, RETAIL Product Tags, WEBPAGE filters |
| AssetGroupService | Integrated | PMax asset-group lifecycle |
| AssetGroupSignalService | Integrated | audience, search-theme, Local Services, vertical-feed signals |
| AssetService | Integrated | image/video/media/text/lead-form/price/location/mobile-app/deep-link asset operations used by supported flows |
| AssetSetAssetService | Integrated | asset membership in AssetSets |
| AssetSetService | Integrated | AssetSet lifecycle |
| AudienceInsightsService | Integrated / access-controlled | public insight RPCs; Google allowlist required |
| AudienceService | Integrated | modern Audience lifecycle with CUSTOMER/ASSET_GROUP scope guards |
| AutomaticallyCreatedAssetRemovalService | Integrated | campaign auto-created asset removal |
| BatchJobService | Integrated | controlled manifest, run, status and row results |
| BenchmarksService | Integrated / access-controlled | public benchmark RPCs; Google allowlist required |
| BiddingDataExclusionService | Integrated | data exclusions |
| BiddingSeasonalityAdjustmentService | Integrated | seasonality adjustments |
| BiddingStrategyService | Integrated | portfolio bidding strategies |
| BillingSetupService | Integrated / access-controlled | create/cancel billing setup; monthly-invoicing eligibility applies |
| BrandSuggestionService | Integrated | verified brand suggestions |
| CampaignAssetService | Integrated | campaign asset links |
| CampaignAssetSetService | Integrated | campaign AssetSet links |
| CampaignBidModifierService | Integrated | CALLS interaction modifier read/update/remove |
| CampaignBudgetService | Integrated | daily/shared budgets |
| CampaignConversionGoalService | Integrated | campaign goal biddability |
| CampaignCriterionService | Integrated | targeting (incl. positive placements), negatives, audience exclusions, schedules (add/update/remove), geo, languages, webpage (DSA) targets, frequency caps on Campaign |
| CampaignCustomizerService | Integrated | campaign customizers |
| CampaignDraftService | Integrated | create/rename/promote/errors/remove |
| CampaignGoalConfigService | Integrated | v25 goal config |
| CampaignGroupService | Integrated | campaign-group lifecycle |
| CampaignLabelService | Integrated | campaign labels |
| CampaignService | Integrated | campaign lifecycle, app campaigns (MULTI_CHANNEL + app_campaign_setting), DSA campaigns (dynamic_search_ads_setting), tracking URL options, ad rotation, EnablePMaxBrandGuidelines |
| CampaignSharedSetService | Integrated | shared negative-list attachment |
| ContentCreatorInsightsService | Integrated / access-controlled | creator + trending insights; Google allowlist required |
| ConversionActionService | Integrated | conversion-action lifecycle |
| ConversionAdjustmentUploadService | Integrated | retractions/restatements |
| ConversionCustomVariableService | Integrated | custom-variable lifecycle |
| ConversionGoalCampaignConfigService | Integrated | conversion-goal campaign config |
| ConversionUploadService | Integrated | offline/enhanced/call conversions, GDPR consent on uploads |
| ConversionValueRuleService | Integrated | value-rule lifecycle |
| ConversionValueRuleSetService | Integrated | value-rule-set lifecycle |
| CustomAudienceService | Integrated | CustomAudience lifecycle |
| CustomConversionGoalService | Integrated | custom goal lifecycle |
| CustomInterestService | Integrated | CustomInterest lifecycle |
| CustomerAssetService | Integrated | account-scope asset links |
| CustomerAssetSetService | Integrated | account-scope AssetSet links |
| CustomerClientLinkService | Integrated | manager → client invite/unlink flow with validated cross-account exception |
| CustomerConversionGoalService | Integrated | customer conversion goals |
| CustomerCustomizerService | Integrated | customer customizers |
| CustomerLabelService | Integrated | manager/customer labels |
| CustomerManagerLinkService | Integrated | accept/decline/move/unlink manager relationships using the v25 singular mutate RPC with `operations[]` |
| CustomerNegativeCriterionService | Integrated | account-level placement/app/content/IP/shared-list exclusions |
| CustomerService | Integrated | accessible customers, create client, mutable operational settings, tracking URL options |
| CustomerSkAdNetworkConversionValueSchemaService | Integrated / specialized | schema visibility via GAQL + capability explanation; generic mutation intentionally not exposed because the public v25 resource documents `schema` as output-only |
| CustomerUserAccessInvitationService | Integrated | user invitations |
| CustomerUserAccessService | Integrated | roles/access removal |
| CustomizerAttributeService | Integrated | customizer definitions |
| DataLinkService | Integrated | Google Ads data-link lifecycle |
| ExperimentArmService | Integrated | create/update/remove + atomic two-arm traffic split |
| ExperimentService | Integrated | mutate/schedule/errors/promote/graduate/end |
| GeoTargetConstantService | Integrated | geo lookup/resolution |
| GoalService | Integrated | v25 unified acquisition/retention/loyalty goals |
| GoogleAdsFieldService | Integrated | field metadata get/search |
| GoogleAdsService | Integrated | SearchStream + typed atomic Mutate + GAQL fallback |
| IdentityVerificationService | Integrated / access-controlled | get/start identity verification; account eligibility applies |
| IncentiveService | Integrated / access-controlled | fetch/apply incentives; Google explicitly requires allowlisting |
| InvoiceService | Integrated / access-controlled | invoice retrieval; billing eligibility applies |
| KeywordPlanAdGroupKeywordService | Integrated | persistent plan positive/negative keywords |
| KeywordPlanAdGroupService | Integrated | persistent plan ad groups |
| KeywordPlanCampaignKeywordService | Integrated | persistent plan campaign negatives |
| KeywordPlanCampaignService | Integrated | persistent plan campaigns |
| KeywordPlanIdeaService | Integrated | ideas, historical metrics, forecast metrics |
| KeywordPlanService | Integrated | persistent plan lifecycle |
| KeywordThemeConstantService | Integrated | Smart Campaign theme suggestions |
| LabelService | Integrated | label lifecycle |
| LocalServicesLeadService | Integrated / access-controlled | leads, conversations, feedback; Local Services account eligibility applies |
| MultiPartyAuthReviewService | Integrated / access-controlled | beta approve/reject/revoke review workflow |
| OfflineUserDataJobService | Integrated / access-controlled | Customer Match jobs; account/data-use eligibility applies |
| PaymentsAccountService | Integrated / access-controlled | payments-account discovery |
| ProductLinkInvitationService | Integrated | create/accept/reject/revoke, with Merchant Center exception respected |
| ProductLinkService | Integrated | Merchant/Ads/Data Partner active links |
| ReachPlanService | Integrated / access-controlled | all six public v25 planning RPCs; Google requires a ReachPlan-allowlisted developer token/account |
| RecommendationService | Integrated | list/generate/apply/dismiss |
| RecommendationSubscriptionService | Integrated | auto-apply subscription enable/pause |
| RemarketingActionService | Integrated | action lifecycle + Google tag snippets |
| ReservationService | **Not publicly callable** | Google explicitly documents this service as not publicly available |
| ShareablePreviewService | Integrated | PMax asset-group and supported YouTube previews |
| SharedCriterionService | Integrated | shared negative criteria |
| SharedSetService | Integrated | shared sets/negative lists |
| SmartCampaignSettingService | Integrated | update settings + GetSmartCampaignStatus |
| SmartCampaignSuggestService | Integrated | keyword, budget and ad suggestions |
| ThirdPartyAppAnalyticsLinkService | Integrated | link/status/shareable-ID lifecycle |
| TravelAssetSuggestionService | Integrated | Travel asset suggestions |
| UserDataService | Integrated / access-controlled | small Customer Match uploads, PII kept out of audit payload |
| UserListCustomerTypeService | Integrated | new/existing customer assignments |
| UserListService | Integrated | remarketing and Customer Match list lifecycle |
| YouTubeVideoUploadService | Integrated / access-controlled | upload/status/update/remove; product/account eligibility applies |

## Explicit v25 removals and migrations

Google Ads API v25 removed the legacy `CustomerLifecycleGoalService` and
`CampaignLifecycleGoalService`. This MCP does **not** emulate those deleted
contracts. Acquisition, retention and loyalty operations use the v25 unified
`GoalService` / campaign-goal configuration model.

Smart Campaigns remain supported in v25. **Smart Shopping** is the obsolete
workflow; supported retail automation should use Performance Max.

## Specialized SKAdNetwork boundary

Google publishes `MutateCustomerSkAdNetworkConversionValueSchema`, but the public
v25 resource contract marks both `resource_name` and `schema` as output-only.
Because of that mismatch, 0.16.0 does not expose a generic dict-to-protobuf schema
writer. The MCP exposes the schema read surface and an explicit capability result
instead of presenting an undocumented write path as production-safe coverage.

This is a deliberate safety boundary, not an untracked service gap.

## Coverage boundaries

“Integrated” does not mean Google grants every account permission to every
feature. Reach Plan, Incentives, closed-beta generation and several insight
surfaces require explicit Google allowlisting. Billing, Customer Match, Local
Services, Identity Verification, YouTube upload and similar products can also
return Google authorization/eligibility errors for accounts that lack the
relevant capability.

The MCP intentionally does not expose an unrestricted arbitrary protobuf mutation
endpoint. High-impact operations use typed tools or constrained protobuf-JSON
wrappers with strict parsing, customer ownership checks, confirmation and audit.
This is a safety boundary, not a coverage gap.

## Production invariants in 0.16.0

1. Reads and writes pass the deployment customer allowlist when configured.
2. Mutations recursively inspect customer-scoped resource references, including
   references inside CREATE operations.
3. Legitimate manager/client linking is a narrow exception: every referenced
   customer still has to be explicitly allowed.
4. Pending writes are durable across restart when using the built-in SQLite audit
   backend; replay arguments are encrypted at rest.
5. Sensitive data tools record counts/consent/metadata in the audit log rather
   than raw Customer Match identifiers.
6. Spend, destructive and sensitive operations remain separately gated even when
   standard auto-approve is enabled.
7. Audience CUSTOMER/ASSET_GROUP naming rules are validated before mutation.
8. Undocumented SKAdNetwork schema writers are blocked by regression guards.

Last audited against Google Ads API v25 reference: **2026-08-20**.
