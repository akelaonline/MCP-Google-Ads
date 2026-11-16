"""Deployment scope for Merchant Center accounts.

Merchant Center account IDs and Google Ads customer IDs are different
identifier spaces even though both are numeric, so a Google Ads allowlist must
never authorise a Merchant account (or the other way round). This module holds
the Merchant-specific policy shared by the REST client (every read and write)
and the safety layer (confirmation and replay of pending writes).

Policy:
* ``GOOGLE_ADS_MCP_ALLOWED_MERCHANT_IDS`` set  -> only those accounts.
* not set, but the deployment is hardened (a Google Ads allowlist is configured
  or required, or ``GOOGLE_ADS_MCP_REQUIRE_MERCHANT_ALLOWLIST`` is on)
  -> Merchant access is refused until a Merchant allowlist is configured.
* not set and nothing hardened -> unscoped, as in a plain development setup.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from .errors import GoogleAdsMcpError


def normalize_merchant_account_id(value: Any) -> str:
    text = str(value).strip()
    if not text.isdigit() or int(text) <= 0:
        raise ValueError(
            "merchant_id must be a positive numeric Merchant Center account ID."
        )
    return text


def is_merchant_tool(tool_name: str) -> bool:
    """True for tools whose target ID is a Merchant Center account ID."""
    return "merchant_center" in tool_name


@dataclass(frozen=True)
class MerchantScope:
    allowed_ids: frozenset[str] = frozenset()
    require_allowlist: bool = False
    hardened_without_scope: bool = False

    @classmethod
    def build(
        cls,
        *,
        allowed_ids: Iterable[str] | None = None,
        require_allowlist: bool = False,
        ads_scope_configured: bool = False,
    ) -> MerchantScope:
        ids = frozenset(
            normalize_merchant_account_id(item)
            for item in (allowed_ids or ())
            if str(item).strip()
        )
        if require_allowlist and not ids:
            raise GoogleAdsMcpError(
                "GOOGLE_ADS_MCP_REQUIRE_MERCHANT_ALLOWLIST is enabled but no "
                "GOOGLE_ADS_MCP_ALLOWED_MERCHANT_IDS were configured."
            )
        return cls(
            allowed_ids=ids,
            require_allowlist=require_allowlist,
            hardened_without_scope=(not ids) and ads_scope_configured,
        )

    @classmethod
    def from_settings(cls, settings: Any) -> MerchantScope:
        return cls.build(
            allowed_ids=getattr(settings, "allowed_merchant_ids", ()),
            require_allowlist=bool(getattr(settings, "require_merchant_allowlist", False)),
            ads_scope_configured=bool(
                getattr(settings, "require_customer_allowlist", False)
                or getattr(settings, "allowed_customer_ids", ())
            ),
        )

    @property
    def restricted(self) -> bool:
        return bool(self.allowed_ids)

    def ensure_usable(self) -> None:
        """Refuse before any call when the deployment has no usable Merchant scope."""
        self._refuse_unscoped()

    def _refuse_unscoped(self) -> None:
        if self.hardened_without_scope:
            raise GoogleAdsMcpError(
                "Merchant Center access is disabled: this deployment restricts Google "
                "Ads accounts but has no GOOGLE_ADS_MCP_ALLOWED_MERCHANT_IDS. Merchant "
                "Center account IDs are a separate scope from Google Ads customer IDs; "
                "configure the Merchant allowlist to enable Merchant tools."
            )

    def assert_allowed(self, merchant_id: Any) -> str:
        """Normalize ``merchant_id`` and enforce the Merchant scope."""
        normalized = normalize_merchant_account_id(merchant_id)
        self._refuse_unscoped()
        if self.allowed_ids and normalized not in self.allowed_ids:
            raise GoogleAdsMcpError(
                f"Merchant Center account {normalized} is outside "
                "GOOGLE_ADS_MCP_ALLOWED_MERCHANT_IDS. The request was blocked "
                "before contacting Google."
            )
        return normalized

    def filter_accounts(self, accounts: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
        """Keep only accounts inside the Merchant scope (discovery results)."""
        self._refuse_unscoped()
        items = list(accounts)
        if not self.allowed_ids:
            return items
        allowed: list[dict[str, Any]] = []
        for item in items:
            account_id = _account_id_of(item)
            if account_id is not None and account_id in self.allowed_ids:
                allowed.append(item)
        return allowed


def _account_id_of(account: dict[str, Any]) -> str | None:
    raw = account.get("accountId")
    if raw is None:
        name = str(account.get("name") or "")
        if name.startswith("accounts/"):
            raw = name.split("/", 2)[1]
    if raw is None:
        return None
    text = str(raw).strip()
    return text if text.isdigit() else None
