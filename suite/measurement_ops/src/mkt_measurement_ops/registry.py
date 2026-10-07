from __future__ import annotations

from collections.abc import Iterable

from .models import SiteTarget


class SiteRegistry:
    """Small deterministic registry; persistence/provider comes after the POC."""

    def __init__(self, sites: Iterable[SiteTarget] = ()) -> None:
        self._sites: dict[str, SiteTarget] = {}
        for site in sites:
            self.add(site)

    def add(self, site: SiteTarget) -> None:
        site.validate()
        if site.key in self._sites:
            raise ValueError(f"duplicate site key: {site.key}")
        domain = site.domain.lower().strip()
        if any(existing.domain.lower().strip() == domain for existing in self._sites.values()):
            raise ValueError(f"duplicate site domain: {site.domain}")
        self._sites[site.key] = site

    def get(self, key: str) -> SiteTarget:
        try:
            return self._sites[key]
        except KeyError as exc:
            raise KeyError(f"unknown site: {key}") from exc

    def list(self) -> list[SiteTarget]:
        return sorted(self._sites.values(), key=lambda site: site.key)
