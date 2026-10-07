from __future__ import annotations

from dataclasses import asdict

from fastmcp import FastMCP

from .models import DeploymentMode, GoogleStack, SitePlatform, SiteTarget
from .registry import SiteRegistry
from .risk import classify_action, requires_confirmation

mcp = FastMCP(
    "MKT Measurement Ops",
    instructions=(
        "Measurement operations orchestrator. Audit first. Never publish GTM or deploy a site "
        "without explicit confirmation. Prefer workspace/branch changes over direct production edits."
    ),
)

registry = SiteRegistry()


@mcp.tool()
def list_sites() -> list[dict]:
    """List sites known to the Measurement Ops registry."""
    return [asdict(site) for site in registry.list()]


@mcp.tool()
def register_site(
    key: str,
    domain: str,
    platform: str,
    deployment_mode: str,
    repository: str | None = None,
    wordpress_endpoint: str | None = None,
    gtm_account_id: str | None = None,
    gtm_container_id: str | None = None,
    ga4_property_id: str | None = None,
    google_ads_customer_id: str | None = None,
) -> dict:
    """Register a site without storing credentials or secrets."""
    site = SiteTarget(
        key=key,
        domain=domain,
        platform=SitePlatform(platform),
        deployment_mode=DeploymentMode(deployment_mode),
        repository=repository,
        wordpress_endpoint=wordpress_endpoint,
        google=GoogleStack(
            gtm_account_id=gtm_account_id,
            gtm_container_id=gtm_container_id,
            ga4_property_id=ga4_property_id,
            google_ads_customer_id=google_ads_customer_id,
        ),
    )
    registry.add(site)
    return asdict(site)


@mcp.tool()
def get_site(key: str) -> dict:
    """Return one site's routing metadata."""
    return asdict(registry.get(key))


@mcp.tool()
def classify_measurement_action(action: str) -> dict:
    """Return the suite's safety classification for an operation."""
    risk = classify_action(action)
    return {
        "action": action,
        "risk": risk.value,
        "requires_confirmation": requires_confirmation(action),
    }


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
