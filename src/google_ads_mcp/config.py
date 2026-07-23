"""Centralized configuration, loaded from environment / .env file."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

_ENV_FILE = os.environ.get("GOOGLE_ADS_MCP_ENV_FILE")
if _ENV_FILE:
    load_dotenv(_ENV_FILE)
else:
    # Fall back to a .env file next to the current working directory.
    load_dotenv(Path.cwd() / ".env")


def _bool(name: str, default: bool) -> bool:
    val = os.environ.get(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


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
            cfg["login_customer_id"] = self.login_customer_id.replace("-", "")
        return cfg


def load_settings() -> Settings:
    return Settings(
        developer_token=os.environ.get("GOOGLE_ADS_DEVELOPER_TOKEN", ""),
        client_id=os.environ.get("GOOGLE_ADS_CLIENT_ID", ""),
        client_secret=os.environ.get("GOOGLE_ADS_CLIENT_SECRET", ""),
        refresh_token=os.environ.get("GOOGLE_ADS_REFRESH_TOKEN", ""),
        login_customer_id=os.environ.get("GOOGLE_ADS_LOGIN_CUSTOMER_ID") or None,
        auto_approve=_bool("GOOGLE_ADS_MCP_AUTO_APPROVE", False),
        pending_ttl_minutes=int(os.environ.get("GOOGLE_ADS_MCP_PENDING_TTL_MINUTES", "30")),
        audit_db_path=os.environ.get("GOOGLE_ADS_MCP_AUDIT_DB", "./audit.db"),
        transport=os.environ.get("GOOGLE_ADS_MCP_TRANSPORT", "stdio"),
        http_port=int(os.environ.get("GOOGLE_ADS_MCP_HTTP_PORT", "8080")),
    )
