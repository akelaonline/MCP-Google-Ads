"""Offline subprocess tests: no Ads client, credentials or network requests."""

import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from cryptography.fernet import Fernet

ROOT = Path(__file__).resolve().parents[1]
LAUNCHER = ROOT / "scripts/run_profile.py"


def profile(tmp_path):
    root = tmp_path / "profile"
    root.mkdir(mode=0o700)
    package = tmp_path / "fake/google_ads_mcp"
    package.mkdir(parents=True)
    (package / "__init__.py").write_text("")
    for name in ("config.py", "helpers.py"):
        (package / name).write_bytes((ROOT / "src/google_ads_mcp" / name).read_bytes())
    (package / "server.py").write_text(
        """import hashlib,json,os,sys\nfrom pathlib import Path\nfrom .config import load_settings\ndef main():\n assert len(sys.argv)==1\n s=load_settings()\n Path(s.audit_db_path).with_suffix(".started.json").write_text(json.dumps({"db":s.audit_db_path,"key_hash":hashlib.sha256(os.environ["GOOGLE_ADS_MCP_PENDING_ENCRYPTION_KEY"].encode()).hexdigest(),"readonly":s.read_only,"auto":s.auto_approve or s.auto_approve_spend or s.auto_approve_destructive or s.auto_approve_sensitive,"scope":sorted(s.allowed_manager_ids)}))\n sys.stdin.readline()\n"""
    )
    values = {
        "GOOGLE_ADS_CLIENT_ID": "fake-client",
        "GOOGLE_ADS_CLIENT_SECRET": "fake-secret",
        "GOOGLE_ADS_REFRESH_TOKEN": "fake-refresh",
        "GOOGLE_ADS_MCP_READ_ONLY": "false",
        "GOOGLE_ADS_MCP_AUTO_APPROVE": "false",
        "GOOGLE_ADS_MCP_AUTO_APPROVE_SPEND": "false",
        "GOOGLE_ADS_MCP_AUTO_APPROVE_DESTRUCTIVE": "false",
        "GOOGLE_ADS_MCP_AUTO_APPROVE_SENSITIVE": "false",
        "GOOGLE_ADS_MCP_REQUIRE_CUSTOMER_ALLOWLIST": "true",
        "GOOGLE_ADS_MCP_ALLOWED_MANAGER_IDS": "1234567890",
        "GOOGLE_ADS_MCP_AUDIT_DB": str(root / "audit.db"),
        "GOOGLE_ADS_MCP_PENDING_ENCRYPTION_KEY": Fernet.generate_key().decode(),
        "GOOGLE_ADS_MCP_TRANSPORT": "stdio",
        "GOOGLE_ADS_MCP_ALLOW_INSECURE_HTTP": "false",
    }
    env_file = root / "ads.env"

    def save():
        env_file.write_text(
            "\n".join(k + "=" + json.dumps(v) for k, v in values.items()) + "\n"
        )
        env_file.chmod(0o600)

    save()
    env = dict(
        os.environ, PYTHONPATH=str(package.parent), GOOGLE_ADS_MCP_AUTO_APPROVE="true"
    )
    command = [
        sys.executable,
        str(LAUNCHER),
        "--env",
        str(env_file),
        "--mode",
        "editor",
    ]
    return root, values, save, env, command


def test_concurrent_client_processes_have_distinct_pending_storage(tmp_path):
    root, values, _save, env, command = profile(tmp_path)
    processes = []
    try:
        for count in range(1, 4):
            process = subprocess.Popen(
                command,
                env=env,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            processes.append(process)
            deadline = time.monotonic() + 5
            while (
                len(list(root.rglob("*.started.json"))) < count
                and time.monotonic() < deadline
            ):
                assert process.poll() is None, process.stderr.read()
                time.sleep(0.02)
            assert len(list(root.rglob("*.started.json"))) == count
        records = [
            json.loads(path.read_text()) for path in root.rglob("*.started.json")
        ]
        assert len({r["db"] for r in records}) == 3
        assert len({r["key_hash"] for r in records}) == 3
        assert all(
            not r["auto"] and not r["readonly"] and r["scope"] == ["1234567890"]
            for r in records
        )
        assert hashlib.sha256(
            values["GOOGLE_ADS_MCP_PENDING_ENCRYPTION_KEY"].encode()
        ).hexdigest() in {r["key_hash"] for r in records}
        keys = list((root / "instances").rglob("pending.key"))
        assert len(keys) == 2
        assert all(key.stat().st_mode & 0o077 == 0 for key in keys)
    finally:
        for process in processes:
            _, error = process.communicate("\n", timeout=5)
            assert process.returncode == 0, error


def test_mode_autoapproval_and_database_mismatch_are_local_failures(tmp_path):
    root, values, save, env, command = profile(tmp_path)
    valid = subprocess.run(
        command + ["--check"], env=env, capture_output=True, text=True
    )
    assert valid.returncode == 0, valid.stderr
    for name, bad in [
        ("GOOGLE_ADS_MCP_READ_ONLY", "true"),
        ("GOOGLE_ADS_MCP_AUTO_APPROVE_SPEND", "true"),
        ("GOOGLE_ADS_MCP_AUDIT_DB", str(tmp_path / "other.db")),
    ]:
        previous = values[name]
        values[name] = bad
        save()
        result = subprocess.run(
            command + ["--check"], env=env, capture_output=True, text=True
        )
        assert result.returncode != 0
        assert not list(root.rglob("*.started.json"))
        assert not list(root.rglob("*.db"))
        values[name] = previous


def test_private_file_required(tmp_path):
    root, _values, _save, env, command = profile(tmp_path)
    (root / "ads.env").chmod(0o644)
    result = subprocess.run(
        command + ["--check"], env=env, capture_output=True, text=True
    )
    assert result.returncode != 0
    assert "0600" in result.stderr
