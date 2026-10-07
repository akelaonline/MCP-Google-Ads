import pytest

from mkt_measurement_ops.gtm_installer import GTMDriftError, GTMTrackingInstaller


class _FakeWriter:
    def __init__(self):
        self.triggers = []
        self.tags = []
        self.next_trigger = 1
        self.next_tag = 1

    def list_triggers(self, *_):
        return list(self.triggers)

    def list_tags(self, *_):
        return list(self.tags)

    def enable_built_in_variables(self, *args):
        return {"builtInVariable": [{"type": item} for item in args[-1]]}

    def create_trigger(self, *args):
        body = dict(args[-1])
        body["triggerId"] = str(self.next_trigger)
        self.next_trigger += 1
        self.triggers.append(body)
        return body

    def create_tag(self, *args):
        body = dict(args[-1])
        body["tagId"] = str(self.next_tag)
        self.next_tag += 1
        self.tags.append(body)
        return body


def test_standard_event_install_is_idempotent() -> None:
    writer = _FakeWriter()
    installer = GTMTrackingInstaller(writer)

    first = installer.install_standard_click_event("1", "2", "3", event_name="phone_click", measurement_id="G-ABC123")
    second = installer.install_standard_click_event("1", "2", "3", event_name="phone_click", measurement_id="G-ABC123")

    assert first["created"] == {"trigger": True, "tag": True}
    assert second["created"] == {"trigger": False, "tag": False}
    assert len(writer.triggers) == 1
    assert len(writer.tags) == 1


def test_existing_wrong_trigger_type_fails_as_drift() -> None:
    writer = _FakeWriter()
    writer.triggers.append({"name": "MKT - Phone Click", "type": "pageview", "triggerId": "99"})
    installer = GTMTrackingInstaller(writer)

    with pytest.raises(GTMDriftError, match="exists with type"):
        installer.install_standard_click_event("1", "2", "3", event_name="phone_click", measurement_id="G-ABC123")


def test_google_tag_install_is_idempotent() -> None:
    writer = _FakeWriter()
    installer = GTMTrackingInstaller(writer)

    first = installer.install_google_tag("1", "2", "3", tag_id="G-ABC123")
    second = installer.install_google_tag("1", "2", "3", tag_id="G-ABC123")

    assert first["created"] == {"trigger": True, "tag": True}
    assert second["created"] == {"trigger": False, "tag": False}


def test_provider_form_install_is_idempotent() -> None:
    writer = _FakeWriter()
    installer = GTMTrackingInstaller(writer)

    first = installer.install_provider_form_event(
        "1", "2", "3",
        provider="contactform7",
        measurement_id="G-ABC123",
    )
    second = installer.install_provider_form_event(
        "1", "2", "3",
        provider="contactform7",
        measurement_id="G-ABC123",
    )

    assert first["created"]["listener"] is True
    assert first["created"]["event_tag"] is True
    assert second["created"]["listener"] is False
    assert second["created"]["event_tag"] is False
    assert len(writer.triggers) == 2
    assert len(writer.tags) == 2


def test_native_form_install_is_idempotent() -> None:
    writer = _FakeWriter()
    installer = GTMTrackingInstaller(writer)

    first = installer.install_native_form_event(
        "1", "2", "3",
        measurement_id="G-ABC123",
        form_id="contact-form",
        page_path="/contact",
    )
    second = installer.install_native_form_event(
        "1", "2", "3",
        measurement_id="G-ABC123",
        form_id="contact-form",
        page_path="/contact",
    )

    assert first["created"] == {"trigger": True, "tag": True}
    assert second["created"] == {"trigger": False, "tag": False}


def test_existing_same_name_different_filter_fails_as_drift() -> None:
    writer = _FakeWriter()
    writer.triggers.append(
        {
            "name": "MKT - Phone Click",
            "type": "linkClick",
            "triggerId": "99",
            "filter": [],
        }
    )
    installer = GTMTrackingInstaller(writer)

    with pytest.raises(GTMDriftError, match="configuration drift"):
        installer.install_standard_click_event(
            "1", "2", "3",
            event_name="phone_click",
            measurement_id="G-ABC123",
        )


def test_multiple_native_forms_can_share_same_ga4_event_without_name_collision() -> None:
    writer = _FakeWriter()
    installer = GTMTrackingInstaller(writer)

    installer.install_native_form_event(
        "1", "2", "3",
        measurement_id="G-ABC123",
        event_name="generate_lead",
        form_id="contact-form",
    )
    installer.install_native_form_event(
        "1", "2", "3",
        measurement_id="G-ABC123",
        event_name="generate_lead",
        form_id="quote-form",
    )

    assert len(writer.triggers) == 2
    assert len(writer.tags) == 2
    assert writer.tags[0]["name"] != writer.tags[1]["name"]
    assert all(
        any(
            parameter.get("key") == "eventName" and parameter.get("value") == "generate_lead"
            for parameter in tag["parameter"]
        )
        for tag in writer.tags
    )


def test_different_data_layer_sources_can_map_to_same_ga4_event() -> None:
    writer = _FakeWriter()
    installer = GTMTrackingInstaller(writer)

    installer.install_custom_event(
        "1", "2", "3",
        measurement_id="G-ABC123",
        data_layer_event="contact_success",
        ga4_event_name="generate_lead",
    )
    installer.install_custom_event(
        "1", "2", "3",
        measurement_id="G-ABC123",
        data_layer_event="booking_success",
        ga4_event_name="generate_lead",
    )

    assert len(writer.triggers) == 2
    assert len(writer.tags) == 2
    assert writer.tags[0]["name"] != writer.tags[1]["name"]
