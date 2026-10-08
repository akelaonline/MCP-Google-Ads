"""Isolate even test-module imports from the real Measurement Ops database."""

import os
import tempfile
from pathlib import Path

import pytest

_test_db_dir: tempfile.TemporaryDirectory[str] | None = None
_previous_db: str | None = None


def pytest_configure(config: pytest.Config) -> None:
    """Run before collection: imports of server.py must see a disposable DB."""
    global _test_db_dir, _previous_db
    _previous_db = os.environ.get("MEASUREMENT_OPS_DB")
    _test_db_dir = tempfile.TemporaryDirectory(prefix="mkt-measurement-ops-pytest-")
    os.environ["MEASUREMENT_OPS_DB"] = str(Path(_test_db_dir.name) / "test.db")


def pytest_unconfigure(config: pytest.Config) -> None:
    """Restore the caller environment and discard all pytest database files."""
    global _test_db_dir, _previous_db
    if _previous_db is None:
        os.environ.pop("MEASUREMENT_OPS_DB", None)
    else:
        os.environ["MEASUREMENT_OPS_DB"] = _previous_db
    if _test_db_dir is not None:
        _test_db_dir.cleanup()
    _test_db_dir = None
    _previous_db = None
