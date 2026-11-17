"""scripts/lab_preflight.py: positive and negative cases (no network, no secrets)."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import lab_preflight

GOOD = {
    "GOOGLE_ADS_MCP_READ_ONLY": "true",
    "GOOGLE_ADS_MCP_AUTO_APPROVE": "false",
    "GOOGLE_ADS_MCP_ALLOWED_CUSTOMER_IDS": "123-456-7890",
    "GOOGLE_ADS_MCP_REQUIRE_CUSTOMER_ALLOWLIST": "true",
}
SECRET = "super-secret-value-123"


@pytest.fixture(autouse=True)
def checkout(tmp_path, monkeypatch):
    """A pristine fake checkout: these tests must never inspect the real one."""
    root = tmp_path / "checkout"
    root.mkdir()
    monkeypatch.setattr(sys.modules[__name__], "CHECKOUT", root)
    return root


CHECKOUT: Path = ROOT  # replaced per test by the autouse fixture


def _clean_env() -> dict[str, str]:
    return {k: v for k, v in os.environ.items() if not k.startswith("GOOGLE_")}


def _write(path: Path, values: dict[str, str], mode: int = 0o600) -> Path:
    path.write_text("\n".join(f"{k}={v}" for k, v in values.items()) + "\n")
    path.chmod(mode)
    return path


def _lab(tmp_path: Path, **overrides):
    lab = tmp_path / "lab"
    lab.mkdir(mode=0o700)
    lab.chmod(0o700)
    values = {**GOOD, "GOOGLE_ADS_MCP_AUDIT_DB": str(lab / "audit.db")}
    values.update(overrides)
    values = {k: v for k, v in values.items() if v is not None}
    env_file = _write(lab / "lab.env", values)
    return lab, env_file


def _run(lab, env_file, environ=None):
    return lab_preflight.run(lab, env_file, environ or {}, repo=CHECKOUT)


def _failed(report):
    return [label for ok, label in report.rows if not ok]


def test_positive_good_lab_passes(tmp_path):
    lab, env_file = _lab(tmp_path)
    report = _run(lab, env_file)
    assert report.ok, _failed(report)


def test_positive_dotenv_syntax_is_parsed_like_the_runtime(tmp_path):
    lab, env_file = _lab(tmp_path)
    env_file.write_text(
        "# comment\n"
        'export GOOGLE_ADS_MCP_READ_ONLY="TRUE"  # inline comment\n'
        "GOOGLE_ADS_MCP_AUTO_APPROVE='off'\n"
        'GOOGLE_ADS_MCP_ALLOWED_CUSTOMER_IDS="123-456-7890, 098-765-4321"\n'
        "GOOGLE_ADS_MCP_REQUIRE_CUSTOMER_ALLOWLIST=  On \n"
        f"GOOGLE_ADS_MCP_AUDIT_DB={lab / 'audit.db'}\n"
    )
    env_file.chmod(0o600)
    report = _run(lab, env_file)
    assert report.ok, _failed(report)


def test_positive_merchant_scope_valid(tmp_path):
    lab, env_file = _lab(
        tmp_path,
        GOOGLE_ADS_MCP_ALLOWED_MERCHANT_IDS="111,222",
        GOOGLE_ADS_MCP_REQUIRE_MERCHANT_ALLOWLIST="true",
    )
    assert _run(lab, env_file).ok


@pytest.mark.parametrize("value", ["1", "yes", "on", "TRUE", " On ", "Yes"])
def test_negative_every_runtime_truthy_auto_approve_value_fails(tmp_path, value):
    for name in (
        "GOOGLE_ADS_MCP_AUTO_APPROVE",
        "GOOGLE_ADS_MCP_AUTO_APPROVE_SPEND",
        "GOOGLE_ADS_MCP_AUTO_APPROVE_DESTRUCTIVE",
        "GOOGLE_ADS_MCP_AUTO_APPROVE_SENSITIVE",
    ):
        sub = tmp_path / name
        sub.mkdir()
        lab, env_file = _lab(sub, **{name: value})
        report = _run(lab, env_file)
        assert not report.ok
        assert any(name in label for label in _failed(report)), name


@pytest.mark.parametrize("value", [None, "false", "0", "no", "", "maybe"])
def test_negative_read_only_must_be_truthy(tmp_path, value):
    lab, env_file = _lab(tmp_path, GOOGLE_ADS_MCP_READ_ONLY=value)
    assert not _run(lab, env_file).ok


@pytest.mark.parametrize("value", [None, "false", "0", ""])
def test_negative_customer_allowlist_must_be_required(tmp_path, value):
    lab, env_file = _lab(tmp_path, GOOGLE_ADS_MCP_REQUIRE_CUSTOMER_ALLOWLIST=value)
    assert any("REQUIRE_CUSTOMER_ALLOWLIST" in x for x in _failed(_run(lab, env_file)))


@pytest.mark.parametrize(
    "ids", [None, "", "abc", "123", "123-456-789", "1234567890,12x", "12345678901"]
)
def test_negative_customer_ids_must_exist_and_be_valid(tmp_path, ids):
    lab, env_file = _lab(tmp_path, GOOGLE_ADS_MCP_ALLOWED_CUSTOMER_IDS=ids)
    assert not _run(lab, env_file).ok


@pytest.mark.parametrize("ids", ["abc", "0", "-5", "12-3"])
def test_negative_merchant_ids_must_be_valid(tmp_path, ids):
    lab, env_file = _lab(tmp_path, GOOGLE_ADS_MCP_ALLOWED_MERCHANT_IDS=ids)
    assert not _run(lab, env_file).ok


def test_negative_merchant_required_but_empty(tmp_path):
    lab, env_file = _lab(tmp_path, GOOGLE_ADS_MCP_REQUIRE_MERCHANT_ALLOWLIST="true")
    assert not _run(lab, env_file).ok


def test_negative_db_outside_lab_even_if_path_contains_the_lab_name(tmp_path):
    """The previous substring check accepted this."""
    lab, env_file = _lab(tmp_path)
    sneaky = tmp_path / "elsewhere" / lab.name / "audit.db"
    sneaky.parent.mkdir(parents=True)
    _write(env_file, {**GOOD, "GOOGLE_ADS_MCP_AUDIT_DB": str(sneaky)})
    report = _run(lab, env_file)
    assert any("audit DB" in x and "inside the lab" in x for x in _failed(report))


def test_negative_db_dotdot_escape(tmp_path):
    lab, env_file = _lab(tmp_path)
    _write(env_file, {**GOOD, "GOOGLE_ADS_MCP_AUDIT_DB": str(lab / ".." / "audit.db")})
    assert not _run(lab, env_file).ok


def test_negative_relative_db_path(tmp_path):
    lab, env_file = _lab(tmp_path)
    _write(env_file, {**GOOD, "GOOGLE_ADS_MCP_AUDIT_DB": "audit.db"})
    assert any("absolute" in x for x in _failed(_run(lab, env_file)))


def test_negative_db_missing(tmp_path):
    lab, env_file = _lab(tmp_path, GOOGLE_ADS_MCP_AUDIT_DB=None)
    assert not _run(lab, env_file).ok


def test_negative_db_symlink_to_outside(tmp_path):
    lab, env_file = _lab(tmp_path)
    outside = tmp_path / "outside.db"
    outside.write_bytes(b"x")
    outside.chmod(0o600)
    (lab / "audit.db").symlink_to(outside)
    report = _run(lab, env_file)
    assert not report.ok
    assert any("symlink" in x or "inside the lab" in x for x in _failed(report))


def test_negative_key_symlink_to_outside(tmp_path):
    lab, env_file = _lab(tmp_path)
    outside = tmp_path / "outside.key"
    outside.write_bytes(b"k")
    (lab / "audit.db.pending.key").symlink_to(outside)
    assert any("pending key" in x for x in _failed(_run(lab, env_file)))


def test_negative_db_directory_is_a_symlink_out_of_the_lab(tmp_path):
    lab, env_file = _lab(tmp_path)
    real = tmp_path / "real_dir"
    real.mkdir()
    (lab / "sub").symlink_to(real, target_is_directory=True)
    _write(env_file, {**GOOD, "GOOGLE_ADS_MCP_AUDIT_DB": str(lab / "sub" / "audit.db")})
    assert not _run(lab, env_file).ok


def test_negative_lab_directory_itself_is_a_symlink(tmp_path):
    lab, _ = _lab(tmp_path)
    link = tmp_path / "linked_lab"
    link.symlink_to(lab, target_is_directory=True)
    report = _run(link, link / "lab.env")
    assert any("lab directory" in x and "symlink" in x for x in _failed(report))


def test_negative_env_file_is_a_symlink(tmp_path):
    lab, env_file = _lab(tmp_path)
    real = tmp_path / "real.env"
    real.write_text(env_file.read_text())
    real.chmod(0o600)
    env_file.unlink()
    env_file.symlink_to(real)
    assert not _run(lab, env_file).ok


def test_negative_env_file_outside_lab(tmp_path):
    lab, env_file = _lab(tmp_path)
    outside = tmp_path / "other.env"
    outside.write_text(env_file.read_text())
    outside.chmod(0o600)
    assert any(
        "env file" in x and "inside the lab" in x for x in _failed(_run(lab, outside))
    )


@pytest.mark.parametrize("mode", [0o644, 0o640, 0o604, 0o666])
def test_negative_env_file_must_be_private(tmp_path, mode):
    lab, env_file = _lab(tmp_path)
    env_file.chmod(mode)
    assert any("env file" in x and "private" in x for x in _failed(_run(lab, env_file)))


def test_negative_lab_directory_must_be_private(tmp_path):
    lab, env_file = _lab(tmp_path)
    lab.chmod(0o755)
    assert any(
        "lab directory" in x and "private" in x for x in _failed(_run(lab, env_file))
    )


def test_negative_missing_env_file_named_dot_env_is_not_picked_up(tmp_path):
    """Mission 008 uses lab.env: a lone .env must not satisfy the check."""
    lab, env_file = _lab(tmp_path)
    (lab / ".env").write_text(env_file.read_text())
    env_file.unlink()
    assert not _run(lab, lab / "lab.env").ok


def test_negative_shell_environment_overrides_the_file(tmp_path):
    lab, env_file = _lab(tmp_path)
    report = _run(lab, env_file, {"GOOGLE_ADS_MCP_AUTO_APPROVE": "true"})
    assert any("override" in x for x in _failed(report))


def test_positive_shell_environment_matching_the_file_is_fine(tmp_path):
    lab, env_file = _lab(tmp_path)
    assert _run(lab, env_file, {"GOOGLE_ADS_MCP_READ_ONLY": "true"}).ok


def test_negative_lab_inside_production_directory(tmp_path, monkeypatch):
    home = tmp_path / "home"
    (home / ".google_ads_mcp" / "lab").mkdir(parents=True)
    monkeypatch.setenv("HOME", str(home))
    lab = home / ".google_ads_mcp" / "lab"
    lab.chmod(0o700)
    env_file = _write(
        lab / "lab.env", {**GOOD, "GOOGLE_ADS_MCP_AUDIT_DB": str(lab / "a.db")}
    )
    assert any(
        "separate from the production" in x for x in _failed(_run(lab, env_file))
    )


def test_cli_exit_codes_and_no_secret_is_ever_printed(tmp_path):
    lab, env_file = _lab(
        tmp_path, GOOGLE_ADS_REFRESH_TOKEN=SECRET, GOOGLE_ADS_CLIENT_SECRET=SECRET
    )
    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "lab_preflight.py"),
        "--lab-dir",
        str(lab),
        "--repo-root",
        str(CHECKOUT),
    ]
    ok = subprocess.run(
        cmd, capture_output=True, text=True, check=False, env=_clean_env()
    )
    assert ok.returncode == 0, ok.stdout
    assert "PREFLIGHT PASSED" in ok.stdout
    assert SECRET not in ok.stdout + ok.stderr

    _write(
        env_file,
        {
            **GOOD,
            "GOOGLE_ADS_MCP_AUTO_APPROVE": "yes",
            "GOOGLE_ADS_MCP_AUDIT_DB": SECRET,
        },
    )
    bad = subprocess.run(
        cmd, capture_output=True, text=True, check=False, env=_clean_env()
    )
    assert bad.returncode == 1
    assert "PREFLIGHT FAILED" in bad.stdout
    assert SECRET not in bad.stdout + bad.stderr


def test_cli_explicit_env_file_option(tmp_path):
    lab, env_file = _lab(tmp_path)
    renamed = lab / "mission.env"
    env_file.rename(renamed)
    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "lab_preflight.py"),
        "--lab-dir",
        str(lab),
        "--repo-root",
        str(CHECKOUT),
    ]
    assert (
        subprocess.run(
            cmd, capture_output=True, text=True, check=False, env=_clean_env()
        ).returncode
        == 1
    )
    done = subprocess.run(
        [*cmd, "--env-file", str(renamed)],
        capture_output=True,
        text=True,
        check=False,
        env=_clean_env(),
    )
    assert done.returncode == 0, done.stdout


def test_security_control_kept_stray_dotenv_in_checkout_fails(checkout, tmp_path):
    lab, env_file = _lab(tmp_path)
    assert _run(lab, env_file).ok
    (checkout / ".env").write_text("GOOGLE_ADS_REFRESH_TOKEN=x\n")
    failed = _failed(_run(lab, env_file))
    assert any("repository has no .env" in label for label in failed)


def test_cli_repo_root_controls_the_stray_dotenv_check(checkout, tmp_path):
    lab, _ = _lab(tmp_path)
    (checkout / ".env").write_text("X=1\n")
    cmd = [
        sys.executable,
        str(ROOT / "scripts" / "lab_preflight.py"),
        "--lab-dir",
        str(lab),
        "--repo-root",
        str(checkout),
    ]
    done = subprocess.run(
        cmd, capture_output=True, text=True, check=False, env=_clean_env()
    )
    assert done.returncode == 1 and "repository has no .env" in done.stdout


def test_real_checkout_dotenv_does_not_influence_these_tests():
    """A stray .env at the real checkout root (the Owner's) must not matter here."""
    assert CHECKOUT != ROOT and not (CHECKOUT / ".env").exists()
