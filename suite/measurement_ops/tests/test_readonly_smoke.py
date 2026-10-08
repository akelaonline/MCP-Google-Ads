import runpy
import subprocess
import sys
from pathlib import Path


SCRIPTS = Path(__file__).resolve().parents[1] / "scripts"


def test_readonly_smoke_invokes_only_list_methods() -> None:
    namespace = runpy.run_path(str(SCRIPTS / "smoke_readonly.py"))
    check = namespace["check_readonly_connections"]

    class FakeGTM:
        def list_accounts(self):
            return [{"accountId": "test"}]

    class FakeGA4:
        def list_property_summaries(self):
            return [{"property": "properties/1"}, {"property": "properties/2"}]

    result = check(FakeGTM(), FakeGA4())
    assert result == {
        "gtm_accounts_count": 1,
        "ga4_properties_count": 2,
        "api_readonly_verified": True,
        "production_tracking_verified": False,
    }


def test_readonly_smoke_requires_explicit_flag() -> None:
    result = subprocess.run(
        [sys.executable, str(SCRIPTS / "smoke_readonly.py")],
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 2
    assert "--confirm-readonly" in result.stderr
    assert "READONLY GOOGLE API DISCOVERY PASS" not in result.stdout
