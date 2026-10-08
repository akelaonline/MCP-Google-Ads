import json
import runpy
from pathlib import Path

import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "authorize_readonly.py"


def _desktop_client() -> dict:
    return {
        "installed": {
            "client_id": "test-only-id.apps.googleusercontent.com",
            "client_secret": "test-only-secret",
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": ["http://localhost"],
        }
    }


def test_google_desktop_client_validation(tmp_path) -> None:
    path = tmp_path / "desktop-client.json"
    path.write_text(json.dumps(_desktop_client()), encoding="utf-8")
    validate = runpy.run_path(str(SCRIPT))["_validate_desktop_client"]
    validate(path)


@pytest.mark.parametrize(
    "field, value",
    [
        ("auth_uri", "https://evil.example/authorize"),
        ("token_uri", "https://evil.example/token"),
        ("client_secret", ""),
    ],
)
def test_rejects_untrusted_desktop_oauth_configuration(tmp_path, field, value) -> None:
    payload = _desktop_client()
    payload["installed"][field] = value
    path = tmp_path / "desktop-client.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    validate = runpy.run_path(str(SCRIPT))["_validate_desktop_client"]
    with pytest.raises(ValueError, match="Desktop|Google"):
        validate(path)


def test_web_oauth_client_is_not_accepted_as_desktop_client(tmp_path) -> None:
    path = tmp_path / "web-client.json"
    path.write_text(json.dumps({"web": _desktop_client()["installed"]}), encoding="utf-8")
    validate = runpy.run_path(str(SCRIPT))["_validate_desktop_client"]
    with pytest.raises(ValueError, match="Desktop"):
        validate(path)
