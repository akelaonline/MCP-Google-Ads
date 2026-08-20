from google_ads_mcp.safety import RiskLevel, classify_risk


def test_sensitive_identity_and_data_operations():
    assert classify_risk("start_identity_verification", {}) is RiskLevel.SENSITIVE
    assert (
        classify_risk("update_customer_skad_network_conversion_value_schema", {})
        is RiskLevel.SENSITIVE
    )
    assert classify_risk("upload_user_data_small_batch", {}) is RiskLevel.SENSITIVE
    assert classify_risk("apply_google_ads_incentive", {}) is RiskLevel.SENSITIVE


def test_spend_and_delivery_operations():
    for tool in (
        "add_customer_negative_criterion",
        "add_asset_group_signal",
        "replace_asset_group_listing_filter_tree",
        "create_experiment_arms",
        "update_experiment_arm",
        "create_conversion_value_rule",
        "update_conversion_value_rule",
        "update_smart_campaign_setting",
    ):
        assert classify_risk(tool, {}) is RiskLevel.SPEND, tool


def test_account_link_and_mpa_terminal_states_are_destructive():
    assert (
        classify_risk("set_account_link_status", {"status": "ENABLED"})
        is RiskLevel.SENSITIVE
    )
    assert (
        classify_risk("set_account_link_status", {"status": "REMOVED"})
        is RiskLevel.DESTRUCTIVE
    )
    assert (
        classify_risk("resolve_multi_party_auth_review", {"status": "APPROVED"})
        is RiskLevel.SENSITIVE
    )
    assert (
        classify_risk("resolve_multi_party_auth_review", {"status": "REVOKED"})
        is RiskLevel.DESTRUCTIVE
    )
