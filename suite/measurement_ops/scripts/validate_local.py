from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORDPRESS_PLUGIN = ROOT / "wordpress" / "mkt-measurement-bridge" / "mkt-measurement-bridge.php"


def run(*args: str, env: dict[str, str] | None = None) -> None:
    print("+", " ".join(args), flush=True)
    subprocess.run(args, cwd=ROOT, check=True, env=env)


def main() -> int:
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

    php = shutil.which("php")
    if php and WORDPRESS_PLUGIN.exists():
        run(php, "-l", str(WORDPRESS_PLUGIN))
    else:
        print("PHP lint skipped (php executable not available)", flush=True)

    print("MEASUREMENT OPS LOCAL VALIDATION GREEN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
