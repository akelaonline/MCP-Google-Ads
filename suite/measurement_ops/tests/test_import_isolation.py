import os
import subprocess
import sys
from pathlib import Path

from mkt_measurement_ops.registry import LazySiteRegistry


def test_pytest_collection_uses_disposable_database() -> None:
    database = Path(os.environ["MEASUREMENT_OPS_DB"])
    assert database.parent.name.startswith("mkt-measurement-ops-pytest-")
    assert database.name == "test.db"


def test_lazy_registry_defers_first_database_write(tmp_path, monkeypatch) -> None:
    database = tmp_path / "registry.db"
    monkeypatch.setenv("MEASUREMENT_OPS_DB", str(database))

    registry = LazySiteRegistry()
    assert not database.exists()

    assert registry.list() == []
    assert database.exists()


def test_importing_server_cannot_create_a_default_home_database(tmp_path) -> None:
    clean_home = tmp_path / "isolated-home"
    clean_home.mkdir()
    env = dict(os.environ)
    env["HOME"] = str(clean_home)
    env.pop("MEASUREMENT_OPS_DB", None)

    result = subprocess.run(
        [sys.executable, "-c", "from mkt_measurement_ops.server import mcp; print(type(mcp).__name__)"],
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )
    assert "FastMCP" in result.stdout
    assert not (clean_home / ".mkt-measurement-ops").exists()
