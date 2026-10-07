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
