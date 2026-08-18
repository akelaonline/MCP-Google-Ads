"""Shared context object passed into every tool module's `register()`."""

from __future__ import annotations

from dataclasses import dataclass

from .audit import AuditLog
from .client import GoogleAdsClientWrapper
from .config import Settings, load_settings
from .safety import SafetyLayer


@dataclass
class AppContext:
    settings: Settings
    client: GoogleAdsClientWrapper
    safety: SafetyLayer
    audit: AuditLog


def build_context() -> AppContext:
    settings = load_settings()
    audit = AuditLog(settings.audit_db_path)
    client = GoogleAdsClientWrapper(settings)
    safety = SafetyLayer(
        auto_approve=settings.auto_approve,
        ttl_minutes=settings.pending_ttl_minutes,
        audit_log=audit,
        auto_approve_spend=settings.auto_approve_spend,
        auto_approve_destructive=settings.auto_approve_destructive,
        auto_approve_sensitive=settings.auto_approve_sensitive,
        allowed_customer_ids=settings.allowed_customer_ids,
        require_customer_allowlist=settings.require_customer_allowlist,
    )
    return AppContext(settings=settings, client=client, safety=safety, audit=audit)
