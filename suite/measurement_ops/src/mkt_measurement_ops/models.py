from __future__ import annotations

import ipaddress
import re
from dataclasses import dataclass, field
from enum import StrEnum


class SitePlatform(StrEnum):
    WORDPRESS = "wordpress"
    ASTRO = "astro"
    STATIC = "static"
    OTHER = "other"


class DeploymentMode(StrEnum):
    WORDPRESS_MCP = "wordpress_mcp"
    GITHUB = "github"
    MANUAL = "manual"


@dataclass(frozen=True, slots=True)
class GoogleStack:
    gtm_account_id: str | None = None
    gtm_container_id: str | None = None
    gtm_public_id: str | None = None
    ga4_property_id: str | None = None
    google_ads_customer_id: str | None = None


@dataclass(frozen=True, slots=True)
class SiteTarget:
    key: str
    domain: str
    platform: SitePlatform
    deployment_mode: DeploymentMode
    google: GoogleStack = field(default_factory=GoogleStack)
    repository: str | None = None
    wordpress_endpoint: str | None = None
    environment: str = "production"

    def validate(self) -> None:
        if not self.key.strip():
            raise ValueError("site key is required")
        if not self.domain.strip():
            raise ValueError("domain is required")
        # Registry domains are hostnames, never arbitrary URLs or destinations.
        domain = self.domain.strip()
        hostname_pattern = (
            r"(?=.{1,253}$)(?:[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?\\.)+"
            r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?$"
        )
        if not re.fullmatch(hostname_pattern, domain):
            raise ValueError("domain must be a bare public DNS hostname without URL, port or path")
        if domain.lower().endswith((".local", ".internal", ".localhost", ".invalid")):
            raise ValueError("private DNS suffixes are not allowed")
        try:
            ipaddress.ip_address(domain)
        except ValueError:
            pass
        else:
            raise ValueError("site domain cannot be an IP address")
        if self.platform == SitePlatform.ASTRO and self.deployment_mode == DeploymentMode.GITHUB:
            if not self.repository:
                raise ValueError("Astro/GitHub sites require repository")
        if self.platform == SitePlatform.WORDPRESS and self.deployment_mode == DeploymentMode.WORDPRESS_MCP:
            if not self.wordpress_endpoint:
                raise ValueError("WordPress MCP sites require wordpress_endpoint")
