import pytest

from mkt_measurement_ops.gtm_builders import (
    build_ga4_event_tag,
    build_standard_click_bundle,
    build_custom_event_trigger,
    build_form_submit_trigger,
    provider_listener_html,
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


@pytest.mark.parametrize(
    ("provider", "signal"),
    [
        ("contactform7", "wpcf7mailsent"),
        ("gravityforms", "gform_confirmation_loaded"),
        ("wpforms", "wpformsAjaxSubmitSuccess"),
        ("elementor", "submit_success"),
        ("hubspot", "hsFormCallback"),
        ("typeform", "form-submit"),
        ("calendly", "calendly.event_scheduled"),
    ],
)
def test_provider_listener_recipes_are_deterministic(provider: str, signal: str) -> None:
    html = provider_listener_html(provider, "generate_lead")
    assert signal in html
    assert "generate_lead" in html
    assert "window.dataLayer" in html


def test_unknown_provider_fails_closed() -> None:
    with pytest.raises(ValueError, match="unsupported form provider"):
        provider_listener_html("mysteryforms", "generate_lead")


def test_native_form_trigger_scopes_by_form_and_page() -> None:
    trigger = build_form_submit_trigger(
        name="Lead Form",
        form_id="contact-form",
        page_path="/contact",
    )
    assert trigger["type"] == "formSubmission"
    assert len(trigger["filter"]) == 2
    assert trigger["waitForTags"]["value"] == "false"
    assert trigger["checkValidation"]["value"] == "false"
