from __future__ import annotations

from dataclasses import asdict
from functools import lru_cache

from fastmcp import FastMCP

from .astro import build_astro_measurement_plan
from .ga4 import GA4ReadOnly
from .ga4_admin import GA4AdminReadOnly
from .gtm import GoogleTagManagerReadOnly, GoogleTagManagerWriter
from .gtm_installer import GTMTrackingInstaller
from .jobs import JobStore
from .models import DeploymentMode, GoogleStack, SitePlatform, SiteTarget
from .planner import build_plan
from .registry import SiteRegistry
from .risk import classify_action, requires_confirmation
from .settings import MeasurementSettings
from .web_audit import WebAuditor
from .workflow import JobState

mcp = FastMCP(
    "MKT Measurement Ops",
    instructions=(
        "Measurement operations orchestrator. Audit first. Never publish GTM or deploy a site "
        "without explicit confirmation. Prefer workspace/branch changes over direct production edits."
    ),
)

registry = SiteRegistry()


@lru_cache(maxsize=1)
def _ga4_admin() -> GA4AdminReadOnly:
    return GA4AdminReadOnly.from_env()


@lru_cache(maxsize=1)
def _gtm() -> GoogleTagManagerReadOnly:
    return GoogleTagManagerReadOnly.from_env()


@lru_cache(maxsize=1)
def _gtm_writer() -> GoogleTagManagerWriter:
    return GoogleTagManagerWriter.from_env()


@lru_cache(maxsize=1)
def _gtm_installer() -> GTMTrackingInstaller:
    return GTMTrackingInstaller(_gtm_writer())


@lru_cache(maxsize=1)
def _web_auditor() -> WebAuditor:
    return WebAuditor()


@lru_cache(maxsize=1)
def _ga4() -> GA4ReadOnly:
    return GA4ReadOnly.from_env()


@lru_cache(maxsize=1)
def _jobs() -> JobStore:
    return JobStore.from_env()


@mcp.tool()
def measurement_capabilities() -> dict:
    """Show active mutation capability gates without exposing credentials."""
    settings = MeasurementSettings.from_env()
    return {
        "gtm_read": True,
        "gtm_preview": settings.gtm_enable_preview,
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
def create_measurement_job(site_key: str) -> dict:
    """Create a durable measurement job for a registered site."""
    registry.get(site_key)
    return JobStore.serialize(_jobs().create(site_key))


@mcp.tool()
def start_measurement_job(site_key: str, max_pages: int = 5) -> dict:
    """Create a job, perform a real site audit, and derive the initial tracking plan."""
    site = registry.get(site_key)
    job = _jobs().create(site_key)
    audit = _web_auditor().audit(f"https://{site.domain}", max_pages=max_pages)
    _jobs().transition(
        job.id,
        JobState.AUDITED,
        evidence={
            "kind": "audit",
            "pages_scanned": audit["pages_scanned"],
            "tracking": audit["tracking"],
            "opportunities": audit["opportunities"],
        },
    )
    opportunities = audit["opportunities"]
    goals: list[str] = []
    if opportunities["forms"]:
        goals.append("lead_form")
    if opportunities["whatsapp_links"]:
        goals.append("whatsapp_click")
    if opportunities["phone_links"]:
        goals.append("phone_click")
    if opportunities["email_links"]:
        goals.append("email_click")
    if opportunities["download_links"]:
        goals.append("file_download")
    plan = build_plan(site_key, goals).to_dict()
    _jobs().transition(job.id, JobState.PLANNED, evidence={"kind": "plan", "plan": plan})
    return {
        "job": JobStore.serialize(_jobs().get(job.id)),
        "site": asdict(site),
        "audit": audit,
        "plan": plan,
    }


@mcp.tool()
def get_measurement_job(job_id: str) -> dict:
    """Read durable measurement-job state and evidence."""
    return JobStore.serialize(_jobs().get(job_id))


@mcp.tool()
def astro_measurement_plan(site_key: str, layout_path: str = "src/layouts/Layout.astro") -> dict:
    """Return deterministic Astro files/instructions for the registered Astro site."""
    site = registry.get(site_key)
    if site.platform != SitePlatform.ASTRO:
        raise ValueError(f"site {site_key} is not registered as Astro")
    return build_astro_measurement_plan(layout_path=layout_path)


@mcp.tool()
def ga4_resolve_site_web_stream(site_key: str) -> dict:
    """Resolve the registered site's GA4 web stream and Measurement ID."""
    site = registry.get(site_key)
    property_id = site.google.ga4_property_id
    if not property_id:
        raise ValueError(f"site {site_key} has no ga4_property_id registered")
    return _ga4_admin().resolve_web_stream(property_id, site.domain)


@mcp.tool()
def ga4_realtime_events(property_id: str) -> dict[str, int]:
    """Read current GA4 realtime event counts."""
    return _ga4().realtime_events(property_id)


@mcp.tool()
def ga4_verify_events(property_id: str, expected_events: list[str], job_id: str | None = None) -> dict:
    """Verify production events in GA4 Realtime after publish."""
    result = _ga4().verify_events(property_id, expected_events)
    if job_id is not None:
        job = _jobs().get(job_id)
        if job.state != JobState.PUBLISHED:
            raise ValueError("job must be published before GA4 production verification")
        evidence = {
            "kind": "production_verification",
            "source": "ga4_realtime",
            "passed": result["passed"],
            "property_id": property_id,
            "checks": result["checks"],
        }
        if result["passed"]:
            _jobs().transition(job_id, JobState.PRODUCTION_VERIFIED, evidence=evidence)
        else:
            job.evidence.append(evidence)
            _jobs().save(job)
    return result


@mcp.tool()
def audit_site_url(url: str, max_pages: int = 5) -> dict:
    """Read-only browser audit. Never clicks or submits forms."""
    return _web_auditor().audit(url, max_pages=max_pages)


@mcp.tool()
def audit_and_plan_site(site_key: str, max_pages: int = 5) -> dict:
    """Audit a registered site and derive a conservative standard tracking plan."""
    site = registry.get(site_key)
    audit = _web_auditor().audit(f"https://{site.domain}", max_pages=max_pages)
    opportunities = audit["opportunities"]
    goals: list[str] = []
    if opportunities["forms"]:
        goals.append("lead_form")
    if opportunities["whatsapp_links"]:
        goals.append("whatsapp_click")
    if opportunities["phone_links"]:
        goals.append("phone_click")
    if opportunities["email_links"]:
        goals.append("email_click")
    if opportunities["download_links"]:
        goals.append("file_download")
    plan = build_plan(site_key, goals).to_dict()
    return {"site": asdict(site), "audit": audit, "plan": plan}


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


def _require_planned_job(job_id: str):
    job = _jobs().get(job_id)
    if job.state != JobState.PLANNED:
        raise ValueError("job must be in planned state while installing GTM tracking")
    return job


def _measurement_id_for_job(job_id: str, requested: str | None = None) -> str:
    job = _require_planned_job(job_id)
    if requested and requested.strip():
        return requested.strip()
    site = registry.get(job.site_key)
    property_id = site.google.ga4_property_id
    if not property_id:
        raise ValueError(
            f"site {site.key} has no GA4 property registered; set ga4_property_id or pass measurement_id"
        )
    return _ga4_admin().resolve_web_stream(property_id, site.domain)["measurement_id"]


def _record_install_evidence(job_id: str, operation: str, result: dict) -> dict:
    job = _jobs().get(job_id)
    job.evidence.append(
        {
            "kind": "gtm_install",
            "operation": operation,
            "created": result.get("created", {}),
        }
    )
    _jobs().save(job)
    return result


@mcp.tool()
def gtm_install_google_tag(
    job_id: str,
    account_id: str,
    container_id: str,
    workspace_id: str,
    tag_id: str | None = None,
) -> dict:
    """Idempotently install the base Google tag, auto-resolving GA4 when tag_id is omitted."""
    resolved_tag_id = _measurement_id_for_job(job_id, tag_id)
    result = _gtm_installer().install_google_tag(
        account_id,
        container_id,
        workspace_id,
        tag_id=resolved_tag_id,
    )
    return _record_install_evidence(job_id, "google_tag", result)


@mcp.tool()
def gtm_install_standard_click_event(
    job_id: str,
    account_id: str,
    container_id: str,
    workspace_id: str,
    event_name: str,
    measurement_id: str | None = None,
) -> dict:
    """Install a typed standard click event, auto-resolving the site's GA4 stream by default."""
    resolved_measurement_id = _measurement_id_for_job(job_id, measurement_id)
    result = _gtm_installer().install_standard_click_event(
        account_id,
        container_id,
        workspace_id,
        event_name=event_name,
        measurement_id=resolved_measurement_id,
    )
    return _record_install_evidence(job_id, f"standard_click:{event_name}", result)


@mcp.tool()
def gtm_install_native_form_event(
    job_id: str,
    account_id: str,
    container_id: str,
    workspace_id: str,
    measurement_id: str | None = None,
    event_name: str = "generate_lead",
    form_id: str | None = None,
    page_path: str | None = None,
) -> dict:
    """Install a native form-submit event, auto-resolving the site's GA4 stream by default."""
    resolved_measurement_id = _measurement_id_for_job(job_id, measurement_id)
    result = _gtm_installer().install_native_form_event(
        account_id,
        container_id,
        workspace_id,
        measurement_id=resolved_measurement_id,
        event_name=event_name,
        form_id=form_id,
        page_path=page_path,
    )
    return _record_install_evidence(job_id, f"native_form:{event_name}", result)


@mcp.tool()
def gtm_install_provider_form_event(
    job_id: str,
    account_id: str,
    container_id: str,
    workspace_id: str,
    provider: str,
    measurement_id: str | None = None,
    event_name: str = "generate_lead",
) -> dict:
    """Install a versioned provider listener, auto-resolving the site's GA4 stream by default."""
    resolved_measurement_id = _measurement_id_for_job(job_id, measurement_id)
    result = _gtm_installer().install_provider_form_event(
        account_id,
        container_id,
        workspace_id,
        provider=provider,
        measurement_id=resolved_measurement_id,
        event_name=event_name,
    )
    return _record_install_evidence(job_id, f"provider_form:{provider}:{event_name}", result)


@mcp.tool()
def gtm_install_custom_event(
    job_id: str,
    account_id: str,
    container_id: str,
    workspace_id: str,
    data_layer_event: str,
    ga4_event_name: str,
    measurement_id: str | None = None,
) -> dict:
    """Map an existing dataLayer event to GA4, auto-resolving the site's web stream by default."""
    resolved_measurement_id = _measurement_id_for_job(job_id, measurement_id)
    result = _gtm_installer().install_custom_event(
        account_id,
        container_id,
        workspace_id,
        measurement_id=resolved_measurement_id,
        data_layer_event=data_layer_event,
        ga4_event_name=ga4_event_name,
    )
    return _record_install_evidence(job_id, f"custom_event:{data_layer_event}", result)


@mcp.tool()
def gtm_quick_preview(account_id: str, container_id: str, workspace_id: str) -> dict:
    """Compile a workspace preview. Requires GTM_ENABLE_PREVIEW=true."""
    return _gtm_writer().quick_preview(account_id, container_id, workspace_id)


@mcp.tool()
def prepare_gtm_job(job_id: str, account_id: str, container_id: str, workspace_id: str) -> dict:
    """Move a planned job to prepared only when GTM has no conflicts and quick preview compiles."""
    job = _jobs().get(job_id)
    if job.state != JobState.PLANNED:
        raise ValueError("job must be in planned state before GTM preparation")
    status = _gtm().get_workspace_status(account_id, container_id, workspace_id)
    conflicts = status.get("mergeConflict", [])
    if conflicts:
        raise ValueError(f"GTM workspace has {len(conflicts)} merge conflict(s)")
    preview = _gtm_writer().quick_preview(account_id, container_id, workspace_id)
    if preview.get("compilerError") is True:
        raise ValueError("GTM quick preview reported compiler errors")
    if not preview.get("containerVersion"):
        raise ValueError("GTM quick preview did not return a containerVersion")
    _jobs().transition(
        job_id,
        JobState.PREPARED,
        evidence={
            "kind": "gtm_prepare",
            "account_id": account_id,
            "container_id": container_id,
            "workspace_id": workspace_id,
            "workspace_changes": len(status.get("workspaceChange", [])),
            "compiler_error": False,
        },
    )
    return {
        "job": JobStore.serialize(_jobs().get(job_id)),
        "workspace_status": status,
        "preview": preview,
    }


@mcp.tool()
def gtm_create_workspace(account_id: str, container_id: str, name: str, description: str = "") -> dict:
    """Create an isolated GTM workspace. Requires GTM_ENABLE_WRITES=true."""
    return _gtm_writer().create_workspace(account_id, container_id, name, description)


@mcp.tool()
def create_measurement_version(
    job_id: str,
    account_id: str,
    container_id: str,
    workspace_id: str,
    name: str,
    notes: str = "",
) -> dict:
    """Create a saved GTM version only after preview verification; does not publish."""
    job = _jobs().get(job_id)
    if job.state != JobState.PREVIEW_VERIFIED:
        raise ValueError("job must be preview_verified before creating the release version")
    result = _gtm_writer().create_version(
        account_id,
        container_id,
        workspace_id,
        name=name,
        notes=notes,
    )
    container_version = result.get("containerVersion", result)
    version_id = container_version.get("containerVersionId") if isinstance(container_version, dict) else None
    if not version_id:
        raise ValueError("GTM create_version returned no containerVersionId")
    job.evidence.append(
        {
            "kind": "gtm_version",
            "account_id": account_id,
            "container_id": container_id,
            "workspace_id": workspace_id,
            "version_id": version_id,
            "name": name,
        }
    )
    _jobs().save(job)
    return {"job": JobStore.serialize(job), "gtm": result, "version_id": version_id}


@mcp.tool()
def record_preview_verification(job_id: str, passed: bool, checks: list[str], confirm: bool = False) -> dict:
    """Record operator/browser preview evidence. This is temporary until automated Tag Assistant preview lands."""
    if confirm is not True:
        raise PermissionError("recording preview verification requires confirm=true")
    job = _jobs().get(job_id)
    if job.state != JobState.PREPARED:
        raise ValueError("job must be prepared before preview verification")
    if not passed:
        job.evidence.append({"kind": "preview_verification", "passed": False, "checks": checks})
        _jobs().save(job)
        return JobStore.serialize(job)
    verified = _jobs().transition(
        job_id,
        JobState.PREVIEW_VERIFIED,
        evidence={"kind": "preview_verification", "passed": True, "checks": checks},
    )
    return JobStore.serialize(verified)


@mcp.tool()
def approve_measurement_job(job_id: str, confirm: bool = False) -> dict:
    """Approve a preview-verified, versioned job for publish."""
    if confirm is not True:
        raise PermissionError("job approval requires confirm=true")
    job = _jobs().get(job_id)
    if not any(item.get("kind") == "gtm_version" and item.get("version_id") for item in job.evidence):
        raise ValueError("job must have a saved GTM version before approval")
    approved = _jobs().transition(job_id, JobState.APPROVED)
    return JobStore.serialize(approved)


@mcp.tool()
def publish_measurement_job(
    job_id: str,
    account_id: str,
    container_id: str,
    version_id: str,
    confirm: bool = False,
) -> dict:
    """Publish an approved GTM version and move the durable job to published."""
    job = _jobs().get(job_id)
    if job.state != JobState.APPROVED:
        raise ValueError("job must be approved before publish")
    saved_versions = [
        item.get("version_id")
        for item in job.evidence
        if item.get("kind") == "gtm_version" and item.get("version_id")
    ]
    if not saved_versions or version_id not in saved_versions:
        raise ValueError("version_id was not created and recorded by this measurement job")
    result = _gtm_writer().publish_version(
        account_id,
        container_id,
        version_id,
        confirm=confirm,
    )
    published = _jobs().transition(
        job_id,
        JobState.PUBLISHED,
        evidence={
            "kind": "publish",
            "account_id": account_id,
            "container_id": container_id,
            "version_id": version_id,
        },
    )
    return {"job": JobStore.serialize(published), "gtm": result}


def main() -> None:
    mcp.run()


if __name__ == "__main__":
    main()
