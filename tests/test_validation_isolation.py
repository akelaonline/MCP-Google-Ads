"""The validation battery must never touch the operator's config, DB or key.

Reproduces the review finding: tests/test_tool_registry_sweep.py (which builds the
real server) used to create the DB named by ``GOOGLE_ADS_MCP_AUDIT_DB`` in the
operator's shell. Decoy config/DB/HOME are supplied from outside and must stay
byte-for-byte intact.
"""

from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import validate_local
import validation_isolation

SECRETS = {
    "GOOGLE_ADS_REFRESH_TOKEN": "decoy-refresh-token",
    "GOOGLE_ADS_CLIENT_SECRET": "decoy-client-secret",
    "GOOGLE_ADS_DEVELOPER_TOKEN": "decoy-dev-token",
    "GOOGLE_MERCHANT_CENTER_REFRESH_TOKEN": "decoy-merchant-token",
    "GOOGLE_APPLICATION_CREDENTIALS": "/decoy/adc.json",
    "GOOGLE_ADS_MCP_ALLOWED_CUSTOMER_IDS": "1111111111",
    "GOOGLE_ADS_MCP_AUTO_APPROVE": "true",
}


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _tree(path: Path) -> list[str]:
    return (
        sorted(str(p.relative_to(path)) for p in path.rglob("*"))
        if path.exists()
        else []
    )


@pytest.fixture
def decoys(tmp_path):
    home = tmp_path / "real_home"
    (home / ".google_ads_mcp").mkdir(parents=True)
    existing_db = tmp_path / "existing_audit.db"
    existing_db.write_bytes(b"DECOY-DB-CONTENT")
    missing_db = tmp_path / "must_not_be_created" / "audit.db"
    env_file = tmp_path / "operator.env"
    env_file.write_text(
        "GOOGLE_ADS_REFRESH_TOKEN=from-operator-dotenv\n"
        f"GOOGLE_ADS_MCP_AUDIT_DB={missing_db}\n"
    )
    cwd_env = tmp_path / "cwd"
    cwd_env.mkdir()
    (cwd_env / ".env").write_text("GOOGLE_ADS_CLIENT_SECRET=from-cwd-dotenv\n")
    base = {
        **os.environ,
        **SECRETS,
        "HOME": str(home),
        "GOOGLE_ADS_MCP_ENV_FILE": str(env_file),
        "GOOGLE_ADS_MCP_AUDIT_DB": str(missing_db),
    }
    return {
        "base": base,
        "home": home,
        "existing_db": existing_db,
        "missing_db": missing_db,
        "env_file": env_file,
        "cwd": cwd_env,
    }


def _assert_untouched(d, before):
    assert not d["missing_db"].exists()
    assert not d["missing_db"].parent.exists()
    assert not Path(str(d["missing_db"]) + ".pending.key").exists()
    assert _digest(d["existing_db"]) == before["db"]
    assert _digest(d["env_file"]) == before["env"]
    assert _tree(d["home"]) == before["home"]
    assert not (d["home"] / ".google_ads_mcp" / "audit.db").exists()


def _snapshot(d):
    return {
        "db": _digest(d["existing_db"]),
        "env": _digest(d["env_file"]),
        "home": _tree(d["home"]),
    }


def test_isolated_environment_scrubs_everything_and_redirects_state(tmp_path, decoys):
    env = validation_isolation.isolated_environment(decoys["base"], tmp_path / "w")
    for name in SECRETS:
        if name not in {"GOOGLE_ADS_MCP_ENV_FILE", "GOOGLE_ADS_MCP_AUDIT_DB"}:
            assert name not in env, name
    joined = "\n".join(env.values())
    for secret in ("decoy-", "from-operator", "from-cwd", str(decoys["home"])):
        assert secret not in joined, secret
    work = (tmp_path / "w").resolve()
    for key in ("HOME", "GOOGLE_ADS_MCP_ENV_FILE", "GOOGLE_ADS_MCP_AUDIT_DB"):
        assert Path(env[key]).resolve().is_relative_to(work), key
    assert Path(env["GOOGLE_ADS_MCP_ENV_FILE"]).read_text() == ""
    assert env["PATH"] == decoys["base"]["PATH"]


def test_conftest_isolated_this_very_process():
    """The battery already runs hermetically: no leaked secrets, temp state."""
    for name in SECRETS:
        if name in {"GOOGLE_ADS_MCP_ENV_FILE", "GOOGLE_ADS_MCP_AUDIT_DB"}:
            continue
        assert name not in os.environ
    tmp_root = Path(os.environ["GOOGLE_ADS_MCP_AUDIT_DB"]).resolve()
    assert "gads-mcp-validation-" in str(tmp_root)
    assert "gads-mcp-validation-" in str(Path.home())
    from google_ads_mcp.config import load_settings

    settings = load_settings()
    assert "gads-mcp-validation-" in settings.audit_db_path
    assert settings.refresh_token == ""
    assert settings.auto_approve is False


def test_pytest_subprocess_with_decoys_leaves_them_intact(decoys):
    """Exactly the reported scenario: run the real-server test with decoy config."""
    before = _snapshot(decoys)
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-q",
            "-p",
            "no:cacheprovider",
            str(ROOT / "tests" / "test_tool_registry_sweep.py"),
        ],
        cwd=decoys["cwd"],
        env=decoys["base"],
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout[-800:] + completed.stderr[-400:]
    _assert_untouched(decoys, before)


def test_validate_local_runs_every_step_with_the_isolated_env(decoys, monkeypatch):
    seen = []

    def fake_run(command, **kwargs):
        seen.append(kwargs)
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(validate_local.subprocess, "run", fake_run)
    for key, value in decoys["base"].items():
        monkeypatch.setenv(key, value)
    monkeypatch.setattr(validate_local, "_WORKDIR", None)
    validate_local._run("step", ["echo"])
    (kwargs,) = seen
    env = kwargs["env"]
    assert env["GOOGLE_ADS_MCP_AUDIT_DB"] != str(decoys["missing_db"])
    assert "GOOGLE_ADS_REFRESH_TOKEN" not in env
    assert "from-operator" not in "".join(env.values())
    assert Path(env["HOME"]) != decoys["home"]


def test_stdio_lifecycle_with_decoys_leaves_them_intact(decoys):
    before = _snapshot(decoys)
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "stdio_lifecycle_test.py")],
        cwd=decoys["cwd"],
        env=decoys["base"],
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    assert completed.returncode == 0, completed.stdout[-600:] + completed.stderr[-400:]
    _assert_untouched(decoys, before)


def test_smoke_with_decoys_leaves_them_intact(decoys):
    before = _snapshot(decoys)
    completed = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "smoke_test.py")],
        cwd=decoys["cwd"],
        env=decoys["base"],
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    assert completed.returncode == 0, completed.stdout[-600:] + completed.stderr[-400:]
    _assert_untouched(decoys, before)


def test_validate_local_main_keeps_PATH_and_non_google_variables(tmp_path):
    """Regression: main() once cleared os.environ before building the new one."""
    code = (
        "import os, sys; sys.path.insert(0, 'scripts'); import validate_local;"
        "iso = validate_local._isolated_env();"
        "assert 'PATH' in iso and iso['PATH'] == os.environ['PATH'];"
        "assert 'GOOGLE_ADS_REFRESH_TOKEN' not in iso; print('ok')"
    )
    env = {**os.environ, "GOOGLE_ADS_REFRESH_TOKEN": "decoy"}
    done = subprocess.run(
        [sys.executable, "-c", code],
        cwd=ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert done.returncode == 0 and "ok" in done.stdout, done.stderr[-400:]


_NESTED = "GADS_NESTED_VALIDATION"


@pytest.mark.skipif(os.environ.get(_NESTED) == "1", reason="nested validator run")
def test_full_validator_with_decoy_dotenv_in_checkout_root(decoys, tmp_path):
    """Whole battery in a copy of the checkout whose ROOT holds a decoy ``.env``.

    The Owner's real ``.env`` is never touched or moved: the decoy lives in a
    throw-away copy. Config, DB and key stay intact and the battery is green.
    """
    import shutil

    copy = tmp_path / "checkout_copy"
    shutil.copytree(
        ROOT,
        copy,
        ignore=shutil.ignore_patterns(
            ".git",
            ".venv",
            "venv",
            "__pycache__",
            ".pytest_cache",
            ".ruff_cache",
            "*.egg-info",
            ".env",
        ),
    )
    root_env = copy / ".env"
    root_env.write_text(
        "GOOGLE_ADS_REFRESH_TOKEN=root-dotenv-decoy\n"
        f"GOOGLE_ADS_MCP_AUDIT_DB={decoys['missing_db']}\n"
    )
    key = Path(str(decoys["missing_db"]) + ".pending.key")
    env_digest = _digest(root_env)
    before = _snapshot(decoys)

    env = {
        **decoys["base"],
        _NESTED: "1",
        "PYTHONPATH": str(copy / "src"),
    }
    completed = subprocess.run(
        [sys.executable, str(copy / "scripts" / "validate_local.py")],
        cwd=copy,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=600,
    )
    tail = completed.stdout[-1500:] + completed.stderr[-500:]
    assert completed.returncode == 0, tail
    assert "LOCAL VALIDATION GREEN" in completed.stdout, tail
    assert " failed" not in completed.stdout, tail
    _assert_untouched(decoys, before)
    assert not key.exists()
    assert root_env.exists() and _digest(root_env) == env_digest
