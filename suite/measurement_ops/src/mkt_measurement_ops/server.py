from __future__ import annotations

from dataclasses import asdict
from functools import lru_cache

from fastmcp import FastMCP

from .gtm import GoogleTagManagerReadOnly, GoogleTagManagerWriter
from .models import DeploymentMode, GoogleStack, SitePlatform, SiteTarget
from .planner import build_plan
from .registry import SiteRegistry
from .risk import classify_action, requires_confirmation
from .settings import MeasurementSettings

mcp = FastMCP(
    "MKT Measurement Ops",
    instructions=(
        "Measurement operations orchestrator. Audit first. Never publish GTM or deploy a site "
        "without explicit confirmation. Prefer workspace/branch changes over direct production edits."
    ),
)

registry = SiteRegistry()


@lru_cache(maxsize=1)
def _gtm() -> GoogleTagManagerReadOnly:
    return GoogleTagManagerReadOnly.from_env()


@lru_cache(maxsize=1)
def _gtm_writer() -> GoogleTagManagerWriter:
    return GoogleTagManagerWriter.from_env()


@mcp.tool()
def measurement_capabilities() -> dict:
    """Show active mutation capability gates without exposing credentials."""
    settings = MeasurementSettings.from_env()
    return {
        "gtm_read": True,
        "gtm_write": settings.gtm_enable_writes,
        "gtm_publish": settings.gtm_enable_publish,
        "publish_requires_confirm": True,
        "site_deploy_requires_confirm": True,
    }


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
def build_tracking_plan(site_key: str, goals: list[str], require_consent_audit: bool = True) -> dict:
    """Build a deterministic measurement plan for a registered site."""
    registry.get(site_key)
    return build_plan(site_key, goals, require_consent_audit=require_consent_audit).to_dict()


@mcp.tool()
def classify_measurement_action(action: str) -> dict:
    """Return the suite's safety classification for an operation."""
    risk = classify_action(action)
    return {
        "action": action,
        "risk": risk.value,
        "requires_confirmation": requires_confirmation(action),
    }


@mcp.tool()
def gtm_list_accounts() -> list[dict]:
    """List GTM accounts accessible to the configured read-only identity."""
    return _gtm().list_accounts()


@mcp.tool()
def gtm_list_containers(account_id: str) -> list[dict]:
    """List containers in one GTM account."""
    return _gtm().list_containers(account_id)


@mcp.tool()
def gtm_list_workspaces(account_id: str, container_id: str) -> list[dict]:
    """List workspaces in one GTM container."""
    return _gtm().list_workspaces(account_id, container_id)


@mcp.tool()
def gtm_audit_workspace(account_id: str, container_id: str, workspace_id: str) -> dict:
    """Read-only workspace inventory plus live-version context."""
    client = _gtm()
    tags = client.list_tags(account_id, container_id, workspace_id)
    triggers = client.list_triggers(account_id, container_id, workspace_id)
    variables = client.list_variables(account_id, container_id, workspace_id)
    status = client.get_workspace_status(account_id, container_id, workspace_id)
    live = client.get_live_version(account_id, container_id)
    return {
        "account_id": account_id,
        "container_id": container_id,
        "workspace_id": workspace_id,
        "counts": {
            "tags": len(tags),
            "triggers": len(triggers),
            "variables": len(variables),
        },
        "tags": tags,
        "triggers": triggers,
        "variables": variables,
        "workspace_status": status,
        "live_version": live,
    }


@mcp.tool()
def gtm_quick_preview(account_id: str, container_id: str, workspace_id: str) -> dict:
    """Compile a workspace preview without publishing it."""
    return _gtm().quick_preview(account_id, container_id, workspace_id)


@mcp.tool()
def gtm_create_workspace(account_id: str, container_id: str, name: str, description: str = "") -> dict:
    """Create an isolated GTM workspace. Requires GTM_ENABLE_WRITES=true."""
    return _gtm_writer().create_workspace(account_id, container_id, name, description)


@mcp.tool()
def gtm_create_version(
    account_id: str,
    container_id: str,
    workspace_id: str,
    name: str,
    notes: str = "",
) -> dict:
    """Create a saved GTM container version from a verified workspace; does not publish."""
    return _gtm_writer().create_version(
        account_id,
        container_id,
        workspace_id,
        name=name,
        notes=notes,
    )


@mcp.tool()
def gtm_publish_version(
    account_id: str,
    container_id: str,
    version_id: str,
    confirm: bool = False,
) -> dict:
    """Publish a GTM version live. Requires write+publish gates and confirm=true."""
    return _gtm_writer().publish_version(
        account_id,
        container_id,
        version_id,
        confirm=confirm,
    )


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
