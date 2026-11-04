"""Non-network, non-secret preflight for the GTM + GA4 read-only E2E."""

from __future__ import annotations

import json

from mkt_measurement_ops.credentials import credential_configuration_status
from mkt_measurement_ops.settings import MeasurementSettings


def assess_local_readiness() -> dict:
    settings = MeasurementSettings.from_env()
    mutations_off = not any(
        (settings.gtm_enable_preview, settings.gtm_enable_writes, settings.gtm_enable_publish)
    )
    status = {
        "gtm_preview_disabled": not settings.gtm_enable_preview,
        "gtm_writes_disabled": not settings.gtm_enable_writes,
        "gtm_publish_disabled": not settings.gtm_enable_publish,
        "gtm_readonly_configured": False,
        "ga4_readonly_configured": False,
        "google_api_tested": False,
        "site_tracking_verified": False,
    }
    try:
        status.update(credential_configuration_status())
        credential_error = None
    except (OSError, ValueError, PermissionError) as exc:
        # Expose only the error category. OAuth secrets, content and paths
        # must never end up in diagnostics, logs or MCP tool responses.
        credential_error = type(exc).__name__
    return {
        "ready_for_readonly_smoke": (
            mutations_off
            and status["gtm_readonly_configured"]
            and status["ga4_readonly_configured"]
            and credential_error is None
        ),
        "checks": status,
        "credential_error_type": credential_error,
    }


def main() -> int:
    report = assess_local_readiness()
    print(json.dumps(report, sort_keys=True))
    if report["ready_for_readonly_smoke"]:
        print("LOCAL OAUTH PREFLIGHT PASS — live Google API access NOT YET tested")
        return 0
    print("LOCAL OAUTH PREFLIGHT BLOCKED — no Google API calls made")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
