"""OAuth2 helper for Google Ads and optional Data Manager credentials.

Examples:

    python -m google_ads_mcp.auth --generate-refresh-token
    python -m google_ads_mcp.auth --generate-refresh-token --include-data-manager

The Data Manager API scope is sensitive and may require Google OAuth app
verification for public user-account OAuth clients. Existing Google Ads-only
users can keep their current refresh token unchanged.
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

_ENV_FILE = os.environ.get("GOOGLE_ADS_MCP_ENV_FILE")
if _ENV_FILE:
    load_dotenv(_ENV_FILE)
else:
    load_dotenv(Path.cwd() / ".env")

GOOGLE_ADS_SCOPE = "https://www.googleapis.com/auth/adwords"
DATA_MANAGER_SCOPE = "https://www.googleapis.com/auth/datamanager"
CLOUD_PLATFORM_SCOPE = "https://www.googleapis.com/auth/cloud-platform"
MERCHANT_CENTER_SCOPE = "https://www.googleapis.com/auth/content"


def generate_refresh_token(
    *, include_data_manager: bool = False, include_merchant_center: bool = False
) -> None:
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        print(
            "Missing dependency. Install it with:\n  pip install -e '.[auth]'",
            file=sys.stderr,
        )
        sys.exit(1)

    client_id = os.environ.get("GOOGLE_ADS_CLIENT_ID")
    client_secret = os.environ.get("GOOGLE_ADS_CLIENT_SECRET")
    if not client_id or not client_secret:
        print(
            "Set GOOGLE_ADS_CLIENT_ID and GOOGLE_ADS_CLIENT_SECRET "
            "(env vars or .env) before running this.",
            file=sys.stderr,
        )
        sys.exit(1)

    scopes = [GOOGLE_ADS_SCOPE]
    if include_data_manager:
        scopes.extend([DATA_MANAGER_SCOPE, CLOUD_PLATFORM_SCOPE])
    if include_merchant_center:
        scopes.append(MERCHANT_CENTER_SCOPE)

    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }

    flow = InstalledAppFlow.from_client_config(client_config, scopes=scopes)
    credentials = flow.run_local_server(
        port=0,
        access_type="offline",
        prompt="consent",
    )

    if not credentials.refresh_token:
        print(
            "OAuth completed but Google returned no refresh token. Revoke the app's "
            "existing grant and retry so Google can issue a new offline grant.",
            file=sys.stderr,
        )
        sys.exit(1)

    print("\nSuccess. Add this to your .env file:\n")
    print(f"GOOGLE_ADS_REFRESH_TOKEN={credentials.refresh_token}")
    if include_data_manager:
        print(f"GOOGLE_ADS_DATA_MANAGER_REFRESH_TOKEN={credentials.refresh_token}")
        print(
            "\nAlso set GOOGLE_ADS_DATA_MANAGER_PROJECT_ID to the Google Cloud "
            "project where Data Manager API is enabled."
        )
    if include_merchant_center:
        print(
            "\nThis token also covers Merchant Center (content scope). It is used "
            "automatically as GOOGLE_ADS_REFRESH_TOKEN unless you set a separate "
            "GOOGLE_MERCHANT_CENTER_REFRESH_TOKEN. Also set GOOGLE_MERCHANT_CENTER_ID "
            "to your default Merchant Center account ID."
        )
    print()


def main() -> None:
    parser = argparse.ArgumentParser(description="Google Ads MCP auth helper")
    parser.add_argument(
        "--generate-refresh-token",
        action="store_true",
        help="Run the OAuth desktop flow and print a refresh token.",
    )
    parser.add_argument(
        "--include-data-manager",
        action="store_true",
        help=(
            "Request Google Ads + Data Manager + Cloud Platform scopes. Use this "
            "for new Customer Match integrations that need Data Manager API."
        ),
    )
    parser.add_argument(
        "--include-merchant-center",
        action="store_true",
        help=(
            "Also request the content scope for Google Merchant Center (Merchant "
            "API): account status, products, feeds and reports."
        ),
    )
    args = parser.parse_args()

    if args.include_data_manager and not args.generate_refresh_token:
        parser.error("--include-data-manager requires --generate-refresh-token")
    if args.include_merchant_center and not args.generate_refresh_token:
        parser.error("--include-merchant-center requires --generate-refresh-token")

    if args.generate_refresh_token:
        generate_refresh_token(
            include_data_manager=args.include_data_manager,
            include_merchant_center=args.include_merchant_center,
        )
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
