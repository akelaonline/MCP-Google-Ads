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

    def list_property_summaries(self) -> list[dict]:
        rows: list[dict] = []
        page_token: str | None = None
        while True:
            kwargs: dict[str, Any] = {}
            if page_token:
                kwargs["pageToken"] = page_token
            response = self._service.accountSummaries().list(**kwargs).execute()
            for account in response.get("accountSummaries", []):
                for prop in account.get("propertySummaries", []):
                    rows.append(
                        {
                            "account": account.get("account"),
                            "account_display_name": account.get("displayName"),
                            "property": prop.get("property"),
                            "property_display_name": prop.get("displayName"),
                        }
                    )
            page_token = response.get("nextPageToken")
            if not page_token:
                return rows

    def discover_property_by_measurement_id(self, measurement_id: str) -> dict:
        wanted = measurement_id.strip().upper()
        if not wanted:
            raise ValueError("measurement_id is required")
        matches: list[dict] = []
        for summary in self.list_property_summaries():
            property_path = str(summary.get("property") or "")
            property_id = property_path.split("/")[-1]
            if not property_id:
                continue
            for stream in self.list_web_streams(property_id):
                web = stream.get("webStreamData", {})
                if str(web.get("measurementId") or "").upper() == wanted:
                    matches.append(
                        {
                            **summary,
                            "property_id": property_id,
                            **self._normalized(stream),
                        }
                    )
        if not matches:
            raise LookupError(f"no accessible GA4 web stream matched {measurement_id!r}")
        if len(matches) > 1:
            raise LookupError(f"multiple accessible GA4 web streams matched {measurement_id!r}")
        return matches[0]

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
