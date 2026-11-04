"""Authorize one GTM or GA4 read-only OAuth grant on the user's own desktop.

The browser opens locally; do NOT execute from a headless/cloud VM unless the
user has deliberately configured a secure local callback tunnel.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from mkt_measurement_ops.credentials import (
    GOOGLE_TOKEN_URI,
    default_credential_path,
    required_scope,
    save_readonly_credentials,
)


def _validate_desktop_client(path: Path) -> None:
    if path.is_symlink() or not path.is_file():
        raise ValueError("client secrets must be a regular JSON file")
    payload = json.loads(path.read_text(encoding="utf-8"))
    installed = payload.get("installed") if isinstance(payload, dict) else None
    if not isinstance(installed, dict) or not installed.get("client_id") or not installed.get("client_secret"):
        raise ValueError("Google Cloud OAuth client must have application type Desktop app")
    allowed_google_authorization_urls = {
        "https://accounts.google.com/o/oauth2/auth",
        "https://accounts.google.com/o/oauth2/v2/auth",
    }
    if installed.get("auth_uri") not in allowed_google_authorization_urls:
        raise ValueError("Desktop OAuth authorization URL must point to Google")
    if installed.get("token_uri") != GOOGLE_TOKEN_URI:
        raise ValueError("Desktop OAuth token URL must point to Google's official endpoint")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Consent a dedicated read-only OAuth grant using a desktop browser."
    )
    parser.add_argument("--provider", choices=["gtm", "ga4"], required=True)
    parser.add_argument(
        "--client-secrets",
        type=Path,
        required=True,
        help="Absolute path to Google Cloud Desktop OAuth client JSON; never commit this file.",
    )
    parser.add_argument(
        "--replace",
        action="store_true",
        help="Explicitly rotate/replace an existing local grant.",
    )
    args = parser.parse_args()

    client_secrets = args.client_secrets.expanduser()
    _validate_desktop_client(client_secrets)
    destination = default_credential_path(args.provider)
    if destination.exists() and not args.replace:
        raise FileExistsError(
            "a read-only grant already exists; choose --replace to authorize and rotate it"
        )

    from google_auth_oauthlib.flow import InstalledAppFlow

    scope = required_scope(args.provider)
    print(f"Authorizing {args.provider.upper()} with ONE read-only scope.")
    print("Google consent opens in the LOCAL desktop browser (127.0.0.1).")
    print("No tokens, authorization codes or consent URLs will be printed by this helper.")
    flow = InstalledAppFlow.from_client_secrets_file(
        str(client_secrets), scopes=[scope]
    )
    credentials = flow.run_local_server(
        host="127.0.0.1",
        port=0,
        open_browser=True,
        access_type="offline",
        prompt="consent",
        timeout_seconds=300,
        authorization_prompt_message=None,
    )
    if not credentials.refresh_token:
        raise RuntimeError(
            "Google returned no refresh token; check Desktop OAuth consent and try again"
        )

    # to_json serializes the refresh token. Never print it or write it to repo.
    target = save_readonly_credentials(
        args.provider, credentials.to_json(), replace=args.replace
    )
    print(f"Read-only OAuth configured for {args.provider.upper()}.")
    print(f"Private local grant: {target}")
    print("Grant can be revoked in Google Account security settings.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
