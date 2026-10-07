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
