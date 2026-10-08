from pathlib import Path


SERVER = Path(__file__).resolve().parents[1] / "src" / "mkt_measurement_ops" / "server.py"


def test_no_public_low_level_gtm_publish_tool() -> None:
    source = SERVER.read_text(encoding="utf-8")
    assert "def gtm_publish_version(" not in source
    assert "def publish_measurement_job(" in source


def test_no_public_raw_gtm_entity_create_tools() -> None:
    source = SERVER.read_text(encoding="utf-8")
    assert "def gtm_create_tag(" not in source
    assert "def gtm_create_trigger(" not in source
    assert "def gtm_create_variable(" not in source
    assert "def gtm_install_standard_click_event(" in source
    assert "def gtm_install_provider_form_event(" in source


def test_version_creation_is_managed_by_job() -> None:
    source = SERVER.read_text(encoding="utf-8")
    assert "def gtm_create_version(" not in source
    assert "def create_measurement_version(" in source
    assert "job must be preview_verified before creating the release version" in source



def test_no_public_native_submit_as_lead_tool() -> None:
    source = SERVER.read_text(encoding="utf-8")
    assert "def gtm_install_native_form_event(" not in source
    assert "success_signal_confirmed: bool = False" in source


def test_publish_permission_is_checked_before_atomic_claim() -> None:
    source = SERVER.read_text(encoding="utf-8")
    method = source.split("def publish_measurement_job(", 1)[1].split("\ndef main(", 1)[0]
    assert method.index("_ensure_publish(confirm)") < method.index("_jobs().claim(")
    assert "saved version workspace does not match job workspace" in method


def test_production_completion_requires_browser_attestation() -> None:
    source = SERVER.read_text(encoding="utf-8")
    assert "def record_production_browser_attestation(" in source
    verification = source.split("def ga4_verify_events(", 1)[1].split("\n@mcp.tool()", 1)[0]
    assert "production_browser_attestation" in verification
    assert "browser-side production QA is required" in verification


def test_wordpress_plan_does_not_preconfirm_mutation() -> None:
    source = SERVER.read_text(encoding="utf-8")
    wordpress = source.split("def wordpress_measurement_plan(", 1)[1].split("\n@mcp.tool()", 1)[0]
    assert '"confirm": False' in wordpress
