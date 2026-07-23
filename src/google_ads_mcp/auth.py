"""OAuth2 helper: run this module directly to mint a refresh token.

    python -m google_ads_mcp.auth --generate-refresh-token

Requires GOOGLE_ADS_CLIENT_ID / GOOGLE_ADS_CLIENT_SECRET to already be set
(a Desktop-app OAuth client from Google Cloud Console). Opens a local
browser flow and prints the resulting refresh token — paste it into
GOOGLE_ADS_REFRESH_TOKEN in your .env file.
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

SCOPES = ["https://www.googleapis.com/auth/adwords"]


def generate_refresh_token() -> None:
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        print(
            "Missing dependency. Install it with:\n"
            "  pip install google-auth-oauthlib",
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

    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }

    flow = InstalledAppFlow.from_client_config(client_config, scopes=SCOPES)
    credentials = flow.run_local_server(port=0)

    print("\nSuccess. Add this to your .env file:\n")
    print(f"GOOGLE_ADS_REFRESH_TOKEN={credentials.refresh_token}\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Google Ads MCP auth helper")
    parser.add_argument(
        "--generate-refresh-token",
        action="store_true",
        help="Run the OAuth desktop flow and print a refresh token.",
    )
    args = parser.parse_args()

    if args.generate_refresh_token:
        generate_refresh_token()
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
