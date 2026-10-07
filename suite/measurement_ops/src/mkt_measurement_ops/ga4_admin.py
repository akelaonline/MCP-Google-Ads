from __future__ import annotations

from typing import Any
from urllib.parse import urlparse

from .ga4 import _oauth_credentials


def _host(value: str) -> str:
    raw = (value or "").strip()
    if not raw:
        return ""
    parsed = urlparse(raw if "://" in raw else f"https://{raw}")
    host = (parsed.hostname or "").lower().rstrip(".")
    return host[4:] if host.startswith("www.") else host


class GA4AdminReadOnly:
    """Read-only GA4 Admin API discovery for properties and web data streams."""

    def __init__(self, service: Any) -> None:
        self._service = service

    @classmethod
    def from_env(cls) -> "GA4AdminReadOnly":
        from googleapiclient.discovery import build

        return cls(
            build(
                "analyticsadmin",
                "v1beta",
                credentials=_oauth_credentials(),
                cache_discovery=False,
            )
        )

    def list_data_streams(self, property_id: str) -> list[dict]:
        rows: list[dict] = []
        page_token: str | None = None
        while True:
            kwargs: dict[str, Any] = {"parent": f"properties/{property_id}"}
            if page_token:
                kwargs["pageToken"] = page_token
            response = self._service.properties().dataStreams().list(**kwargs).execute()
            rows.extend(response.get("dataStreams", []))
            page_token = response.get("nextPageToken")
            if not page_token:
                return rows

    def list_web_streams(self, property_id: str) -> list[dict]:
        return [
            stream
            for stream in self.list_data_streams(property_id)
            if stream.get("type") == "WEB_DATA_STREAM" and stream.get("webStreamData")
        ]

    def resolve_web_stream(self, property_id: str, domain: str | None = None) -> dict:
        streams = self.list_web_streams(property_id)
        if not streams:
            raise LookupError(f"GA4 property {property_id} has no web data stream")

        if domain:
            wanted = _host(domain)
            matches = [
                stream
                for stream in streams
                if _host(stream.get("webStreamData", {}).get("defaultUri", "")) == wanted
            ]
            if len(matches) == 1:
                return self._normalized(matches[0])
            if len(matches) > 1:
                raise LookupError(f"multiple GA4 web streams match domain {domain!r}")
            if len(streams) > 1:
                raise LookupError(
                    f"no GA4 web stream matches {domain!r}; property has {len(streams)} web streams"
                )

        if len(streams) != 1:
            raise LookupError(
                f"GA4 property {property_id} has {len(streams)} web streams; domain is required to disambiguate"
            )
        return self._normalized(streams[0])

    @staticmethod
    def _normalized(stream: dict) -> dict:
        web = stream.get("webStreamData", {})
        measurement_id = web.get("measurementId")
        if not measurement_id:
            raise LookupError(f"web stream {stream.get('name', '<unknown>')} has no measurementId")
        return {
            "name": stream.get("name"),
            "display_name": stream.get("displayName"),
            "default_uri": web.get("defaultUri"),
            "measurement_id": measurement_id,
        }
