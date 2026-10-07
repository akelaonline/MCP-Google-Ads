import pytest

from mkt_measurement_ops.ga4_admin import GA4AdminReadOnly


class _Request:
    def __init__(self, payload):
        self.payload = payload

    def execute(self):
        return self.payload


class _DataStreams:
    def __init__(self, pages):
        self.pages = pages
        self.calls = []

    def list(self, **kwargs):
        self.calls.append(kwargs)
        page = 1 if kwargs.get("pageToken") == "next" else 0
        return _Request(self.pages[page])


class _Properties:
    def __init__(self, pages):
        self._streams = _DataStreams(pages)

    def dataStreams(self):
        return self._streams


class _Service:
    def __init__(self, pages):
        self._properties = _Properties(pages)

    def properties(self):
        return self._properties


def _web(name, measurement_id, uri):
    return {
        "name": name,
        "type": "WEB_DATA_STREAM",
        "displayName": name,
        "webStreamData": {
            "measurementId": measurement_id,
            "defaultUri": uri,
        },
    }


def test_resolves_measurement_id_by_domain() -> None:
    service = _Service([
        {
            "dataStreams": [
                _web("properties/123/dataStreams/1", "G-ONE", "https://example.com"),
                _web("properties/123/dataStreams/2", "G-TWO", "https://other.com"),
            ]
        }
    ])
    admin = GA4AdminReadOnly(service)

    result = admin.resolve_web_stream("123", "www.example.com")

    assert result["measurement_id"] == "G-ONE"


def test_ambiguous_property_fails_without_domain() -> None:
    service = _Service([
        {
            "dataStreams": [
                _web("properties/123/dataStreams/1", "G-ONE", "https://example.com"),
                _web("properties/123/dataStreams/2", "G-TWO", "https://other.com"),
            ]
        }
    ])
    admin = GA4AdminReadOnly(service)

    with pytest.raises(LookupError, match="domain is required"):
        admin.resolve_web_stream("123")


def test_data_stream_pagination() -> None:
    service = _Service([
        {"dataStreams": [_web("stream/1", "G-ONE", "https://one.com")], "nextPageToken": "next"},
        {"dataStreams": [_web("stream/2", "G-TWO", "https://two.com")]},
    ])
    admin = GA4AdminReadOnly(service)

    rows = admin.list_data_streams("123")

    assert len(rows) == 2
    assert service._properties._streams.calls[1]["pageToken"] == "next"
