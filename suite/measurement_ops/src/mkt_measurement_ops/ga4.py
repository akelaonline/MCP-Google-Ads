from __future__ import annotations

from typing import Any

from .credentials import load_readonly_credentials

ANALYTICS_READONLY_SCOPE = "https://www.googleapis.com/auth/analytics.readonly"


def _oauth_credentials():
    return load_readonly_credentials("ga4")


class GA4ReadOnly:
    """Read-only GA4 Data API wrapper used for runtime verification."""

    def __init__(self, client: Any) -> None:
        self._client = client

    @classmethod
    def from_env(cls) -> "GA4ReadOnly":
        from google.analytics.data_v1beta import BetaAnalyticsDataClient

        return cls(BetaAnalyticsDataClient(credentials=_oauth_credentials()))

    def realtime_events(self, property_id: str) -> dict[str, int]:
        from google.analytics.data_v1beta.types import Dimension, Metric, RunRealtimeReportRequest

        request = RunRealtimeReportRequest(
            property=f"properties/{property_id}",
            dimensions=[Dimension(name="eventName")],
            metrics=[Metric(name="eventCount")],
        )
        response = self._client.run_realtime_report(request)

        events: dict[str, int] = {}
        for row in response.rows:
            if not row.dimension_values or not row.metric_values:
                continue
            name = row.dimension_values[0].value
            raw_count = row.metric_values[0].value
            try:
                count = int(float(raw_count))
            except (TypeError, ValueError):
                count = 0
            events[name] = events.get(name, 0) + count
        return events

    def verify_events(self, property_id: str, expected_events: list[str]) -> dict:
        events = self.realtime_events(property_id)
        normalized = list(dict.fromkeys(event.strip() for event in expected_events if event.strip()))
        checks = [
            {
                "event_name": event,
                "seen": events.get(event, 0) > 0,
                "event_count": events.get(event, 0),
            }
            for event in normalized
        ]
        return {
            "property_id": property_id,
            "passed": bool(checks) and all(check["seen"] for check in checks),
            "checks": checks,
            "realtime_events": events,
        }
