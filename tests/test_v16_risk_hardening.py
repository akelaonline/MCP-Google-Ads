from __future__ import annotations

import pytest

from google_ads_mcp.safety import RiskLevel, classify_risk


@pytest.mark.parametrize(
    "tool_name",
    [
        "add_location_targeting",
        "set_language_targeting",
        "add_placement_exclusion",
        "add_keywords",
        "update_keyword_match_type",
        "add_negative_keywords",
        "bulk_add_negative_keywords_multi_scope",
        "add_shared_negative_keywords",
        "attach_shared_negative_keyword_list_to_campaign",
        "attach_audience_to_ad_group",
        "add_in_market_or_affinity_audience",
        "add_topic_targeting",
        "create_conversion_action",
        "set_conversion_action_counting",
    ],
)
def test_delivery_or_optimization_changes_require_spend_approval(tool_name: str):
    assert classify_risk(tool_name, {}) is RiskLevel.SPEND


def test_existing_standard_creative_policy_stays_standard():
    assert classify_risk("create_callout_asset", {}) is RiskLevel.STANDARD
    assert classify_risk("create_sitelink_asset", {}) is RiskLevel.STANDARD


def test_status_and_sensitive_precedence_still_win():
    assert (
        classify_risk("bulk_update_campaign_status", {"status": "REMOVED"})
        is RiskLevel.DESTRUCTIVE
    )
    assert (
        classify_risk("upload_customer_match_members", {"status": "ENABLED"})
        is RiskLevel.SENSITIVE
    )
    assert (
        classify_risk("update_keyword_status", {"status": "ENABLED"})
        is RiskLevel.SPEND
    )
