"""Minimal authenticated REST client for Google's Data Manager API.

Customer Match integrations created after Google's 2026 migration cutoff need
Data Manager API support. This client intentionally has no dependency on a
Data Manager SDK: it uses the same OAuth client credentials configured for the
MCP plus a refresh token that includes the ``datamanager`` scope.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from .config import Settings
from .errors import GoogleAdsMcpError

DATA_MANAGER_SCOPE = "https://www.googleapis.com/auth/datamanager"
_DATA_MANAGER_ROOT = "https://datamanager.googleapis.com/v1"
_TOKEN_URL = "https://oauth2.googleapis.com/token"


class DataManagerClient:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._access_token: str | None = None
        self._access_token_expires_at = 0.0

    @property
    def configured(self) -> bool:
        return bool(
            self._settings.data_manager_project_id
            and self._settings.data_manager_refresh_token
            and self._settings.client_id
            and self._settings.client_secret
        )

    def require_configured(self) -> None:
        missing: list[str] = []
        if not self._settings.data_manager_project_id:
            missing.append("GOOGLE_ADS_DATA_MANAGER_PROJECT_ID")
        if not self._settings.data_manager_refresh_token:
            missing.append("GOOGLE_ADS_DATA_MANAGER_REFRESH_TOKEN")
        if not self._settings.client_id:
            missing.append("GOOGLE_ADS_CLIENT_ID")
        if not self._settings.client_secret:
            missing.append("GOOGLE_ADS_CLIENT_SECRET")
        if missing:
            raise GoogleAdsMcpError(
                "Data Manager API is not configured. Missing: "
                + ", ".join(missing)
                + ". Generate a refresh token with the Data Manager scope and "
                "enable the Data Manager API in the configured Google Cloud project."
            )

    def request(
        self,
        method: str,
        path: str,
        *,
        body: dict[str, Any] | None = None,
        query: dict[str, Any] | None = None,
        login_account: str | None = None,
        linked_account: str | None = None,
        timeout: int = 60,
    ) -> dict[str, Any]:
        self.require_configured()
        token = self._get_access_token()
        url = f"{_DATA_MANAGER_ROOT}/{path.lstrip('/')}"
        if query:
            filtered = {k: v for k, v in query.items() if v is not None}
            if filtered:
                url += "?" + urllib.parse.urlencode(filtered)

        payload = None
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "x-goog-user-project": str(self._settings.data_manager_project_id),
            "User-Agent": "google-ads-mcp-data-manager/0.16",
        }
        if login_account:
            headers["login-account"] = login_account
        if linked_account:
            headers["linked-account"] = linked_account
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
            raise GoogleAdsMcpError(
                f"Data Manager API HTTP {ex.code}: {detail}"
            ) from ex
        except (urllib.error.URLError, TimeoutError, OSError) as ex:
            raise GoogleAdsMcpError(f"Data Manager API request failed: {ex}") from ex

    def _get_access_token(self) -> str:
        if self._access_token and time.time() < self._access_token_expires_at - 60:
            return self._access_token

        self.require_configured()
        form = urllib.parse.urlencode(
            {
                "client_id": self._settings.client_id,
                "client_secret": self._settings.client_secret,
                "refresh_token": self._settings.data_manager_refresh_token,
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
                "Could not refresh Data Manager OAuth credentials: " + str(detail)
            ) from ex
        except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as ex:
            raise GoogleAdsMcpError(
                f"Could not refresh Data Manager OAuth credentials: {ex}"
            ) from ex

        token = token_data.get("access_token")
        if not token:
            raise GoogleAdsMcpError(
                "OAuth refresh succeeded but returned no access_token for Data Manager."
            )
        expires_in = int(token_data.get("expires_in", 3600))
        self._access_token = str(token)
        self._access_token_expires_at = time.time() + max(60, expires_in)
        return self._access_token


def google_ads_account_resource(customer_id: str) -> str:
    return f"accountTypes/GOOGLE_ADS/accounts/{customer_id}"


def data_manager_user_list_resource(customer_id: str, user_list_id: str) -> str:
    return f"{google_ads_account_resource(customer_id)}/userLists/{user_list_id}"


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
