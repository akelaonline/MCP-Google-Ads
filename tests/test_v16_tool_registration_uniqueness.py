from __future__ import annotations

from google_ads_mcp.invocation import canonical_tool_modules


def test_known_legacy_duplicate_tools_have_explicit_canonical_owners():
    assert canonical_tool_modules() == {
        "list_asset_group_signals": "google_ads_mcp.tools.pmax_signals_listing",
        "add_asset_group_signal": "google_ads_mcp.tools.pmax_signals_listing",
        "list_asset_group_listing_filters": "google_ads_mcp.tools.pmax_signals_listing",
        "list_conversion_value_rules": "google_ads_mcp.tools.remaining_core_services",
        "create_conversion_value_rule": "google_ads_mcp.tools.remaining_core_services",
    }
