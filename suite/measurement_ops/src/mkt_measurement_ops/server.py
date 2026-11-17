from __future__ import annotations

from dataclasses import asdict, replace
from functools import lru_cache

from fastmcp import FastMCP

from .astro import build_astro_measurement_plan
from .credentials import credential_configuration_status
from .ga4 import GA4ReadOnly
from .ga4_admin import GA4AdminReadOnly, _host
from .gtm import GoogleTagManagerReadOnly, GoogleTagManagerWriter
from .gtm_installer import GTMTrackingInstaller
from .install_plan import build_installation_steps
from .jobs import JobStore
from .models import DeploymentMode, GoogleStack, SitePlatform, SiteTarget
from .planner import build_plan
from .registry import LazySiteRegistry
from .risk import classify_action, requires_confirmation
from .settings import MeasurementSettings
from .web_audit import WebAuditor
from .verification import validated_browser_attestation
from .workflow import JobState

mcp = FastMCP(
    "MKT Measurement Ops",
    instructions=(
        "Measurement operations orchestrator. Audit first. Never publish GTM or deploy a site "
        "without explicit confirmation. Prefer workspace/branch changes over direct production edits."
    ),
)

registry = LazySiteRegistry()


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
        # Means configuration present only, NOT that Google authorization
        # or any API request has been verified in real time.
        **credential_configuration_status(),
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
    gtm_public_id: str | None = None,
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
            gtm_public_id=gtm_public_id,
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
def update_site_google_stack(
    site_key: str,
    gtm_account_id: str | None = None,
    gtm_container_id: str | None = None,
    gtm_public_id: str | None = None,
    ga4_property_id: str | None = None,
    google_ads_customer_id: str | None = None,
) -> dict:
    """Update non-secret Google routing IDs for a registered site."""
    site = registry.get(site_key)
    google = replace(
        site.google,
        gtm_account_id=gtm_account_id if gtm_account_id is not None else site.google.gtm_account_id,
        gtm_container_id=gtm_container_id if gtm_container_id is not None else site.google.gtm_container_id,
        gtm_public_id=gtm_public_id if gtm_public_id is not None else site.google.gtm_public_id,
        ga4_property_id=ga4_property_id if ga4_property_id is not None else site.google.ga4_property_id,
        google_ads_customer_id=(
            google_ads_customer_id
            if google_ads_customer_id is not None
            else site.google.google_ads_customer_id
        ),
    )
    updated = replace(site, google=google)
    registry.replace(updated)
    return asdict(updated)


@mcp.tool()
def create_site_gtm_container(
    site_key: str,
    account_id: str | None = None,
    name: str | None = None,
    confirm: bool = False,
) -> dict:
    """Create a web GTM container for a site that has no mapped container."""
    if confirm is not True:
        raise PermissionError("creating a GTM container requires confirm=true")
    site = registry.get(site_key)
    if site.google.gtm_container_id or site.google.gtm_public_id:
        raise ValueError("site already has a GTM container mapped")
    resolved_account = (account_id or site.google.gtm_account_id or "").strip()
    if not resolved_account:
        raise ValueError("gtm account_id is required to create a new container")

    result = _gtm_writer().create_container(
        resolved_account,
        name=name or f"MKT - {site.domain}",
        domain=site.domain,
    )
    container_id = str(result.get("containerId") or "")
    public_id = str(result.get("publicId") or "")
    if not container_id or not public_id:
        raise ValueError("GTM create_container returned incomplete identity")

    updated = replace(
        site,
        google=replace(
            site.google,
            gtm_account_id=resolved_account,
            gtm_container_id=container_id,
            gtm_public_id=public_id,
        ),
    )
    registry.replace(updated)
    return {"site": asdict(updated), "gtm": result}


@mcp.tool()
def onboard_site_measurement(site_key: str) -> dict:
    """Audit one live page and persist unambiguous GTM/GA4 routing discovered from actual page IDs."""
    site = registry.get(site_key)
    audit = _web_auditor().audit(f"https://{site.domain}", max_pages=1)
    tracking = audit["tracking"]
    notes: list[str] = []
    google = site.google

    observed_gtm = tracking.get("gtm_ids", [])
    if not google.gtm_container_id:
        if len(observed_gtm) == 1:
            discovered = _gtm().discover_container(public_id=observed_gtm[0])
            google = replace(
                google,
                gtm_account_id=discovered["account_id"],
                gtm_container_id=discovered["container_id"],
                gtm_public_id=discovered["public_id"],
            )
            notes.append(f"linked observed GTM container {discovered['public_id']}")
        elif len(observed_gtm) > 1:
            notes.append("multiple GTM public IDs observed; no container was auto-linked")
        else:
            notes.append("no GTM public ID observed; site may need a new GTM installation")

    observed_ga4 = tracking.get("ga4_ids", [])
    if not google.ga4_property_id:
        if len(observed_ga4) == 1:
            discovered_ga4 = _ga4_admin().discover_property_by_measurement_id(observed_ga4[0])
            stream_domain = _host(str(discovered_ga4.get("default_uri") or ""))
            if stream_domain != _host(site.domain):
                notes.append(
                    "observed GA4 stream belongs to another registered domain; "
                    "property was not auto-linked"
                )
            else:
                google = replace(google, ga4_property_id=discovered_ga4["property_id"])
                notes.append(
                    f"linked observed GA4 stream {discovered_ga4['measurement_id']} "
                    f"to property {discovered_ga4['property_id']}"
                )
        elif len(observed_ga4) > 1:
            notes.append("multiple GA4 Measurement IDs observed; no property was auto-linked")
        else:
            notes.append("no GA4 Measurement ID observed; property remains unlinked")

    updated = replace(site, google=google)
    if updated != site:
        registry.replace(updated)

    resolved_stream = None
    if updated.google.ga4_property_id:
        try:
            resolved_stream = _ga4_admin().resolve_web_stream(
                updated.google.ga4_property_id,
                updated.domain,
            )
        except LookupError as exc:
            notes.append(f"GA4 stream resolution needs review: {exc}")

    return {
        "site": asdict(updated),
        "observed_tracking": tracking,
        "ga4_web_stream": resolved_stream,
        "notes": notes,
    }


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
    if opportunities["lead_forms"]:
        goals.append("lead_form")
    if opportunities["newsletter_forms"]:
        goals.append("newsletter_signup")
    if opportunities["signup_forms"]:
        goals.append("sign_up")
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
    if not site.google.gtm_public_id:
        raise ValueError(f"site {site_key} has no gtm_public_id registered")
    return build_astro_measurement_plan(
        gtm_public_id=site.google.gtm_public_id,
        layout_path=layout_path,
    )


@mcp.tool()
def wordpress_measurement_plan(site_key: str) -> dict:
    """Return the exact WordPress MCP ability invocation needed to install the registered GTM container."""
    site = registry.get(site_key)
    if site.platform != SitePlatform.WORDPRESS:
        raise ValueError(f"site {site_key} is not registered as WordPress")
    if not site.wordpress_endpoint:
        raise ValueError(f"site {site_key} has no wordpress_endpoint registered")
    if not site.google.gtm_public_id:
        raise ValueError(f"site {site_key} has no gtm_public_id registered")
    return {
        "endpoint": site.wordpress_endpoint,
        "ability": "mkt-measurement/set-gtm-container",
        "arguments": {
            "gtm_container_id": site.google.gtm_public_id,
            "enabled": True,
            "confirm": False,
        },
        "precondition": "run live-site audit first and stop if an existing GTM bootstrap is already present",
        "verification": [
            "bridge get-config returns the same GTM public ID",
            "live HTML contains exactly one GTM head bootstrap",
            "live HTML contains exactly one GTM noscript iframe",
            "web audit observes the same GTM public ID after deployment",
        ],
    }


@mcp.tool()
def site_deployment_plan(site_key: str, layout_path: str = "src/layouts/Layout.astro") -> dict:
    """Return the platform-specific GTM installation plan without changing production."""
    site = registry.get(site_key)
    if site.platform == SitePlatform.WORDPRESS:
        return wordpress_measurement_plan(site_key)
    if site.platform == SitePlatform.ASTRO:
        return astro_measurement_plan(site_key, layout_path)
    raise ValueError(f"no automated deployment plan for platform {site.platform.value}")


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


def _job_expected_events(job) -> list[str]:
    plan = _latest_evidence(job, "plan")
    if plan is None:
        raise ValueError("job has no audited measurement plan")
    return sorted({
        item["event_name"]
        for item in plan.get("plan", {}).get("events", [])
        if item.get("event_name")
    })


@mcp.tool()
def record_production_browser_attestation(
    job_id: str,
    page_url: str,
    observed_gtm_public_id: str,
    observed_measurement_id: str,
    observed_network_events: list[str],
    consent_checked: bool,
    confirm: bool = False,
) -> dict:
    """Record operator-attested browser/network QA after publish; not autonomous proof."""
    if confirm is not True:
        raise PermissionError("recording production browser QA requires confirm=true")
    job = _jobs().get(job_id)
    if job.state != JobState.PUBLISHED:
        raise ValueError("job must be published before production browser attestation")
    site = registry.get(job.site_key)
    property_id = site.google.ga4_property_id
    if not property_id:
        raise ValueError("site has no registered GA4 property")
    stream = _ga4_admin().resolve_web_stream(property_id, site.domain)
    evidence = validated_browser_attestation(
        site_domain=site.domain,
        page_url=page_url,
        registered_gtm_public_id=site.google.gtm_public_id or "",
        observed_gtm_public_id=observed_gtm_public_id,
        expected_measurement_id=stream["measurement_id"],
        observed_measurement_id=observed_measurement_id,
        expected_events=_job_expected_events(job),
        observed_network_events=observed_network_events,
        consent_checked=consent_checked,
    )
    job.evidence.append(evidence)
    _jobs().save(job)
    return {"job": JobStore.serialize(job), "evidence": evidence}


@mcp.tool()
def ga4_verify_events(property_id: str, expected_events: list[str], job_id: str | None = None) -> dict:
    """Read aggregate GA4 Realtime counts; managed jobs also require prior browser-side QA."""
    if job_id is not None:
        job = _jobs().get(job_id)
        if job.state != JobState.PUBLISHED:
            raise ValueError("job must be published before GA4 production verification")
        site = registry.get(job.site_key)
        if not site.google.ga4_property_id or property_id != site.google.ga4_property_id:
            raise ValueError("GA4 property does not match the registered job site")
        planned = _job_expected_events(job)
        if sorted(set(expected_events)) != planned:
            raise ValueError("GA4 verification must include every expected event in the job plan")
        attestation = _latest_evidence(job, "production_browser_attestation")
        if not attestation or attestation.get("passed") is not True:
            raise ValueError("browser-side production QA is required before GA4 completion")
        if sorted(attestation.get("verified_events", [])) != planned:
            raise ValueError("browser attestation does not cover the complete job plan")

    result = _ga4().verify_events(property_id, expected_events)
    if job_id is not None:
        evidence = {
            "kind": "production_verification",
            "source": "ga4_realtime_plus_operator_browser_attestation",
            "passed": result["passed"],
            "property_id": property_id,
            "checks": result["checks"],
            "automation_level": "operator_attested",
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
    if opportunities["lead_forms"]:
        goals.append("lead_form")
    if opportunities["newsletter_forms"]:
        goals.append("newsletter_signup")
    if opportunities["signup_forms"]:
        goals.append("sign_up")
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


def _latest_evidence(job, kind: str) -> dict | None:
    return next(
        (item for item in reversed(job.evidence) if item.get("kind") == kind),
        None,
    )


def _job_workspace(job_id: str) -> tuple[str, str, str]:
    job = _require_planned_job(job_id)
    site = registry.get(job.site_key)
    evidence = _latest_evidence(job, "gtm_workspace")
    if evidence is None:
        raise ValueError("job has no managed GTM workspace; call create_job_workspace first")
    account_id = str(evidence.get("account_id") or "")
    container_id = str(evidence.get("container_id") or "")
    workspace_id = str(evidence.get("workspace_id") or "")
    if not account_id or not container_id or not workspace_id:
        raise ValueError("job GTM workspace evidence is incomplete")
    if site.google.gtm_account_id and site.google.gtm_account_id != account_id:
        raise ValueError("job workspace account no longer matches the registered site")
    if site.google.gtm_container_id and site.google.gtm_container_id != container_id:
        raise ValueError("job workspace container no longer matches the registered site")
    return account_id, container_id, workspace_id


def _manual_review_pending(job) -> bool:
    audit = _latest_evidence(job, "audit")
    if audit is None:
        return True
    plan = build_installation_steps(
        audit.get("opportunities") or {},
        tracking=audit.get("tracking"),
    )
    if not plan["manual_review"]:
        return False
    return not any(item.get("kind") == "manual_review_resolution" for item in job.evidence)


def _measurement_id_for_job(job_id: str, requested: str | None = None) -> str:
    """Resolve from the job's registered GA4 property; never trust a cross-site override."""
    job = _require_planned_job(job_id)
    site = registry.get(job.site_key)
    property_id = site.google.ga4_property_id
    if not property_id:
        raise ValueError(
            f"site {site.key} has no GA4 property registered; complete GA4 onboarding before installing tags"
        )
    resolved = _ga4_admin().resolve_web_stream(property_id, site.domain)["measurement_id"]
    if requested is not None and requested.strip().upper() != resolved.upper():
        raise ValueError("requested Measurement ID does not match the registered site's GA4 web stream")
    return resolved


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
def create_job_workspace(
    job_id: str,
    name: str | None = None,
    description: str = "",
) -> dict:
    """Create or reuse the isolated GTM workspace owned by this planned job."""
    job = _require_planned_job(job_id)
    existing = _latest_evidence(job, "gtm_workspace")
    if existing:
        return {"job": JobStore.serialize(job), "workspace": existing, "reused": True}

    site = registry.get(job.site_key)
    account_id = site.google.gtm_account_id
    container_id = site.google.gtm_container_id
    if not account_id or not container_id:
        raise ValueError("site must have gtm_account_id and gtm_container_id before workspace creation")

    workspace_name = name or f"MKT Measurement - {site.key} - {job.id[:8]}"
    result = _gtm_writer().create_workspace(
        account_id,
        container_id,
        workspace_name,
        description,
    )
    workspace_id = str(result.get("workspaceId") or "")
    if not workspace_id:
        path = str(result.get("path") or "")
        workspace_id = path.split("/")[-1] if path else ""
    if not workspace_id:
        raise ValueError("GTM create_workspace returned no workspaceId")

    evidence = {
        "kind": "gtm_workspace",
        "account_id": account_id,
        "container_id": container_id,
        "workspace_id": workspace_id,
        "name": result.get("name") or workspace_name,
    }
    job.evidence.append(evidence)
    _jobs().save(job)
    return {"job": JobStore.serialize(job), "workspace": evidence, "gtm": result, "reused": False}


@mcp.tool()
def recommend_job_installation(job_id: str) -> dict:
    """Convert the job audit into conservative executable steps plus explicit manual-review items."""
    job = _require_planned_job(job_id)
    audit = _latest_evidence(job, "audit")
    if audit is None:
        raise ValueError("job has no audit evidence")
    opportunities = audit.get("opportunities") or {}
    return build_installation_steps(opportunities, tracking=audit.get("tracking"))


@mcp.tool()
def apply_recommended_tracking(
    job_id: str,
    measurement_id: str | None = None,
) -> dict:
    """Apply only conservative typed recommendations to the job-owned GTM workspace."""
    account_id, container_id, workspace_id = _job_workspace(job_id)
    resolved_measurement_id = _measurement_id_for_job(job_id, measurement_id)
    plan = recommend_job_installation(job_id)
    if any(
        item.get("reason") == "existing_ga4_page_installation_may_duplicate_base_tag"
        for item in plan["manual_review"]
    ):
        raise ValueError("possible duplicate GA4 bootstrap requires review before GTM writes")
    results: list[dict] = []

    for step in plan["steps"]:
        kind = step["kind"]
        if kind == "google_tag":
            result = _gtm_installer().install_google_tag(
                account_id,
                container_id,
                workspace_id,
                tag_id=resolved_measurement_id,
            )
        elif kind == "standard_click":
            result = _gtm_installer().install_standard_click_event(
                account_id,
                container_id,
                workspace_id,
                event_name=step["event_name"],
                measurement_id=resolved_measurement_id,
            )
        elif kind == "native_form":
            result = _gtm_installer().install_native_form_event(
                account_id,
                container_id,
                workspace_id,
                measurement_id=resolved_measurement_id,
                event_name=step["event_name"],
                form_id=step.get("form_id"),
                page_path=step.get("page_path"),
            )
        elif kind == "provider_form":
            result = _gtm_installer().install_provider_form_event(
                account_id,
                container_id,
                workspace_id,
                provider=step["provider"],
                measurement_id=resolved_measurement_id,
                event_name=step["event_name"],
            )
        else:
            raise ValueError(f"unsupported auto-install step kind: {kind}")
        results.append(
            {
                "step": step,
                "created": result.get("created", {}),
            }
        )

    job = _jobs().get(job_id)
    job.evidence.append(
        {
            "kind": "auto_install_plan",
            "measurement_id": resolved_measurement_id,
            "steps": plan["steps"],
            "manual_review": plan["manual_review"],
            "results": results,
        }
    )
    _jobs().save(job)
    return {
        "job": JobStore.serialize(job),
        "measurement_id": resolved_measurement_id,
        "results": results,
        "manual_review": plan["manual_review"],
    }


@mcp.tool()
def resolve_manual_measurement_review(
    job_id: str,
    resolution: str,
    confirm: bool = False,
) -> dict:
    """Record an explicit resolution for install requirements that could not be safely automated."""
    if confirm is not True:
        raise PermissionError("manual measurement review resolution requires confirm=true")
    job = _require_planned_job(job_id)
    if not _manual_review_pending(job):
        return {"job": JobStore.serialize(job), "resolved": False, "reason": "no pending manual review"}
    if not resolution.strip():
        raise ValueError("resolution is required")
    job.evidence.append(
        {
            "kind": "manual_review_resolution",
            "resolution": resolution.strip(),
        }
    )
    _jobs().save(job)
    return {"job": JobStore.serialize(job), "resolved": True}


@mcp.tool()
def gtm_install_google_tag(
    job_id: str,
    tag_id: str | None = None,
) -> dict:
    """Idempotently install the base Google tag into the job-owned workspace."""
    account_id, container_id, workspace_id = _job_workspace(job_id)
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
    event_name: str,
    measurement_id: str | None = None,
) -> dict:
    """Install a typed standard click event into the job-owned workspace."""
    account_id, container_id, workspace_id = _job_workspace(job_id)
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
def gtm_install_provider_form_event(
    job_id: str,
    provider: str,
    measurement_id: str | None = None,
    event_name: str = "generate_lead",
    success_signal_confirmed: bool = False,
) -> dict:
    """Install provider success callback only after its runtime semantics were verified."""
    if success_signal_confirmed is not True:
        raise PermissionError("provider conversion requires verified success callback confirmation")
    account_id, container_id, workspace_id = _job_workspace(job_id)
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
    data_layer_event: str,
    ga4_event_name: str,
    measurement_id: str | None = None,
) -> dict:
    """Map an existing dataLayer event to GA4 in the job-owned workspace."""
    account_id, container_id, workspace_id = _job_workspace(job_id)
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
def prepare_gtm_job(job_id: str) -> dict:
    """Prepare only the job-owned GTM workspace after all manual requirements are resolved."""
    job = _require_planned_job(job_id)
    if _manual_review_pending(job):
        raise ValueError("job has unresolved manual measurement requirements")
    has_install_evidence = any(
        item.get("kind") == "gtm_install"
        or (item.get("kind") == "auto_install_plan" and item.get("results"))
        for item in job.evidence
    )
    if not has_install_evidence:
        raise ValueError("job has no recorded GTM installation; refusing empty-workspace publish")
    account_id, container_id, workspace_id = _job_workspace(job_id)
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
def create_measurement_version(
    job_id: str,
    name: str,
    notes: str = "",
) -> dict:
    """Create a saved GTM version from the job-owned workspace after preview verification."""
    job = _jobs().get(job_id)
    if job.state != JobState.PREVIEW_VERIFIED:
        raise ValueError("job must be preview_verified before creating the release version")
    existing_versions = [
        item
        for item in job.evidence
        if item.get("kind") == "gtm_version" and item.get("version_id")
    ]
    if existing_versions:
        existing = existing_versions[-1]
        return {
            "job": JobStore.serialize(job),
            "gtm": None,
            "version_id": existing["version_id"],
            "reused": True,
        }
    workspace = _latest_evidence(job, "gtm_workspace")
    if workspace is None:
        raise ValueError("job has no managed GTM workspace")
    account_id = str(workspace.get("account_id") or "")
    container_id = str(workspace.get("container_id") or "")
    workspace_id = str(workspace.get("workspace_id") or "")
    if not account_id or not container_id or not workspace_id:
        raise ValueError("job GTM workspace evidence is incomplete")

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
    confirm: bool = False,
) -> dict:
    """Publish exactly the GTM version recorded by the approved measurement job."""
    if confirm is not True:
        raise PermissionError("publish requires confirm=true before claiming the job")
    _gtm_writer()._ensure_publish(confirm)
    job = _jobs().get(job_id)
    if job.state != JobState.APPROVED:
        raise ValueError("job must be approved before publish")
    version_evidence = _latest_evidence(job, "gtm_version")
    if version_evidence is None or not version_evidence.get("version_id"):
        raise ValueError("job has no saved GTM version")
    version_id = str(version_evidence["version_id"])
    account_id = str(version_evidence.get("account_id") or "")
    container_id = str(version_evidence.get("container_id") or "")
    if not account_id or not container_id:
        raise ValueError("job GTM version evidence is missing account/container identity")

    workspace = _latest_evidence(job, "gtm_workspace")
    if workspace is None:
        raise ValueError("job has no managed GTM workspace")
    if str(workspace.get("account_id") or "") != account_id:
        raise ValueError("saved version account does not match job workspace")
    if str(workspace.get("container_id") or "") != container_id:
        raise ValueError("saved version container does not match job workspace")
    if str(workspace.get("workspace_id") or "") != str(version_evidence.get("workspace_id") or ""):
        raise ValueError("saved version workspace does not match job workspace")
    claimed = _jobs().claim(
        job_id,
        expected=JobState.APPROVED,
        target=JobState.PUBLISHING,
        evidence={
            "kind": "publish_claim",
            "account_id": account_id,
            "container_id": container_id,
            "version_id": version_id,
        },
    )
    try:
        result = _gtm_writer().publish_version(
            account_id,
            container_id,
            version_id,
            confirm=confirm,
        )
    except Exception as exc:
        failed = _jobs().transition(
            job_id,
            JobState.FAILED,
            evidence={
                "kind": "publish_error",
                "error_type": type(exc).__name__,
                "message": str(exc)[:500],
                "reconciliation_required": True,
            },
        )
        raise RuntimeError(
            f"GTM publish failed after job claim; job {failed.id} requires live-version reconciliation"
        ) from exc

    published = _jobs().transition(
        claimed.id,
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
