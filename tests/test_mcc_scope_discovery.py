"""Allowlist derived from MCC (manager) accounts, without manual client IDs."""

from __future__ import annotations

from dataclasses import replace
from types import SimpleNamespace

import pytest

from google_ads_mcp import scope_discovery
from google_ads_mcp.config import Settings, load_settings
from google_ads_mcp.errors import GoogleAdsMcpError
from google_ads_mcp.scope_discovery import resolve_manager_scope

MCC = "1111111111"
CLIENT_A = "2222222222"
CLIENT_B = "3333333333"
CLIENT_C = "4444444444"
CANCELLED = "5555555555"
SUB_MANAGER = "6666666666"
OUTSIDE = "9999999999"


def _row(cid, manager=False, status="ENABLED", level=1):
    return SimpleNamespace(
        customer_client=SimpleNamespace(
            id=int(cid),
            manager=manager,
            status=SimpleNamespace(name=status),
            level=level,
        )
    )


class FakeFactory:
    def __init__(self, rows, error=None):
        self.rows = rows
        self.error = error
        self.calls: list[tuple[str, str | None]] = []
        self.queries: list[str] = []

    def __call__(self, settings, manager_id):
        self.calls.append((manager_id, settings.login_customer_id))
        if self.error:
            raise self.error
        factory = self

        class Service:
            def search_stream(self, customer_id, query):
                assert customer_id == manager_id
                factory.queries.append(query)
                return [SimpleNamespace(results=factory.rows)]

        return SimpleNamespace(get_service=lambda name: Service())


def _settings(**overrides) -> Settings:
    base = Settings(
        developer_token=None,
        client_id="decoy",
        client_secret="decoy",
        refresh_token="decoy",
        login_customer_id=None,
        auto_approve=False,
        pending_ttl_minutes=30,
        audit_db_path=":memory:",
        transport="stdio",
        http_port=8080,
        require_customer_allowlist=True,
        allowed_manager_ids=frozenset({MCC}),
        read_only=True,
    )
    return replace(base, **overrides)


_ROWS = [
    _row(MCC, manager=True, level=0),
    _row(CLIENT_A),
    _row(CLIENT_B),
    _row(CLIENT_C, level=2),
    _row(CANCELLED, status="CANCELED"),
    _row(SUB_MANAGER, manager=True),
]


def test_no_manager_scope_leaves_settings_untouched():
    factory = FakeFactory(_ROWS)
    settings = _settings(
        allowed_manager_ids=frozenset(), allowed_customer_ids=frozenset({CLIENT_A})
    )
    assert resolve_manager_scope(settings, factory) is settings
    assert factory.calls == []


def test_discovers_enabled_clients_only_and_sets_login():
    factory = FakeFactory(_ROWS)
    resolved = resolve_manager_scope(_settings(), factory)
    assert resolved.allowed_customer_ids == {MCC, CLIENT_A, CLIENT_B, CLIENT_C}
    assert CANCELLED not in resolved.allowed_customer_ids
    assert SUB_MANAGER not in resolved.allowed_customer_ids
    assert OUTSIDE not in resolved.allowed_customer_ids
    assert resolved.login_customer_id == MCC
    assert resolved.require_customer_allowlist is True
    assert resolved.read_only is True
    # Only a read-only GAQL over customer_client is issued.
    assert len(factory.queries) == 1
    assert factory.queries[0].lstrip().upper().startswith("SELECT")
    assert "FROM customer_client" in factory.queries[0]


def test_union_with_explicit_ids_and_deny_wins():
    factory = FakeFactory(_ROWS)
    settings = _settings(
        allowed_customer_ids=frozenset({OUTSIDE}),
        excluded_customer_ids=frozenset({CLIENT_B, OUTSIDE}),
    )
    resolved = resolve_manager_scope(settings, factory)
    assert resolved.allowed_customer_ids == {MCC, CLIENT_A, CLIENT_C}


def test_discovery_failure_never_widens_scope():
    factory = FakeFactory(_ROWS, error=RuntimeError("boom secret-token-123"))
    settings = _settings(allowed_customer_ids=frozenset({CLIENT_A}))
    resolved = resolve_manager_scope(settings, factory)
    assert resolved.allowed_customer_ids == {MCC, CLIENT_A}


def test_failure_log_does_not_leak_exception_text(caplog):
    factory = FakeFactory(_ROWS, error=RuntimeError("secret-token-123"))
    with caplog.at_level("WARNING"):
        resolve_manager_scope(_settings(), factory)
    assert "secret-token-123" not in caplog.text
    assert MCC not in caplog.text


def test_empty_scope_after_exclusions_refuses_to_start():
    settings = _settings(
        excluded_customer_ids=frozenset({MCC, CLIENT_A, CLIENT_B, CLIENT_C})
    )
    with pytest.raises(GoogleAdsMcpError, match="no accounts"):
        resolve_manager_scope(settings, FakeFactory(_ROWS))


def test_login_must_be_an_allowed_manager():
    with pytest.raises(GoogleAdsMcpError, match="must be one of"):
        resolve_manager_scope(_settings(login_customer_id=OUTSIDE), FakeFactory(_ROWS))


def test_several_managers_require_explicit_login():
    settings = _settings(allowed_manager_ids=frozenset({MCC, SUB_MANAGER}))
    with pytest.raises(GoogleAdsMcpError, match="LOGIN_CUSTOMER_ID"):
        resolve_manager_scope(settings, FakeFactory(_ROWS))


def test_load_settings_accepts_manager_scope_without_customer_ids(monkeypatch):
    monkeypatch.setenv("GOOGLE_ADS_MCP_REQUIRE_CUSTOMER_ALLOWLIST", "true")
    monkeypatch.delenv("GOOGLE_ADS_MCP_ALLOWED_CUSTOMER_IDS", raising=False)
    monkeypatch.setenv("GOOGLE_ADS_MCP_ALLOWED_MANAGER_IDS", "111-111-1111")
    monkeypatch.setenv("GOOGLE_ADS_MCP_EXCLUDED_CUSTOMER_IDS", "222-222-2222")
    settings = load_settings()
    assert settings.allowed_manager_ids == {MCC}
    assert settings.excluded_customer_ids == {CLIENT_A}


def test_load_settings_still_requires_some_allowlist(monkeypatch):
    monkeypatch.setenv("GOOGLE_ADS_MCP_REQUIRE_CUSTOMER_ALLOWLIST", "true")
    monkeypatch.delenv("GOOGLE_ADS_MCP_ALLOWED_CUSTOMER_IDS", raising=False)
    monkeypatch.delenv("GOOGLE_ADS_MCP_ALLOWED_MANAGER_IDS", raising=False)
    with pytest.raises(ValueError, match="ALLOWED_CUSTOMER_IDS or"):
        load_settings()


def test_resolved_scope_is_enforced_by_client_and_safety(monkeypatch, tmp_path):
    """Build the real context: discovered clients pass, everything else is denied."""
    factory = FakeFactory(_ROWS)
    monkeypatch.setattr(scope_discovery, "_default_client_factory", factory)
    for key, value in {
        "GOOGLE_ADS_MCP_READ_ONLY": "true",
        "GOOGLE_ADS_MCP_REQUIRE_CUSTOMER_ALLOWLIST": "true",
        "GOOGLE_ADS_MCP_ALLOWED_MANAGER_IDS": MCC,
        "GOOGLE_ADS_MCP_AUDIT_DB": str(tmp_path / "audit.db"),
        "GOOGLE_ADS_CLIENT_ID": "decoy",
        "GOOGLE_ADS_CLIENT_SECRET": "decoy",
        "GOOGLE_ADS_REFRESH_TOKEN": "decoy",
    }.items():
        monkeypatch.setenv(key, value)
    monkeypatch.delenv("GOOGLE_ADS_MCP_ALLOWED_CUSTOMER_IDS", raising=False)
    monkeypatch.delenv("GOOGLE_ADS_LOGIN_CUSTOMER_ID", raising=False)

    from google_ads_mcp.context import build_context

    ctx = build_context()
    assert ctx.settings.login_customer_id == MCC
    assert ctx.client.assert_customer_allowed(CLIENT_A) == CLIENT_A
    assert ctx.client.assert_customer_allowed(CLIENT_C) == CLIENT_C
    for denied in (OUTSIDE, CANCELLED, SUB_MANAGER):
        with pytest.raises(GoogleAdsMcpError):
            ctx.client.assert_customer_allowed(denied)
    assert ctx.client.filter_allowed_customer_ids([CLIENT_A, OUTSIDE, CANCELLED]) == [
        CLIENT_A
    ]
