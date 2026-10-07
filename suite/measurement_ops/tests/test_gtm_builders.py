import pytest

from mkt_measurement_ops.gtm_builders import (
    build_ga4_event_tag,
    build_standard_click_bundle,
    build_custom_event_trigger,
)


def test_whatsapp_bundle_is_scoped_to_whatsapp_urls() -> None:
    bundle = build_standard_click_bundle("whatsapp_click", "G-ABC123")
    trigger = bundle["trigger"]

    assert trigger["type"] == "linkClick"
    assert trigger["filter"][0]["type"] == "matchRegex"
    assert trigger["filter"][0]["parameter"][0]["value"] == "{{Click URL}}"
    assert bundle["required_built_in_variables"] == ["clickUrl"]


def test_ga4_event_tag_uses_event_settings_table() -> None:
    tag = build_ga4_event_tag(
        name="GA4 - Event - WhatsApp Click",
        measurement_id="G-ABC123",
        event_name="whatsapp_click",
        firing_trigger_id="99",
        event_parameters=[{"name": "click_url", "value": "{{Click URL}}"}],
    )

    table = next(param for param in tag["parameter"] if param.get("key") == "eventSettingsTable")
    assert tag["type"] == "gaawe"
    assert table["list"][0]["map"][0]["value"] == "click_url"


def test_custom_event_trigger_requires_name() -> None:
    with pytest.raises(ValueError, match="event_name"):
        build_custom_event_trigger(name="Lead", event_name="")
