"""Offline contract tests for tokenless (developer-token-free) auth config.

Google sunset developer tokens on 2026-09-09: the `developer-token` header is
now optional and ignored by the API servers, and access levels live on the
Google Cloud project that owns the OAuth client. The google-ads Python client
dropped its mandatory developer_token config validation in 32.0.0, which this
package now requires (>=32,<34, still on API v25).

These tests pin the MCP-side contract:

- `GOOGLE_ADS_DEVELOPER_TOKEN` is optional.
- `developer_token` is *omitted* from the google-ads config dict when unset or
  empty — never forwarded as None or "".
- Legacy installations that still provide a token keep forwarding it verbatim.
- `GoogleAdsClient.load_from_dict` accepts the tokenless dict at API v25 with
  OAuth refresh mocked, so the suite stays offline.
- MCC (`login_customer_id`) and allowlist configuration are unaffected.
"""

from __future__ import annotations

from google_ads_mcp.client import GOOGLE_ADS_API_VERSION, GoogleAdsClientWrapper
from google_ads_mcp.config import Settings, load_settings

_BASE_KWARGS = {
    "client_id": "fake.apps.googleusercontent.com",
    "client_secret": "fake-secret",
    "refresh_token": "fake-refresh",
    "login_customer_id": None,
    "auto_approve": False,
    "pending_ttl_minutes": 30,
    "audit_db_path": ":memory:",
    "transport": "stdio",
    "http_port": 8080,
}


def _settings(**overrides) -> Settings:
    kwargs = {"developer_token": None, **_BASE_KWARGS, **overrides}
    return Settings(**kwargs)


# ---- load_settings: env -> Settings ----------------------------------------


def test_load_settings_without_developer_token(monkeypatch):
    monkeypatch.delenv("GOOGLE_ADS_DEVELOPER_TOKEN", raising=False)
    settings = load_settings()
    assert settings.developer_token is None


def test_load_settings_with_legacy_developer_token(monkeypatch):
    monkeypatch.setenv("GOOGLE_ADS_DEVELOPER_TOKEN", "LEGACY-TOKEN-123")
    settings = load_settings()
    assert settings.developer_token == "LEGACY-TOKEN-123"


def test_load_settings_empty_developer_token_is_absent(monkeypatch):
    # A `.env` line like GOOGLE_ADS_DEVELOPER_TOKEN= means "not configured",
    # not "empty token".
    monkeypatch.setenv("GOOGLE_ADS_DEVELOPER_TOKEN", "")
    settings = load_settings()
    assert settings.developer_token is None


# ---- google_ads_yaml_dict: key omission vs forwarding ----------------------


def test_yaml_dict_omits_developer_token_when_none():
    cfg = _settings(developer_token=None).google_ads_yaml_dict
    assert "developer_token" not in cfg


def test_yaml_dict_omits_developer_token_when_empty_string():
    cfg = _settings(developer_token="").google_ads_yaml_dict
    assert "developer_token" not in cfg


def test_yaml_dict_forwards_legacy_developer_token():
    cfg = _settings(developer_token="LEGACY-TOKEN-123").google_ads_yaml_dict
    assert cfg["developer_token"] == "LEGACY-TOKEN-123"


def test_yaml_dict_keeps_oauth_and_proto_plus():
    cfg = _settings().google_ads_yaml_dict
    assert cfg["client_id"] == "fake.apps.googleusercontent.com"
    assert cfg["client_secret"] == "fake-secret"
    assert cfg["refresh_token"] == "fake-refresh"
    assert cfg["use_proto_plus"] is True


def test_yaml_dict_normalizes_login_customer_id():
    cfg = _settings(login_customer_id="123-456-7890").google_ads_yaml_dict
    assert cfg["login_customer_id"] == "1234567890"


# ---- Client wrapper passes the tokenless dict through at API v25 ------------


def test_wrapper_loads_client_with_tokenless_dict_at_pinned_api_version(mocker):
    captured = {}

    class _FakeGoogleAdsClient:
        @classmethod
        def load_from_dict(cls, config_dict, version=None):
            captured["config"] = dict(config_dict)
            captured["version"] = version
            return object()

    mocker.patch(
        "google.ads.googleads.client.GoogleAdsClient.load_from_dict",
        _FakeGoogleAdsClient.load_from_dict,
    )
    wrapper = GoogleAdsClientWrapper(_settings())
    assert wrapper.raw is not None
    assert captured["version"] == GOOGLE_ADS_API_VERSION
    assert "developer_token" not in captured["config"]
    assert captured["config"]["use_proto_plus"] is True


# ---- Real google-ads>=32 acceptance, offline via mocked OAuth refresh -------


def _real_client(cfg: dict):
    from google.ads.googleads.client import GoogleAdsClient

    return GoogleAdsClient.load_from_dict(cfg, version=GOOGLE_ADS_API_VERSION)


def test_real_lib_builds_tokenless_client(monkeypatch):
    # google-ads eagerly refreshes OAuth inside load_from_dict; stub the
    # network call so the test verifies only client-library acceptance.
    monkeypatch.setattr(
        "google.oauth2.credentials.Credentials.refresh", lambda self, request: None
    )
    client = _real_client(_settings().google_ads_yaml_dict)
    assert client.developer_token is None
    # API v25 service/type surfaces still resolve on the upgraded SDK.
    assert client.get_service("GoogleAdsService") is not None
    assert client.get_type("Campaign") is not None


def test_real_lib_builds_legacy_token_client(monkeypatch):
    monkeypatch.setattr(
        "google.oauth2.credentials.Credentials.refresh", lambda self, request: None
    )
    client = _real_client(_settings(developer_token="LEGACY-TOKEN-123").google_ads_yaml_dict)
    assert client.developer_token == "LEGACY-TOKEN-123"
    assert client.get_service("GoogleAdsService") is not None


def test_real_lib_tokenless_client_with_mcc(monkeypatch):
    monkeypatch.setattr(
        "google.oauth2.credentials.Credentials.refresh", lambda self, request: None
    )
    client = _real_client(_settings(login_customer_id="123-456-7890").google_ads_yaml_dict)
    assert client.developer_token is None
    assert client.login_customer_id == "1234567890"
