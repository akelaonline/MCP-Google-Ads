from types import SimpleNamespace

from mkt_measurement_ops.ga4 import GA4ReadOnly


class _Client:
    def run_realtime_report(self, request):
        assert request.property == "properties/123"
        return SimpleNamespace(
            rows=[
                SimpleNamespace(
                    dimension_values=[SimpleNamespace(value="generate_lead")],
                    metric_values=[SimpleNamespace(value="2")],
                ),
                SimpleNamespace(
                    dimension_values=[SimpleNamespace(value="whatsapp_click")],
                    metric_values=[SimpleNamespace(value="1")],
                ),
            ]
        )


def test_realtime_event_verification() -> None:
    client = GA4ReadOnly(_Client())
    result = client.verify_events("123", ["generate_lead", "whatsapp_click"])

    assert result["passed"] is True
    assert result["realtime_events"]["generate_lead"] == 2


def test_verification_fails_when_expected_event_is_missing() -> None:
    client = GA4ReadOnly(_Client())
    result = client.verify_events("123", ["generate_lead", "phone_click"])

    assert result["passed"] is False
