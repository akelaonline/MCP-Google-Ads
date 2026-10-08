from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from importlib.metadata import version
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_RUFF = "0.8.6"
WORDPRESS_PLUGIN = ROOT / "wordpress" / "mkt-measurement-bridge" / "mkt-measurement-bridge.php"


def run(*args: str, env: dict[str, str] | None = None) -> None:
    print("+", " ".join(args), flush=True)
    subprocess.run(args, cwd=ROOT, check=True, env=env)


def main() -> int:
    print(f"Python: {sys.version.split()[0]}", flush=True)
    actual_ruff = version("ruff")
    print(f"Ruff: {actual_ruff} (expected {EXPECTED_RUFF})", flush=True)
    if actual_ruff != EXPECTED_RUFF:
        raise RuntimeError(
            f"unexpected Ruff {actual_ruff}; install project dev dependencies "
            f"to use the pinned Ruff {EXPECTED_RUFF}"
        )
    run(sys.executable, "-m", "compileall", "-q", "src", "tests", "scripts")
    run(sys.executable, "-m", "ruff", "check", "src", "tests", "scripts")
    run(sys.executable, "-m", "pytest", "-q")

    with tempfile.TemporaryDirectory(prefix="measurement-ops-validate-") as tmp:
        env = dict(os.environ)
        env["MEASUREMENT_OPS_DB"] = str(Path(tmp) / "measurement_ops.db")
        run(
            sys.executable,
            "-c",
            (
                "import pkgutil, mkt_measurement_ops; "
                "[__import__(m.name) for m in pkgutil.walk_packages("
                "mkt_measurement_ops.__path__, mkt_measurement_ops.__name__ + '.')]; "
                "from mkt_measurement_ops.server import mcp; "
                "print('ALL MODULE IMPORTS OK', mkt_measurement_ops.__version__, type(mcp).__name__)"
            ),
            env=env,
        )

    if WORDPRESS_PLUGIN.exists():
        php = shutil.which("php")
        if not php:
            raise RuntimeError(
                "PHP lint required but PHP is not installed; "
                "cannot declare the WordPress-inclusive validation GREEN"
            )
        run(php, "-l", str(WORDPRESS_PLUGIN))

    print("MEASUREMENT OPS LOCAL VALIDATION GREEN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
