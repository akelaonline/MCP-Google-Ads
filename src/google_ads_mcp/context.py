"""Shared context object passed into every tool module's `register()`."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .audit import AuditLog
from .client import GoogleAdsClientWrapper
from .config import Settings, load_settings
from .merchant_client import MerchantCenterClient
from .merchant_scope import MerchantScope
from .read_only import ReadOnlySafetyProxy
from .safety import SafetyLayer
from .scoped_client import ScopedGoogleAdsClientWrapper


@dataclass
class AppContext:
    settings: Settings
    client: GoogleAdsClientWrapper
    safety: Any
    audit: AuditLog
    merchant: MerchantCenterClient | None = None

    def assert_merchant_allowed(self, merchant_id: Any) -> str:
        """Validate a Merchant account ID named by an Ads-side tool.

        Merchant account IDs are a separate scope from Ads customer IDs, so the
        Ads allowlist never authorizes them. Uses the live Merchant client's
        scope; falls back to the one derived from settings.
        """
        scope = (
            self.merchant.scope
            if self.merchant is not None
            else MerchantScope.from_settings(self.settings)
        )
        return scope.assert_allowed(merchant_id)


def build_context() -> AppContext:
    settings = load_settings()
    audit = AuditLog(settings.audit_db_path)
    client = ScopedGoogleAdsClientWrapper(settings)
    base_safety = SafetyLayer(
        auto_approve=settings.auto_approve,
        ttl_minutes=settings.pending_ttl_minutes,
        audit_log=audit,
        auto_approve_spend=settings.auto_approve_spend,
        auto_approve_destructive=settings.auto_approve_destructive,
        auto_approve_sensitive=settings.auto_approve_sensitive,
        allowed_customer_ids=settings.allowed_customer_ids,
        require_customer_allowlist=settings.require_customer_allowlist,
        allowed_merchant_ids=settings.allowed_merchant_ids,
        require_merchant_allowlist=settings.require_merchant_allowlist,
    )
    safety = ReadOnlySafetyProxy(base_safety) if settings.read_only else base_safety
    merchant = MerchantCenterClient(settings)
    return AppContext(
        settings=settings, client=client, safety=safety, audit=audit, merchant=merchant
    )