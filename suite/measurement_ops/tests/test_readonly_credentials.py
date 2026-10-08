import json
import os
import stat

import pytest

from mkt_measurement_ops.credentials import (
    GA4_READONLY_SCOPE,
    GTM_READONLY_SCOPE,
    credential_configuration_status,
    default_credential_path,
    load_readonly_credentials,
    save_readonly_credentials,
)


def _credentials(scope: str) -> str:
    return json.dumps(
        {
            "token": "fake-access-token-for-unit-test",
            "refresh_token": "fake-refresh-token-for-unit-test",
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_id": "client-id",
            "client_secret": "client-secret",
            "scopes": [scope],
        }
    )


def test_provider_files_are_separate_and_owner_only(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    gtm = save_readonly_credentials("gtm", _credentials(GTM_READONLY_SCOPE))
    ga4 = save_readonly_credentials("ga4", _credentials(GA4_READONLY_SCOPE))

    assert gtm != ga4
    assert gtm == default_credential_path("gtm")
    assert "fake-refresh-token" not in str(gtm)
    if os.name == "posix":
        assert stat.S_IMODE(gtm.stat().st_mode) == 0o600
        assert stat.S_IMODE(gtm.parent.stat().st_mode) == 0o700
    assert credential_configuration_status() == {
        "gtm_readonly_configured": True,
        "ga4_readonly_configured": True,
    }
    assert load_readonly_credentials("gtm").scopes == [GTM_READONLY_SCOPE]
    assert load_readonly_credentials("ga4").scopes == [GA4_READONLY_SCOPE]


def test_wrong_or_elevated_scope_is_rejected(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    with pytest.raises(ValueError, match="read-only provider scope"):
        save_readonly_credentials("gtm", _credentials(GA4_READONLY_SCOPE))

    elevated = json.loads(_credentials(GTM_READONLY_SCOPE))
    elevated["scopes"].append("https://www.googleapis.com/auth/tagmanager.publish")
    with pytest.raises(ValueError, match="read-only provider scope"):
        save_readonly_credentials("gtm", json.dumps(elevated))


def test_overwriting_existing_grant_requires_explicit_replace(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    save_readonly_credentials("gtm", _credentials(GTM_READONLY_SCOPE))
    with pytest.raises(FileExistsError, match="--replace"):
        save_readonly_credentials("gtm", _credentials(GTM_READONLY_SCOPE))
    target = save_readonly_credentials(
        "gtm", _credentials(GTM_READONLY_SCOPE), replace=True
    )
    assert target.exists()


def test_group_readable_token_file_is_rejected(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    target = save_readonly_credentials("gtm", _credentials(GTM_READONLY_SCOPE))
    if os.name != "posix":
        pytest.skip("POSIX-only file mode test")
    target.chmod(0o644)
    with pytest.raises(PermissionError, match="chmod 600"):
        load_readonly_credentials("gtm")


def test_symlinked_credentials_are_rejected(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    original = save_readonly_credentials("gtm", _credentials(GTM_READONLY_SCOPE))
    symlink = tmp_path / "shortcut.json"
    symlink.symlink_to(original)
    monkeypatch.setenv("GTM_GOOGLE_CREDENTIALS_FILE", str(symlink))
    with pytest.raises(PermissionError, match="symbolic link"):
        load_readonly_credentials("gtm")


def test_missing_oauth_does_not_make_network_requests(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    for key in ("GTM_GOOGLE_CLIENT_ID", "GTM_GOOGLE_CLIENT_SECRET", "GTM_GOOGLE_REFRESH_TOKEN"):
        monkeypatch.delenv(key, raising=False)
    with pytest.raises(RuntimeError, match="authorize_readonly.py"):
        load_readonly_credentials("gtm")


def test_existing_legacy_env_configuration_is_recognized(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("GTM_GOOGLE_CLIENT_ID", "test-client")
    monkeypatch.setenv("GTM_GOOGLE_CLIENT_SECRET", "test-secret")
    monkeypatch.setenv("GTM_GOOGLE_REFRESH_TOKEN", "test-refresh")
    assert credential_configuration_status()["gtm_readonly_configured"] is True
