from __future__ import annotations

from google_ads_mcp.invocation import canonical_tool_modules, legacy_tool_modules


def test_known_legacy_duplicate_tools_have_explicit_canonical_owners():
    assert canonical_tool_modules() == {
        "list_asset_group_signals": "google_ads_mcp.tools.pmax_signals_listing",
        "add_asset_group_signal": "google_ads_mcp.tools.pmax_signals_listing",
        "list_asset_group_listing_filters": "google_ads_mcp.tools.pmax_signals_listing",
        # The typed condition-based create is canonical; the protobuf-JSON
        # power-user variant lives under create_conversion_value_rule_from_json.
        "create_conversion_value_rule": "google_ads_mcp.tools.conversions",
        # The richer read (owner_customer + condition objects) is canonical.
        "list_conversion_value_rules": "google_ads_mcp.tools.remaining_core_services",
    }


def test_declared_legacy_modules_match_actual_superseded_sources():
    assert legacy_tool_modules() == {
        "list_asset_group_signals": frozenset({"google_ads_mcp.tools.performance_max"}),
        "add_asset_group_signal": frozenset({"google_ads_mcp.tools.performance_max"}),
        "list_asset_group_listing_filters": frozenset(
            {"google_ads_mcp.tools.performance_max"}
        ),
        "create_conversion_value_rule": frozenset(
            {"google_ads_mcp.tools.remaining_core_services"}
        ),
        "list_conversion_value_rules": frozenset({"google_ads_mcp.tools.conversions"}),
    }
