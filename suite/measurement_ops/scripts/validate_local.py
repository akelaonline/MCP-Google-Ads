from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(*args: str) -> None:
    print("+", " ".join(args), flush=True)
    subprocess.run(args, cwd=ROOT, check=True)


def main() -> int:
    run(sys.executable, "-m", "ruff", "check", "src", "tests", "scripts")
    run(sys.executable, "-m", "pytest", "-q")
    run(
        sys.executable,
        "-c",
        (
            "from mkt_measurement_ops.server import mcp; "
            "from mkt_measurement_ops import __version__; "
            "print('MCP import OK', __version__, type(mcp).__name__)"
        ),
    )
    print("MEASUREMENT OPS LOCAL VALIDATION GREEN")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
