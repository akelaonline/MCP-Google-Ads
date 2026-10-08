"""Provider-specific OAuth credential storage and read-only loading.

Credentials never belong in Site Registry, job evidence, source control, or
tool responses. The desktop authorization helper is the only writer.
"""

from __future__ import annotations

import json
import os
import secrets
import stat
from pathlib import Path
from typing import Any

GTM_READONLY_SCOPE = "https://www.googleapis.com/auth/tagmanager.readonly"
GA4_READONLY_SCOPE = "https://www.googleapis.com/auth/analytics.readonly"

_PROVIDER_SCOPES = {
    "gtm": GTM_READONLY_SCOPE,
    "ga4": GA4_READONLY_SCOPE,
}
_ENV_PREFIXES = {
    "gtm": "GTM_GOOGLE",
    "ga4": "GA4_GOOGLE",
}


def oauth_directory() -> Path:
    return Path.home() / ".mkt-measurement-ops" / "oauth"


def default_credential_path(provider: str) -> Path:
    _require_provider(provider)
    return oauth_directory() / f"{provider}-readonly.json"


def _require_provider(provider: str) -> None:
    if provider not in _PROVIDER_SCOPES:
        raise ValueError(f"unsupported OAuth provider: {provider}")


def required_scope(provider: str) -> str:
    _require_provider(provider)
    return _PROVIDER_SCOPES[provider]


def credential_path(provider: str) -> Path:
    _require_provider(provider)
    overridden = os.environ.get(f"{_ENV_PREFIXES[provider]}_CREDENTIALS_FILE")
    return Path(overridden).expanduser() if overridden else default_credential_path(provider)


def _read_private_token_data(path: Path) -> dict[str, Any]:
    if path.is_symlink():
        raise PermissionError("OAuth credentials cannot be loaded through a symbolic link")
    if not path.is_file():
        raise FileNotFoundError("OAuth credential file was not found")
    if os.name == "posix" and stat.S_IMODE(path.stat().st_mode) & 0o077:
        raise PermissionError("OAuth credential file must be owner-only (chmod 600)")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError("invalid OAuth credential file")
    return payload


def _file_is_configured(provider: str) -> bool:
    path = credential_path(provider)
    if not path.exists():
        return False
    _validate_credential_data(_read_private_token_data(path), provider)
    return True


def _validate_credential_data(payload: dict[str, Any], provider: str) -> None:
    required = {"client_id", "client_secret", "refresh_token", "token_uri"}
    if any(not payload.get(key) for key in required):
        raise ValueError("OAuth credential file is missing required fields")
    scopes = payload.get("scopes") or []
    if not isinstance(scopes, list) or set(scopes) != {required_scope(provider)}:
        raise ValueError("OAuth credential scopes do not match the expected read-only provider scope")


def _legacy_configured(provider: str) -> bool:
    prefix = _ENV_PREFIXES[provider]
    return all(
        os.environ.get(f"{prefix}_{suffix}")
        for suffix in ("CLIENT_ID", "CLIENT_SECRET", "REFRESH_TOKEN")
    )


def credential_configuration_status() -> dict[str, bool]:
    """Configuration presence only; does not assert usable Google API access."""
    return {
        "gtm_readonly_configured": _file_is_configured("gtm") or bool(_legacy_configured("gtm")),
        "ga4_readonly_configured": _file_is_configured("ga4") or bool(_legacy_configured("ga4")),
    }


def load_readonly_credentials(provider: str) -> Any:
    """Load one provider's read-only OAuth grant, without exposing token material."""
    _require_provider(provider)
    path = credential_path(provider)
    from google.oauth2.credentials import Credentials

    if path.exists() or path.is_symlink():
        payload = _read_private_token_data(path)
        _validate_credential_data(payload, provider)
        return Credentials.from_authorized_user_info(
            payload, scopes=[required_scope(provider)]
        )

    prefix = _ENV_PREFIXES[provider]
    fields = {
        "client_id": os.getenv(f"{prefix}_CLIENT_ID"),
        "client_secret": os.getenv(f"{prefix}_CLIENT_SECRET"),
        "refresh_token": os.getenv(f"{prefix}_REFRESH_TOKEN"),
    }
    missing = [
        f"{prefix}_{field.upper()}"
        for field, value in fields.items()
        if not value
    ]
    if missing:
        raise RuntimeError(
            f"missing {provider.upper()} read-only OAuth configuration; "
            f"run the local authorize_readonly.py helper or configure: {', '.join(missing)}"
        )

    return Credentials(
        token=None,
        refresh_token=fields["refresh_token"],
        token_uri="https://oauth2.googleapis.com/token",
        client_id=fields["client_id"],
        client_secret=fields["client_secret"],
        scopes=[required_scope(provider)],
    )


def save_readonly_credentials(provider: str, credential_json: str, *, replace: bool = False) -> Path:
    """Atomic 0600 write; never prints or returns the token contents."""
    _require_provider(provider)
    payload = json.loads(credential_json)
    if not isinstance(payload, dict):
        raise ValueError("invalid OAuth token response")
    _validate_credential_data(payload, provider)
    destination = default_credential_path(provider)
    destination.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    if destination.parent.is_symlink():
        raise PermissionError("OAuth credential directory must not be a symlink")
    if os.name == "posix" and stat.S_IMODE(destination.parent.stat().st_mode) & 0o077:
        raise PermissionError("OAuth credential directory must be owner-only (chmod 700)")
    if destination.exists() and not replace:
        raise FileExistsError("OAuth credentials already exist; use --replace to replace them")
    if destination.is_symlink():
        raise PermissionError("OAuth destination must not be a symbolic link")

    temporary = destination.with_name(
        destination.name + f".tmp-{secrets.token_hex(8)}"
    )
    descriptor = os.open(
        temporary,
        os.O_WRONLY | os.O_CREAT | os.O_EXCL,
        0o600,
    )
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    finally:
        if temporary.exists():
            temporary.unlink()
    return destination
