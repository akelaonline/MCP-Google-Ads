from __future__ import annotations

import json
import os
import sqlite3
from collections.abc import Iterable
from dataclasses import asdict
from pathlib import Path

from .models import DeploymentMode, GoogleStack, SitePlatform, SiteTarget


class SiteRegistry:
    """Deterministic site registry with optional SQLite persistence."""

    def __init__(
        self,
        sites: Iterable[SiteTarget] = (),
        *,
        db_path: str | Path | None = None,
    ) -> None:
        self._sites: dict[str, SiteTarget] = {}
        self._db_path = Path(db_path) if db_path is not None else None
        if self._db_path is not None:
            self._db_path.parent.mkdir(parents=True, exist_ok=True)
            self._init_db()
            self._load()
        for site in sites:
            self.add(site)

    @classmethod
    def from_env(cls) -> "SiteRegistry":
        return cls(db_path=os.getenv("MEASUREMENT_OPS_DB", "./measurement_ops.db"))

    def _connect(self) -> sqlite3.Connection:
        if self._db_path is None:
            raise RuntimeError("registry persistence is not configured")
        connection = sqlite3.connect(self._db_path)
        connection.row_factory = sqlite3.Row
        return connection

    def _init_db(self) -> None:
        with self._connect() as db:
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS measurement_sites (
                    site_key TEXT PRIMARY KEY,
                    domain TEXT NOT NULL UNIQUE,
                    payload_json TEXT NOT NULL,
                    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                """
            )

    @staticmethod
    def _serialize(site: SiteTarget) -> str:
        return json.dumps(asdict(site), sort_keys=True)

    @staticmethod
    def _deserialize(payload: str) -> SiteTarget:
        data = json.loads(payload)
        google = data.get("google") or {}
        return SiteTarget(
            key=data["key"],
            domain=data["domain"],
            platform=SitePlatform(data["platform"]),
            deployment_mode=DeploymentMode(data["deployment_mode"]),
            google=GoogleStack(
                gtm_account_id=google.get("gtm_account_id"),
                gtm_container_id=google.get("gtm_container_id"),
                ga4_property_id=google.get("ga4_property_id"),
                google_ads_customer_id=google.get("google_ads_customer_id"),
            ),
            repository=data.get("repository"),
            wordpress_endpoint=data.get("wordpress_endpoint"),
            environment=data.get("environment", "production"),
        )

    def _load(self) -> None:
        with self._connect() as db:
            rows = db.execute(
                "SELECT site_key, payload_json FROM measurement_sites ORDER BY site_key"
            ).fetchall()
        for row in rows:
            site = self._deserialize(row["payload_json"])
            site.validate()
            self._sites[site.key] = site

    def add(self, site: SiteTarget) -> None:
        site.validate()
        if site.key in self._sites:
            raise ValueError(f"duplicate site key: {site.key}")
        domain = site.domain.lower().strip()
        if any(existing.domain.lower().strip() == domain for existing in self._sites.values()):
            raise ValueError(f"duplicate site domain: {site.domain}")

        if self._db_path is not None:
            try:
                with self._connect() as db:
                    db.execute(
                        """
                        INSERT INTO measurement_sites (site_key, domain, payload_json)
                        VALUES (?, ?, ?)
                        """,
                        (site.key, domain, self._serialize(site)),
                    )
            except sqlite3.IntegrityError as exc:
                raise ValueError(f"site key or domain already exists: {site.key} / {site.domain}") from exc

        self._sites[site.key] = site

    def get(self, key: str) -> SiteTarget:
        try:
            return self._sites[key]
        except KeyError as exc:
            raise KeyError(f"unknown site: {key}") from exc

    def list(self) -> list[SiteTarget]:
        return sorted(self._sites.values(), key=lambda site: site.key)
