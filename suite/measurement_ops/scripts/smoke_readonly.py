"""Opt-in, authenticated read-only connection smoke for GTM and GA4.

Prints only sanitized counts. Never modifies Google resources or prints tokens.
"""

from __future__ import annotations

import argparse

from mkt_measurement_ops.credentials import credential_configuration_status
from mkt_measurement_ops.ga4_admin import GA4AdminReadOnly
from mkt_measurement_ops.gtm import GoogleTagManagerReadOnly
from mkt_measurement_ops.settings import MeasurementSettings


def check_readonly_connections(gtm: GoogleTagManagerReadOnly, ga4: GA4AdminReadOnly) -> dict:
    # These operations only list accessible resources. Nothing is created,
    # deleted, tagged, previewed or published.
    accounts = gtm.list_accounts()
    properties = ga4.list_property_summaries()
    return {
        "gtm_accounts_count": len(accounts),
        "ga4_properties_count": len(properties),
        "api_readonly_verified": True,
        "production_tracking_verified": False,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Read-only GTM/GA4 API smoke; requires explicit confirmation."
    )
    parser.add_argument(
        "--confirm-readonly",
        action="store_true",
        help="Authorize real read-only Google API calls with the configured test identity.",
    )
    args = parser.parse_args()
    if not args.confirm_readonly:
        parser.error("pass --confirm-readonly to permit real read-only API calls")

    settings = MeasurementSettings.from_env()
    if settings.gtm_enable_preview or settings.gtm_enable_writes or settings.gtm_enable_publish:
        raise PermissionError("all GTM preview/write/publish capability flags must be false")

    configured = credential_configuration_status()
    if not all(configured.values()):
        raise RuntimeError(
            "GTM and GA4 read-only OAuth are not both configured; "
            "run scripts/authorize_readonly.py on the local desktop"
        )

    print("Running ONLY GTM accounts.list and GA4 accountSummaries.list")
    result = check_readonly_connections(
        GoogleTagManagerReadOnly.from_env(),
        GA4AdminReadOnly.from_env(),
    )
    print(f"GTM accessible account count: {result['gtm_accounts_count']}")
    print(f"GA4 accessible property count: {result['ga4_properties_count']}")
    print("READONLY GOOGLE API DISCOVERY PASS")
    print("This does NOT certify site tagging, consent, conversions or deployment.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
