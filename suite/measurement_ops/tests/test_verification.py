import pytest

from mkt_measurement_ops.verification import validated_browser_attestation


BASE = {
    "site_domain": "cambridge.com.ar",
    "page_url": "https://www.cambridge.com.ar/contact",
    "registered_gtm_public_id": "GTM-ABC123",
    "observed_gtm_public_id": "GTM-ABC123",
    "expected_measurement_id": "G-ABC123",
    "observed_measurement_id": "G-ABC123",
    "expected_events": ["generate_lead", "whatsapp_click"],
    "observed_network_events": ["whatsapp_click", "generate_lead"],
    "consent_checked": True,
}


def test_attestation_requires_matching_site_and_event_hits() -> None:
    result = validated_browser_attestation(**BASE)
    assert result["passed"] is True
    assert result["automation_level"] == "manual_attestation"


@pytest.mark.parametrize(
    ("override", "message"),
    [
        ({"page_url": "https://evil.example/contact"}, "registered site"),
        ({"observed_gtm_public_id": "GTM-WRONG"}, "GTM container"),
        ({"observed_measurement_id": "G-WRONG"}, "Measurement ID"),
        ({"observed_network_events": ["generate_lead"]}, "whatsapp_click"),
        ({"consent_checked": False}, "consent state"),
    ],
)
def test_attestation_fails_closed(override: dict, message: str) -> None:
    with pytest.raises(ValueError, match=message):
        validated_browser_attestation(**(BASE | override))
