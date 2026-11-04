from __future__ import annotations

from urllib.parse import urlparse


def _hostname(value: str) -> str:
    parsed = urlparse(value)
    if parsed.scheme != "https" or not parsed.hostname:
        raise ValueError("browser evidence requires a full https URL")
    hostname = parsed.hostname.lower().rstrip(".")
    return hostname[4:] if hostname.startswith("www.") else hostname


def validated_browser_attestation(
    *,
    site_domain: str,
    page_url: str,
    registered_gtm_public_id: str,
    observed_gtm_public_id: str,
    expected_measurement_id: str,
    observed_measurement_id: str,
    expected_events: list[str],
    observed_network_events: list[str],
    consent_checked: bool,
) -> dict:
    """Validate operator-observed production QA metadata; not autonomous proof.

    This function deliberately never treats GA4 aggregate Realtime counts as
    browser-side evidence of a specific visit.
    """
    if _hostname(page_url) != site_domain.lower().removeprefix("www.").rstrip("."):
        raise ValueError("browser QA URL is not on the registered site")
    if not registered_gtm_public_id:
        raise ValueError("registered site is missing GTM public ID")
    if observed_gtm_public_id != registered_gtm_public_id:
        raise ValueError("observed GTM container does not match the registered site")
    if observed_measurement_id != expected_measurement_id:
        raise ValueError("observed GA4 Measurement ID does not match the registered property stream")
    if consent_checked is not True:
        raise ValueError("consent state must be checked before verifying production")
    required = {name.strip() for name in expected_events if name.strip()}
    observed = {name.strip() for name in observed_network_events if name.strip()}
    if not required:
        raise ValueError("production QA requires at least one expected event")
    missing = sorted(required - observed)
    if missing:
        raise ValueError(f"missing browser-observed GA4 network events: {', '.join(missing)}")
    return {
        "kind": "production_browser_attestation",
        "source": "operator_attested_browser_network",
        "passed": True,
        "page_url": page_url,
        "gtm_public_id": observed_gtm_public_id,
        "measurement_id": observed_measurement_id,
        "verified_events": sorted(required),
        "consent_checked": True,
        "automation_level": "manual_attestation",
    }
