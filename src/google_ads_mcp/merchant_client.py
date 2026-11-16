"""Minimal authenticated REST client for Google's Merchant API.

Google's legacy Content API for Shopping (``content.googleapis.com``) sunset on
2026-08-18; new integrations must use the Merchant API
(``merchantapi.googleapis.com``), which splits functionality across several
versioned sub-APIs (accounts, products, datasources, reports, ...) that share
one OAuth flow and the same ``content`` scope.

This client intentionally has no dependency on a Merchant API SDK: it reuses
the OAuth client credentials already configured for Google Ads
(``GOOGLE_ADS_CLIENT_ID`` / ``GOOGLE_ADS_CLIENT_SECRET``) plus a refresh token
that includes the ``content`` scope. That refresh token may be the same one
used for Google Ads (request both scopes together with
``--include-merchant-center``) or a separate one set via
``GOOGLE_MERCHANT_CENTER_REFRESH_TOKEN``.
"""

from __future__ import annotations

import base64
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from .config import Settings
from .errors import GoogleAdsMcpError
from .merchant_scope import MerchantScope, normalize_merchant_account_id

CONTENT_SCOPE = "https://www.googleapis.com/auth/content"
_MERCHANT_API_ROOT = "https://merchantapi.googleapis.com"
_TOKEN_URL = "https://oauth2.googleapis.com/token"
_ACCOUNT_IN_PATH = re.compile(r"^accounts/([^/:]+)")
_PLAIN_ID_PART = re.compile(r"[A-Za-z0-9._-]+")
_REGISTRATION_HINT = (
    " Merchant API v1 requires a one-time developer registration of the Google "
    "Cloud project used for OAuth (accounts.developerRegistration.registerGcp, or "
    "Merchant Center > Settings > API). See docs/MERCHANT_V1_ONBOARDING.md."
)


class MerchantCenterClient:
    """Thin JSON REST client shared by every Merchant Center tool."""

    def __init__(self, settings: Settings):
        self._settings = settings
        self._access_token: str | None = None
        self._access_token_expires_at = 0.0
        self._scope = MerchantScope.from_settings(settings)

    @property
    def scope(self) -> MerchantScope:
        return self._scope

    def assert_merchant_allowed(self, merchant_id: str) -> str:
        """Normalize a Merchant account ID and enforce the Merchant allowlist."""
        return self._scope.assert_allowed(merchant_id)

    def filter_allowed_accounts(self, accounts: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Restrict discovery results to this deployment's Merchant scope."""
        return self._scope.filter_accounts(accounts)

    @property
    def _refresh_token(self) -> str | None:
        return (
            self._settings.merchant_center_refresh_token
            or self._settings.refresh_token
            or None
        )

    @property
    def configured(self) -> bool:
        return bool(
            self._refresh_token
            and self._settings.client_id
            and self._settings.client_secret
        )

    @property
    def default_account_id(self) -> str | None:
        return self._settings.merchant_center_default_id

    def require_configured(self) -> None:
        missing: list[str] = []
        if not self._refresh_token:
            missing.append(
                "GOOGLE_MERCHANT_CENTER_REFRESH_TOKEN (or GOOGLE_ADS_REFRESH_TOKEN "
                "with the content scope)"
            )
        if not self._settings.client_id:
            missing.append("GOOGLE_ADS_CLIENT_ID")
        if not self._settings.client_secret:
            missing.append("GOOGLE_ADS_CLIENT_SECRET")
        if missing:
            raise GoogleAdsMcpError(
                "Merchant Center API is not configured. Missing: "
                + ", ".join(missing)
                + ". Generate a refresh token with the content scope, for example "
                "'python -m google_ads_mcp.auth --generate-refresh-token "
                "--include-merchant-center'."
            )

    def request(
        self,
        method: str,
        api: str,
        version: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        query: dict[str, Any] | None = None,
        timeout: int = 60,
    ) -> dict[str, Any]:
        """Call one Merchant API sub-API, e.g. api='products', version='v1beta'."""
        self._scope.ensure_usable()
        self.require_configured()
        # Defense in depth: every request, read or write, is checked against the
        # Merchant scope before any credential is used or any byte leaves.
        account_match = _ACCOUNT_IN_PATH.match(path.lstrip("/"))
        if account_match:
            self.assert_merchant_allowed(account_match.group(1))
        token = self._get_access_token()
        url = f"{_MERCHANT_API_ROOT}/{api}/{version}/{path.lstrip('/')}"
        if query:
            filtered = {k: v for k, v in query.items() if v is not None}
            if filtered:
                url += "?" + urllib.parse.urlencode(filtered)

        payload = None
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "google-ads-mcp-merchant-center/0.18.1",
        }
        if body is not None:
            payload = json.dumps(body, separators=(",", ":")).encode("utf-8")

        request = urllib.request.Request(
            url,
            data=payload,
            headers=headers,
            method=method.upper(),
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                raw = response.read()
                if not raw:
                    return {}
                return json.loads(raw.decode("utf-8"))
        except urllib.error.HTTPError as ex:
            raw = ex.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(raw)
                detail = _format_google_api_error(parsed)
            except (json.JSONDecodeError, TypeError, ValueError):
                detail = raw[:2000] or str(ex)
            hint = ""
            lowered = detail.lower()
            if ex.code in (401, 403) and "regist" in lowered and (
                "developer" in lowered or "gcp" in lowered or "cloud project" in lowered
            ):
                hint = _REGISTRATION_HINT
            raise GoogleAdsMcpError(
                f"Merchant API HTTP {ex.code}: {detail}{hint}"
            ) from ex
        except (urllib.error.URLError, TimeoutError, OSError) as ex:
            raise GoogleAdsMcpError(f"Merchant API request failed: {ex}") from ex

    def _get_access_token(self) -> str:
        if self._access_token and time.time() < self._access_token_expires_at - 60:
            return self._access_token

        self.require_configured()
        form = urllib.parse.urlencode(
            {
                "client_id": self._settings.client_id,
                "client_secret": self._settings.client_secret,
                "refresh_token": self._refresh_token,
                "grant_type": "refresh_token",
            }
        ).encode("utf-8")
        request = urllib.request.Request(
            _TOKEN_URL,
            data=form,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                token_data = json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as ex:
            raw = ex.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(raw)
                detail = parsed.get("error_description") or parsed.get("error") or raw
            except (json.JSONDecodeError, TypeError):
                detail = raw
            raise GoogleAdsMcpError(
                "Could not refresh Merchant Center OAuth credentials: " + str(detail)
            ) from ex
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as ex:
            raise GoogleAdsMcpError(
                f"Could not refresh Merchant Center OAuth credentials: {ex}"
            ) from ex

        token = token_data.get("access_token")
        if not token:
            raise GoogleAdsMcpError(
                "OAuth refresh succeeded but returned no access_token for Merchant Center."
            )
        expires_in = int(token_data.get("expires_in", 3600))
        self._access_token = str(token)
        self._access_token_expires_at = time.time() + max(60, expires_in)
        return self._access_token


def normalize_merchant_id(value: str) -> str:
    return normalize_merchant_account_id(value)


def account_path(merchant_id: str) -> str:
    return f"accounts/{normalize_merchant_id(merchant_id)}"


def encode_product_id(raw_id: str) -> str:
    """Unpadded base64url (RFC 4648 §5), the Merchant API v1 encoded ID format."""
    return base64.urlsafe_b64encode(raw_id.encode("utf-8")).decode("ascii").rstrip("=")


def build_product_id(content_language: str, feed_label: str, offer_id: str) -> str:
    """Return the v1 ``{productinput}`` segment: ``content_language~feed_label~offer_id``.

    Plain when every part is URL-safe; otherwise unpadded base64url, which v1
    requires whenever a part contains characters such as ``/``, ``%`` or ``~``.
    """
    parts = (content_language.strip(), feed_label.strip(), offer_id.strip())
    if not all(parts):
        raise ValueError("content_language, feed_label and offer_id must not be empty.")
    raw = "~".join(parts)
    if all(_PLAIN_ID_PART.fullmatch(part) for part in parts):
        return raw
    return encode_product_id(raw)


def normalize_product_id(product_id: str) -> str:
    """Normalize a caller-supplied product ID to the v1 ``{product}`` segment.

    Accepts ``en~US~sku123``, ``local~en~US~sku123`` and the v1beta-era
    ``online~en~US~sku123`` (the retired channel prefix is dropped). A segment
    without ``~`` is assumed to be already base64url-encoded.
    """
    raw = str(product_id).strip()
    if not raw:
        raise ValueError("product_id must not be empty.")
    if "~" not in raw:
        return raw
    parts = raw.split("~")
    if len(parts) == 4 and parts[0] == "online":
        parts = parts[1:]
    candidate = "~".join(parts)
    if all(_PLAIN_ID_PART.fullmatch(part) for part in parts):
        return candidate
    return encode_product_id(candidate)


def product_path(merchant_id: str, product_id: str) -> str:
    return f"{account_path(merchant_id)}/products/{normalize_product_id(product_id)}"


def product_input_path(merchant_id: str, product_input_id: str) -> str:
    return f"{account_path(merchant_id)}/productInputs/{product_input_id}"


def datasource_resource_name(merchant_id: str, datasource_id: str) -> str:
    text = str(datasource_id).strip()
    if not text.isdigit():
        raise ValueError("datasource_id must be the numeric Merchant Center data source ID.")
    return f"{account_path(merchant_id)}/dataSources/{text}"


def _format_google_api_error(payload: dict[str, Any]) -> str:
    error = payload.get("error")
    if isinstance(error, dict):
        status = error.get("status")
        message = error.get("message")
        details = error.get("details")
        pieces = [str(value) for value in (status, message) if value]
        if details:
            pieces.append(json.dumps(details, default=str)[:1200])
        if pieces:
            return " | ".join(pieces)
    return json.dumps(payload, default=str)[:2000]
