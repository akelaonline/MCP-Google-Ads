import pytest

from mkt_measurement_ops.ga4_admin import GA4AdminReadOnly


class _DiscoveryAdmin(GA4AdminReadOnly):
    def __init__(self, summaries, streams):
        self.summaries = summaries
        self.streams = streams

    def list_property_summaries(self):
        return list(self.summaries)

    def list_web_streams(self, property_id):
        return list(self.streams.get(property_id, []))


def _stream(mid, uri):
    return {
        "name": "properties/x/dataStreams/1",
        "type": "WEB_DATA_STREAM",
        "displayName": uri,
        "webStreamData": {"measurementId": mid, "defaultUri": uri},
    }


def test_discovers_property_from_measurement_id() -> None:
    admin = _DiscoveryAdmin(
        [
            {"account": "accounts/1", "property": "properties/100", "property_display_name": "One"},
            {"account": "accounts/1", "property": "properties/200", "property_display_name": "Two"},
        ],
        {
            "100": [_stream("G-ONE", "https://one.com")],
            "200": [_stream("G-TWO", "https://two.com")],
        },
    )

    result = admin.discover_property_by_measurement_id("g-two")

    assert result["property_id"] == "200"
    assert result["measurement_id"] == "G-TWO"


def test_duplicate_measurement_id_fails_closed() -> None:
    admin = _DiscoveryAdmin(
        [
            {"account": "accounts/1", "property": "properties/100"},
            {"account": "accounts/2", "property": "properties/200"},
        ],
        {
            "100": [_stream("G-SAME", "https://one.com")],
            "200": [_stream("G-SAME", "https://two.com")],
        },
    )

    with pytest.raises(LookupError, match="multiple"):
        admin.discover_property_by_measurement_id("G-SAME")
