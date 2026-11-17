"""Exercise Desktop OAuth command with a fake flow: no browser or Google calls."""

import json
import runpy
import sys
import types
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "authorize_readonly.py"


def test_desktop_consent_does_not_log_auth_url_or_credentials(
    tmp_path, monkeypatch, capsys
) -> None:
    client_path = tmp_path / "desktop.json"
    client_path.write_text(
        json.dumps(
            {
                "installed": {
                    "client_id": "fake-desktop-client-id",
                    "client_secret": "fake-desktop-secret",
                    "auth_uri": "https://accounts.google.com/o/oauth2/v2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                }
            }
        ),
        encoding="utf-8",
    )
    invoked = {}
    fake_token = "fake-test-refresh-token-do-not-log"

    class FakeCredentials:
        refresh_token = fake_token

        def to_json(self):
            return json.dumps(
                {
                    "refresh_token": fake_token,
                    "scopes": ["https://www.googleapis.com/auth/tagmanager.readonly"],
                }
            )

    class FakeFlow:
        @classmethod
        def from_client_secrets_file(cls, path, scopes):
            invoked["client_path"] = path
            invoked["scopes"] = scopes
            return cls()

        def run_local_server(self, **kwargs):
            invoked["flow_kwargs"] = kwargs
            return FakeCredentials()

    fake_package = types.ModuleType("google_auth_oauthlib")
    fake_flow_module = types.ModuleType("google_auth_oauthlib.flow")
    fake_flow_module.InstalledAppFlow = FakeFlow
    monkeypatch.setitem(sys.modules, "google_auth_oauthlib", fake_package)
    monkeypatch.setitem(sys.modules, "google_auth_oauthlib.flow", fake_flow_module)

    namespace = runpy.run_path(str(SCRIPT))
    namespace["main"].__globals__["save_readonly_credentials"] = (
        lambda provider, credential_json, replace: (
            invoked.update(provider=provider, grant=credential_json, replace=replace)
            or tmp_path / "gtm-readonly.json"
        )
    )
    monkeypatch.setattr(
        sys,
        "argv",
        ["authorize_readonly.py", "--provider", "gtm", "--client-secrets", str(client_path)],
    )

    assert namespace["main"]() == 0
    assert invoked["flow_kwargs"]["authorization_prompt_message"] is None
    assert invoked["flow_kwargs"]["open_browser"] is True
    assert invoked["flow_kwargs"]["host"] == "127.0.0.1"
    assert invoked["flow_kwargs"]["access_type"] == "offline"
    assert invoked["scopes"] == ["https://www.googleapis.com/auth/tagmanager.readonly"]
    assert invoked["provider"] == "gtm"
    assert fake_token in invoked["grant"]

    output = capsys.readouterr().out
    assert fake_token not in output
    assert "accounts.google.com/o/oauth2" not in output
    assert "fake-desktop-secret" not in output
