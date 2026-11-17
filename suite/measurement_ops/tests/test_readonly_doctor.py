import json
import runpy
import subprocess
import sys
from pathlib import Path

from mkt_measurement_ops.credentials import (
    GA4_READONLY_SCOPE,
    GTM_READONLY_SCOPE,
    save_readonly_credentials,
)


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "doctor_readonly.py"


def _grant(scope: str) -> str:
    return json.dumps(
        {
            "token": "test-only-token",
            "refresh_token": "test-only-refresh",
            "token_uri": "https://oauth2.googleapis.com/token",
            "client_id": "test-only-client",
            "client_secret": "test-only-secret",
            "scopes": [scope],
        }
    )


def test_doctor_blocks_unconfigured_grants_without_calling_google(
    tmp_path, monkeypatch
) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    for prefix in ("GTM_GOOGLE", "GA4_GOOGLE"):
        for suffix in ("CLIENT_ID", "CLIENT_SECRET", "REFRESH_TOKEN", "CREDENTIALS_FILE"):
            monkeypatch.delenv(f"{prefix}_{suffix}", raising=False)
    for flag in ("GTM_ENABLE_PREVIEW", "GTM_ENABLE_WRITES", "GTM_ENABLE_PUBLISH"):
        monkeypatch.setenv(flag, "false")
    doctor = runpy.run_path(str(SCRIPT))["assess_local_readiness"]
    report = doctor()
    assert report["ready_for_readonly_smoke"] is False
    assert report["checks"]["google_api_tested"] is False
    assert not (tmp_path / ".mkt-measurement-ops").exists()


def test_doctor_ready_when_both_private_grants_exist(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    for flag in ("GTM_ENABLE_PREVIEW", "GTM_ENABLE_WRITES", "GTM_ENABLE_PUBLISH"):
        monkeypatch.setenv(flag, "false")
    for prefix in ("GTM_GOOGLE", "GA4_GOOGLE"):
        for suffix in ("CLIENT_ID", "CLIENT_SECRET", "REFRESH_TOKEN", "CREDENTIALS_FILE"):
            monkeypatch.delenv(f"{prefix}_{suffix}", raising=False)
    save_readonly_credentials("gtm", _grant(GTM_READONLY_SCOPE))
    save_readonly_credentials("ga4", _grant(GA4_READONLY_SCOPE))
    report = runpy.run_path(str(SCRIPT))["assess_local_readiness"]()
    assert report["ready_for_readonly_smoke"] is True
    assert report["checks"]["google_api_tested"] is False


def test_doctor_blocks_any_mutation_flag(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("HOME", str(tmp_path))
    save_readonly_credentials("gtm", _grant(GTM_READONLY_SCOPE))
    save_readonly_credentials("ga4", _grant(GA4_READONLY_SCOPE))
    for flag in ("GTM_ENABLE_PREVIEW", "GTM_ENABLE_WRITES", "GTM_ENABLE_PUBLISH"):
        monkeypatch.setenv(flag, "false")
    doctor = runpy.run_path(str(SCRIPT))["assess_local_readiness"]
    assert doctor()["ready_for_readonly_smoke"] is True
    for flag in ("GTM_ENABLE_PREVIEW", "GTM_ENABLE_WRITES", "GTM_ENABLE_PUBLISH"):
        monkeypatch.setenv(flag, "true")
        report = doctor()
        assert report["ready_for_readonly_smoke"] is False
        monkeypatch.setenv(flag, "false")


def test_doctor_requires_explicit_credentials(tmp_path) -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPT)],
        env={"HOME": str(tmp_path), "PATH": "/usr/bin:/bin"},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert '"google_api_tested": false' in result.stdout
    assert "no Google API calls made" in result.stdout
