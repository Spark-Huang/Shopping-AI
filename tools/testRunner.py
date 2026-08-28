#!/usr/bin/env python3
"""Run Shopping AI offline and integration test suites."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path
from urllib.request import urlopen


REPO_ROOT = Path(__file__).resolve().parents[1]
TESTS_DIR = REPO_ROOT / "tests"


def run(command: list[str], cwd: Path, **kwargs) -> int:
    return subprocess.run(command, cwd=cwd, **kwargs).returncode


def unit(pytest_args: list[str]) -> int:
    return run((sys.executable, "-m", "pytest", "-c", "tests/pytest.ini", *pytest_args), REPO_ROOT)


def integration(host: str, port: int, timeout: int) -> int:
    try:
        with urlopen(f"http://{host}:{port}/health", timeout=timeout) as response:
            if response.status >= 500:
                return 1
    except Exception as exc:
        print(f"orchestrator health check failed: {exc}", file=sys.stderr)
        return 1
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("suite", choices=("unit", "integration", "all"), nargs="?", default="all")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8009)
    parser.add_argument("--timeout", type=int, default=5)
    parser.add_argument("pytest_args", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    if args.pytest_args and args.pytest_args[0] == "--":
        args.pytest_args.pop(0)

    statuses: list[int] = []
    if args.suite in {"unit", "all"}:
        statuses.append(unit(args.pytest_args or ["tests/unit"]))
    if args.suite in {"integration", "all"}:
        statuses.append(integration(args.host, args.port, args.timeout))
    return 1 if any(statuses) else 0


if __name__ == "__main__":
    raise SystemExit(main())
