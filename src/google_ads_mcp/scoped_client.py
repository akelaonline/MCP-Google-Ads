"""Production-scoped Google Ads client extensions.

The base wrapper already enforces request-customer allowlists, recursive mutation
ownership, and manager-side ``customer_client`` / ``customer_client_link`` row
filtering. This subclass adds the inverse client-side ``customer_manager_link``
surface, whose output-only ``manager_customer`` field can otherwise reveal a
manager account outside the deployment allowlist.
"""

from __future__ import annotations

from typing import Any

from .client import (
    GoogleAdsClientWrapper,
    _customer_id_from_resource_name,
    _gaql_from_resource,
)
from .errors import GoogleAdsMcpError


class ScopedGoogleAdsClientWrapper(GoogleAdsClientWrapper):
    """GoogleAdsClientWrapper with complete MCC link-read allowlist filtering."""

    def _filter_allowed_hierarchy_rows(
        self, query: str, rows: list[dict[str, Any]]
    ) -> list[dict[str, Any]]:
        # Keep all existing manager-side filtering in the base class first.
        rows = super()._filter_allowed_hierarchy_rows(query, rows)
        if not self._allowed_customer_ids or not rows:
            return rows

        if _gaql_from_resource(query) != "customer_manager_link":
            return rows

        filtered: list[dict[str, Any]] = []
        for row in rows:
            data = row.get("customer_manager_link") or {}
            manager_resource = str(data.get("manager_customer") or "").strip()
            manager_id = _customer_id_from_resource_name(manager_resource)
            if manager_id is None:
                raise GoogleAdsMcpError(
                    "A customer_manager_link GAQL query in an allowlisted deployment "
                    "must select customer_manager_link.manager_customer so linked "
                    "manager customers can be filtered."
                )
            if manager_id in self._allowed_customer_ids:
                filtered.append(row)
        return filtered
