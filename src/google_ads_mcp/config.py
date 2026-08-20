"""Centralized configuration, loaded from environment / .env file."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

from .helpers import normalize_customer_id

_ENV_FILE = os.environ.get("GOOGLE_ADS_MCP_ENV_FILE")
if _ENV_FILE:
    load_dotenv(_ENV_FILE)
else:
    load_dotenv(Path.cwd() / ".env")


def _bool(name: str, default: bool) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


def _customer_id_set(name: str) -> frozenset[str]:
    raw = os.environ.get(name, "")
    values: set[str] = set()
    for item in raw.split(","):
        if not item.strip():
            continue
        normalized = normalize_customer_id(item)
        if not normalized.isdigit():
            raise ValueError(
                f"{name} contains invalid Google Ads customer ID {item!r}; "
                "use digits with optional dashes, separated by commas."
            )
        values.add(normalized)
    return frozenset(values)


@dataclass(frozen=True)
class Settings:
    developer_token: str
    client_id: str
    client_secret: str
    refresh_token: str
    login_customer_id: str | None
    auto_approve: bool
    pending_ttl_minutes: int
    audit_db_path: str
    transport: str
    http_port: int
    allowed_customer_ids: frozenset[str] = frozenset()
    require_customer_allowlist: bool = False
    auto_approve_spend: bool = False
    auto_approve_destructive: bool = False
    auto_approve_sensitive: bool = False
    data_manager_project_id: str | None = None
    data_manager_refresh_token: str | None = None
    read_only: bool = False

    @property
    def google_ads_yaml_dict(self) -> dict:
        """Config dict in the shape google-ads-python's GoogleAdsClient expects."""
        cfg = {
            "developer_token": self.developer_token,
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "refresh_token": self.refresh_token,
            "use_proto_plus": True,
        }
        if self.login_customer_id:
            cfg["login_customer_id"] = normalize_customer_id(self.login_customer_id)
        return cfg


def _resolve_audit_db_path(raw: str | None) -> str:
    """Resolve the configured (or default) audit DB path safely."""
    home_dir = Path.home() / ".google_ads_mcp"
    if not raw:
        home_dir.mkdir(parents=True, exist_ok=True)
        return str(home_dir / "audit.db")

    path = Path(raw).expanduser()
    if not path.is_absolute():
        path = Path.home() / ".google_ads_mcp" / path.name
    path.parent.mkdir(parents=True, exist_ok=True)
    return str(path)


def load_settings() -> Settings:
    allowed_customer_ids = _customer_id_set("GOOGLE_ADS_MCP_ALLOWED_CUSTOMER_IDS")
    require_customer_allowlist = _bool(
        "GOOGLE_ADS_MCP_REQUIRE_CUSTOMER_ALLOWLIST", False
    )
    if require_customer_allowlist and not allowed_customer_ids:
        raise ValueError(
            "GOOGLE_ADS_MCP_REQUIRE_CUSTOMER_ALLOWLIST=true requires at least one "
            "GOOGLE_ADS_MCP_ALLOWED_CUSTOMER_IDS entry."
        )

    data_manager_project_id = (
        os.environ.get("GOOGLE_ADS_DATA_MANAGER_PROJECT_ID", "").strip() or None
    )
    data_manager_refresh_token = (
        os.environ.get("GOOGLE_ADS_DATA_MANAGER_REFRESH_TOKEN", "").strip() or None
    )

    return Settings(
        developer_token=os.environ.get("GOOGLE_ADS_DEVELOPER_TOKEN", ""),
        client_id=os.environ.get("GOOGLE_ADS_CLIENT_ID", ""),
        client_secret=os.environ.get("GOOGLE_ADS_CLIENT_SECRET", ""),
        refresh_token=os.environ.get("GOOGLE_ADS_REFRESH_TOKEN", ""),
        login_customer_id=os.environ.get("GOOGLE_ADS_LOGIN_CUSTOMER_ID") or None,
        auto_approve=_bool("GOOGLE_ADS_MCP_AUTO_APPROVE", False),
        pending_ttl_minutes=int(
            os.environ.get("GOOGLE_ADS_MCP_PENDING_TTL_MINUTES", "30")
        ),
        audit_db_path=_resolve_audit_db_path(os.environ.get("GOOGLE_ADS_MCP_AUDIT_DB")),
        transport=os.environ.get("GOOGLE_ADS_MCP_TRANSPORT", "stdio"),
        http_port=int(os.environ.get("GOOGLE_ADS_MCP_HTTP_PORT", "8080")),
        allowed_customer_ids=allowed_customer_ids,
        require_customer_allowlist=require_customer_allowlist,
        auto_approve_spend=_bool("GOOGLE_ADS_MCP_AUTO_APPROVE_SPEND", False),
        auto_approve_destructive=_bool(
            "GOOGLE_ADS_MCP_AUTO_APPROVE_DESTRUCTIVE", False
        ),
        auto_approve_sensitive=_bool("GOOGLE_ADS_MCP_AUTO_APPROVE_SENSITIVE", False),
        data_manager_project_id=data_manager_project_id,
        data_manager_refresh_token=data_manager_refresh_token,
        read_only=_bool("GOOGLE_ADS_MCP_READ_ONLY", False),
    )
