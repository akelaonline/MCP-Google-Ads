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
    )
    return AppContext(settings=settings, client=client, safety=safety, audit=audit)
