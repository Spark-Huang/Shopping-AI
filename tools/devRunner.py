#!/usr/bin/env python3
"""Start Shopping AI services on the local host."""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen


REPO_ROOT = Path(__file__).resolve().parents[1]
RUN_DIR = REPO_ROOT / ".local-run"
LOG_DIR = RUN_DIR / "logs"
PID_DIR = RUN_DIR / "pids"


@dataclass(frozen=True)
class ServiceSpec:
    cwd: Path
    command: tuple[str, ...]
    host: str = "127.0.0.1"
    port: int = 80


SERVICES = {
    "search": ServiceSpec(REPO_ROOT / "search", ("uvicorn", "app.main:app", "--port", "8010"), port=8010),
    "memory": ServiceSpec(REPO_ROOT / "memory", ("uvicorn", "app.main:app", "--port", "8011"), port=8011),
    "safety": ServiceSpec(REPO_ROOT / "safety", ("uvicorn", "app.main:app", "--port", "8012"), port=8012),
    "orchestrator": ServiceSpec(REPO_ROOT / "orchestrator", ("uvicorn", "app.main:app", "--port", "8009"), port=8009),
    "web": ServiceSpec(REPO_ROOT / "web", ("npm", "run", "dev", "--", "--host"), port=5173),
}


def _wait_http(name: str, url: str, timeout: int) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        try:
            with urlopen(url, timeout=1) as response:
                if response.status < 500:
                    return True
        except Exception:
            pass
        time.sleep(0.5)
    print(f"{name} did not become ready at {url}", file=sys.stderr)
    return False


def _start(name: str, spec: ServiceSpec) -> None:
    pid_path = PID_DIR / f"{name}.pid"
    log_path = LOG_DIR / f"{name}.log"
    if pid_path.exists() and (int(pid_path.read_text().strip()) if pid_path.read_text().strip() else 0):
        print(f"{name} already has a recorded process")
        return

    environment = os.environ.copy()
    environment["PYTHONPATH"] = os.pathsep.join(
        [str(spec.cwd), environment.get("PYTHONPATH", "")]
    ).rstrip(os.pathsep)
    environment.setdefault("SHARED_CONFIG_ROOT", str(REPO_ROOT / "platform" / "configs"))
    environment.setdefault("SHARED_DATA_ROOT", str(REPO_ROOT / "platform" / "data"))

    with log_path.open("a", encoding="utf-8") as log_file:
        process = subprocess.Popen(
            spec.command,
            cwd=spec.cwd,
            env=environment,
            stdout=log_file,
            stderr=subprocess.STDOUT,
        )
    pid_path.write_text(f"{process.pid}\n")
    print(f"started {name} (pid {process.pid}, log {log_path})")


def start(services: list[str]) -> int:
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    PID_DIR.mkdir(parents=True, exist_ok=True)
    for name in services:
        _start(name, SERVICES[name])
    for name in services:
        spec = SERVICES[name]
        if not _wait_http(name, f"http://{spec.host}:{spec.port}", 90):
            return 1
    print("Shopping AI web UI: http://127.0.0.1:5173")
    return 0


def stop(services: list[str]) -> int:
    for name in reversed(services):
        pid_path = PID_DIR / f"{name}.pid"
        if not pid_path.exists():
            continue
        pid_text = pid_path.read_text().strip()
        if pid_text:
            try:
                os.kill(int(pid_text), 15)
            except ProcessLookupError:
                pass
        pid_path.unlink(missing_ok=True)
        print(f"stopped {name}")
    return 0


def status(services: list[str]) -> int:
    for name in services:
        pid_path = PID_DIR / f"{name}.pid"
        pid = int(pid_path.read_text()) if pid_path.exists() and pid_path.read_text().strip() else None
        alive = False
        if pid:
            try:
                os.kill(pid, 0)
                alive = True
            except ProcessLookupError:
                pass
        print(f"{name}: pid={pid or '-'} alive={alive} port={SERVICES[name].port}")
    return 0


def logs(services: list[str], lines: int) -> int:
    for name in services:
        log_path = LOG_DIR / f"{name}.log"
        print(f"===== {name} =====")
        if log_path.exists():
            subprocess.run(("tail", "-n", str(lines), str(log_path)), check=False)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("start", "stop", "status", "logs"))
    parser.add_argument("--service", choices=SERVICES, action="append")
    parser.add_argument("--lines", type=int, default=80)
    args = parser.parse_args()
    services = args.service or list(SERVICES)
    handlers = {"start": start, "stop": stop, "status": status}
    if args.command == "logs":
        return logs(services, args.lines)
    return handlers[args.command](services)


if __name__ == "__main__":
    raise SystemExit(main())
