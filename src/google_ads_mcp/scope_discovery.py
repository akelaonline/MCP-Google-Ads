"""Derive the customer allowlist from one or more MCC (manager) accounts.

Instead of copying every client ID into ``GOOGLE_ADS_MCP_ALLOWED_CUSTOMER_IDS``, an
operator can name the manager account(s) in ``GOOGLE_ADS_MCP_ALLOWED_MANAGER_IDS``.
At startup the server lists each manager's client accounts (``customer_client``,
read-only GAQL) and freezes the result into the normal allowlist. Every downstream
control (client wrapper, safety layer, Merchant scope, replay) keeps enforcing the
same fail-closed allowlist; nothing is relaxed.

Rules:
* effective scope = explicit allowed IDs + the manager IDs themselves + their
  ENABLED client accounts - ``GOOGLE_ADS_MCP_EXCLUDED_CUSTOMER_IDS`` (deny wins);
* a failed or empty discovery never widens the scope: only the explicit IDs remain,
  and with a required allowlist the server refuses to start if nothing is left;
* the scope is fixed for the process lifetime. A client added to the MCC later is
  denied until the server restarts.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass, replace
from typing import Any

from .config import Settings
from .errors import GoogleAdsMcpError
from .helpers import normalize_customer_id

logger = logging.getLogger(__name__)

_QUERY = (
    "SELECT customer_client.id, customer_client.manager, customer_client.status, "
    "customer_client.level FROM customer_client"
)


@dataclass(frozen=True)
class ManagerDiscovery:
    manager_id: str
    clients: frozenset[str]
    error: str | None = None


def _default_client_factory(settings: Settings, manager_id: str) -> Any:
    from google.ads.googleads.client import GoogleAdsClient

    from .client import GOOGLE_ADS_API_VERSION

    config = dict(settings.google_ads_yaml_dict)
    config["login_customer_id"] = manager_id
    return GoogleAdsClient.load_from_dict(config, version=GOOGLE_ADS_API_VERSION)


def discover_manager_clients(
    settings: Settings,
    manager_id: str,
    client_factory: Callable[[Settings, str], Any] | None = None,
) -> ManagerDiscovery:
    """List ENABLED non-manager client accounts under ``manager_id`` (read-only)."""
    factory = client_factory or _default_client_factory
    try:
        client = factory(settings, manager_id)
        service = client.get_service("GoogleAdsService")
        found: set[str] = set()
        for batch in service.search_stream(customer_id=manager_id, query=_QUERY):
            for row in batch.results:
                item = row.customer_client
                if bool(item.manager):
                    continue
                status = getattr(item.status, "name", str(item.status))
                if status != "ENABLED":
                    continue
                found.add(normalize_customer_id(str(item.id)))
        return ManagerDiscovery(manager_id, frozenset(found))
    except Exception as exc:  # noqa: BLE001 - fail closed: never widen the scope on error
        return ManagerDiscovery(manager_id, frozenset(), error=type(exc).__name__)


def _empty_scope_error() -> GoogleAdsMcpError:
    # Downstream components read an empty allowlist as "unrestricted" when the
    # allowlist is not required, so an empty effective scope must never be returned.
    return GoogleAdsMcpError(
        "The customer allowlist resolved to no accounts. Check the manager IDs, the "
        "OAuth identity's access and GOOGLE_ADS_MCP_EXCLUDED_CUSTOMER_IDS."
    )


def resolve_manager_scope(
    settings: Settings,
    client_factory: Callable[[Settings, str], Any] | None = None,
) -> Settings:
    """Return settings whose allowlist includes the discovered MCC clients.

    Exclusions always win, with or without managers. A resolved scope is never
    empty: that would silently mean unrestricted access, so it is refused.
    """
    managers = settings.allowed_manager_ids
    excluded = frozenset(settings.excluded_customer_ids)

    if not managers:
        if not excluded:
            return settings
        if not settings.allowed_customer_ids:
            raise GoogleAdsMcpError(
                "GOOGLE_ADS_MCP_EXCLUDED_CUSTOMER_IDS needs an allowlist to subtract "
                "from: set GOOGLE_ADS_MCP_ALLOWED_CUSTOMER_IDS or "
                "GOOGLE_ADS_MCP_ALLOWED_MANAGER_IDS, or remove the exclusions."
            )
        effective = set(settings.allowed_customer_ids) - excluded
        if not effective:
            raise _empty_scope_error()
        return replace(settings, allowed_customer_ids=frozenset(effective))

    login = normalize_customer_id(settings.login_customer_id or "")
    if not login:
        if len(managers) != 1:
            raise GoogleAdsMcpError(
                "GOOGLE_ADS_MCP_ALLOWED_MANAGER_IDS lists several managers: set "
                "GOOGLE_ADS_LOGIN_CUSTOMER_ID to the one used for API access."
            )
        login = next(iter(managers))
    elif login not in managers:
        raise GoogleAdsMcpError(
            "GOOGLE_ADS_LOGIN_CUSTOMER_ID must be one of "
            "GOOGLE_ADS_MCP_ALLOWED_MANAGER_IDS when manager scope is enabled."
        )

    discovered: set[str] = set()
    for manager_id in sorted(managers):
        result = discover_manager_clients(settings, manager_id, client_factory)
        if result.error:
            logger.warning(
                "MCC scope discovery failed for one manager (%s); its clients stay "
                "outside the allowlist.",
                result.error,
            )
        discovered |= result.clients

    effective = (
        set(settings.allowed_customer_ids) | set(managers) | discovered
    ) - excluded
    if not effective:
        raise _empty_scope_error()
    logger.info(
        "Customer allowlist resolved from manager scope: %d accounts (%d discovered, "
        "%d excluded).",
        len(effective),
        len(discovered),
        len(excluded),
    )
    return replace(
        settings,
        allowed_customer_ids=frozenset(effective),
        require_customer_allowlist=True,
        login_customer_id=login,
    )
