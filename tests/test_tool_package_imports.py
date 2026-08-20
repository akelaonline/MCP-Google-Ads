from __future__ import annotations


def test_tool_package_imports_all_registered_modules():
    """Catch missing/renamed helpers that would break build_server tool registration."""
    from google_ads_mcp.tools import ALL_MODULES

    assert ALL_MODULES
    assert all(hasattr(module, "register") for module in ALL_MODULES)


def test_reporting_currency_helper_is_available():
    """Regression for the 0.16.0 from_micros startup/import failure."""
    from google_ads_mcp.client import from_micros, micros

    assert micros(25.50) == 25_500_000
    assert from_micros(25_500_000) == 25.5
