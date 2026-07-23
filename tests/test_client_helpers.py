from google_ads_mcp.client import from_micros, micros


def test_micros_roundtrip():
    assert micros(25.50) == 25_500_000
    assert micros(1) == 1_000_000
    assert from_micros(25_500_000) == 25.50


def test_micros_rounding():
    # Guard against float artifacts like 10.1 * 1_000_000 == 10099999.999...
    assert micros(10.1) == 10_100_000
