#!/usr/bin/env python3
"""Container Build Check (REQ-MTS-CI-005): build the image, start it with default settings, verify it.

    python scripts/verification/container_check.py [--build] [--image NAME] [--context DIR]
        [--port PORT] [--startup-timeout SECONDS] [--health-timeout SECONDS]
        [--report PATH] [--keep]

Steps:

  build   docker build (only with --build)
  start   docker run without any setting, so the image defaults apply: production
          mode, no credentials, no LLM key
  ready   GET /health answers HTTP 200 before the startup timeout; the check stops
          at once when the container exits
  health  GET /health and GET /api/v1/health answer HTTP 200 with a "status" field,
          and the image HEALTHCHECK reports "healthy" before the health timeout
  auth    requests without credentials to protected routes are refused with HTTP 401
  user    the effective UID of process 1 and of every other process in the
          container is not 0 (root)

The container is removed at the end, also after a failure (unless --keep). A
failed report includes the reason and the last lines of the container log.

Exit codes: 0 passed, 1 a check failed, 2 Docker is not available.
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import subprocess
import sys
import time
import urllib.error
import urllib.request
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Callable, Sequence

LABEL = "tenant-rag-verification"
CONTAINER_PORT = 8000
AUTH_PROBES: tuple[tuple[str, str, dict[str, Any]], ...] = (
    ("POST", "/api/v1/query", {"question": "Container Build Check"}),
    ("POST", "/api/v1/documents/reset", {}),
)
LOG_LINES = 150
OUTPUT_TAIL_LINES = 60


@dataclass
class CommandResult:
    returncode: int
    stdout: str
    stderr: str


@dataclass
class HttpResult:
    status: int | None
    body: str
    error: str | None = None

    def json(self) -> Any:
        try:
            return json.loads(self.body)
        except (TypeError, ValueError):
            return None


def _stream(command: Sequence[str], timeout: float | None) -> CommandResult:
    tail: deque[str] = deque(maxlen=OUTPUT_TAIL_LINES)
    started = time.monotonic()
    with subprocess.Popen(
        list(command), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1
    ) as proc:
        if proc.stdout is None:
            raise RuntimeError("no output pipe")
        for line in proc.stdout:
            print(line, end="", flush=True)
            tail.append(line.rstrip("\n"))
            if timeout is not None and time.monotonic() - started > timeout:
                proc.kill()
                return CommandResult(124, "\n".join(tail), f"timed out after {timeout:.0f} s")
        returncode = proc.wait()
    return CommandResult(returncode, "\n".join(tail), "")


def run_command(command: Sequence[str], timeout: float | None = None, stream: bool = False) -> CommandResult:
    """Run a command. With stream=True the output is printed while it runs."""
    try:
        if stream:
            return _stream(command, timeout)
        proc = subprocess.run(list(command), capture_output=True, text=True, timeout=timeout, check=False)
    except FileNotFoundError as exc:
        return CommandResult(127, "", str(exc))
    except subprocess.TimeoutExpired:
        return CommandResult(124, "", f"timed out after {timeout} s")
    return CommandResult(proc.returncode, proc.stdout, proc.stderr)


def http_request(
    method: str,
    url: str,
    payload: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
    timeout: float = 30.0,
) -> HttpResult:
    """One HTTP request with the standard library; never raises for HTTP or network errors."""
    data = None
    request_headers = dict(headers or {})
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        request_headers.setdefault("Content-Type", "application/json")
    request = urllib.request.Request(url, data=data, method=method, headers=request_headers)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return HttpResult(response.status, response.read(65536).decode("utf-8", "replace"))
    except urllib.error.HTTPError as exc:
        return HttpResult(exc.code, exc.read(65536).decode("utf-8", "replace"))
    except (urllib.error.URLError, OSError, ValueError) as exc:
        return HttpResult(None, "", str(getattr(exc, "reason", exc)))


def effective_uid(text: str) -> int | None:
    """Effective UID from the 'Uid:' line of /proc/<pid>/status."""
    for line in text.splitlines():
        fields = line.split()
        if fields and fields[0] == "Uid:" and len(fields) >= 3 and fields[2].isdigit():
            return int(fields[2])
    return None


class CheckFailedError(Exception):
    """A step failed; the step is already recorded."""


class DockerUnavailableError(Exception):
    """The docker command or the Docker daemon is not available."""


class ContainerCheck:
    """The steps of the Container Build Check, with injectable Docker and HTTP clients."""

    def __init__(
        self,
        *,
        image: str,
        context: str,
        port: int,
        startup_timeout: float,
        health_timeout: float,
        build: bool,
        keep: bool = False,
        run: Callable[..., CommandResult] = run_command,
        http: Callable[..., HttpResult] = http_request,
        sleep: Callable[[float], None] = time.sleep,
        clock: Callable[[], float] = time.monotonic,
        name: str | None = None,
    ) -> None:
        self.image = image
        self.context = context
        self.port = port
        self.startup_timeout = startup_timeout
        self.health_timeout = health_timeout
        self.build = build
        self.keep = keep
        self.run = run
        self.http = http
        self.sleep = sleep
        self.clock = clock
        self.name = name or f"{LABEL}-{os.getpid()}"
        self.steps: list[dict[str, Any]] = []
        self.details: dict[str, Any] = {}
        self.started = False

    def url(self, path: str) -> str:
        return f"http://127.0.0.1:{self.port}{path}"

    def docker(self, *args: str, timeout: float | None = 120, stream: bool = False) -> CommandResult:
        return self.run(["docker", *args], timeout=timeout, stream=stream)

    def record(self, step: str, status: str, detail: str, **extra: Any) -> None:
        self.steps.append({"step": step, "status": status, "detail": detail, **extra})
        print(f"[{status.upper()}] {step}: {detail}", flush=True)

    def fail(self, step: str, detail: str, **extra: Any) -> None:
        self.record(step, "fail", detail, **extra)
        raise CheckFailedError(detail)

    def execute(self) -> dict[str, Any]:
        """Run every step and return the report. The container is always removed."""
        report: dict[str, Any] = {
            "schema": 1,
            "check": "container",
            "title": "Container Build Check",
            "mode": "blocking",
            "image": self.image,
            "python": platform.python_version(),
        }
        unavailable = None
        try:
            self._check_docker()
            self._build()
            self._start()
            self._wait_until_ready()
            self._check_health()
            self._check_auth()
            self._check_user()
        except DockerUnavailableError as exc:
            unavailable = str(exc)
            self.record("docker", "error", unavailable)
        except CheckFailedError:
            pass
        except Exception as exc:  # the report must be written and the container removed
            self.record("internal", "fail", f"unexpected error: {exc!r}")
        finally:
            if self.started:
                failed = any(step["status"] != "pass" for step in self.steps)
                logs = self._logs()
                report["log_tail"] = logs if failed else logs[-20:]
                if not self.keep:
                    self._remove()
        failed_steps = [step for step in self.steps if step["status"] in ("fail", "error")]
        if unavailable:
            status = "error"
        elif failed_steps:
            status = "fail"
        else:
            status = "pass"
        report.update(
            status=status,
            steps=self.steps,
            details=self.details,
            problems=[f"{step['step']}: {step['detail']}" for step in failed_steps],
            summary=self._summary(status, failed_steps),
        )
        return report

    def _summary(self, status: str, failed_steps: list[dict[str, Any]]) -> str:
        if status != "pass":
            return "; ".join(f"{step['step']}: {step['detail']}" for step in failed_steps)
        details = self.details
        built = f"built in {details['build_seconds']:.0f} s" if "build_seconds" in details else "image present"
        probes = ", ".join(str(probe["status"]) for probe in details.get("auth_probes", []))
        return (
            f"{built}; ready after {details.get('ready_seconds', 0):.0f} s; health HTTP 200 "
            f"({details.get('health_status', {}).get('/api/v1/health')}); HEALTHCHECK healthy; "
            f"requests without credentials: HTTP {probes}; runtime UID {details.get('uid')}"
        )

    def _check_docker(self) -> None:
        result = self.docker("version", "--format", "{{.Server.Version}}", timeout=60)
        if result.returncode != 0:
            detail = (result.stderr or result.stdout).strip()[:300]
            raise DockerUnavailableError(f"docker is not available: {detail}")
        self.details["docker_version"] = result.stdout.strip()

    def _build(self) -> None:
        if not self.build:
            if self.docker("image", "inspect", self.image, timeout=60).returncode != 0:
                self.fail("build", f"the image {self.image} does not exist; run with --build")
            self.record("build", "pass", f"the image {self.image} exists (not rebuilt)")
            return
        started = self.clock()
        result = self.docker(
            "build", "--label", f"{LABEL}=1", "--tag", self.image, self.context, timeout=3600, stream=True
        )
        seconds = self.clock() - started
        if result.returncode != 0:
            tail = f"{result.stdout}\n{result.stderr}".strip().splitlines()[-OUTPUT_TAIL_LINES:]
            self.fail("build", f"docker build failed (exit code {result.returncode})", output_tail=tail)
        self.details["build_seconds"] = round(seconds, 1)
        self.record("build", "pass", f"the image {self.image} was built in {seconds:.0f} s")

    def _start(self) -> None:
        user = self.docker("image", "inspect", "--format", "{{.Config.User}}", self.image, timeout=60)
        self.details["image_user"] = user.stdout.strip() if user.returncode == 0 else ""
        result = self.docker(
            "run",
            "--detach",
            "--name",
            self.name,
            "--label",
            f"{LABEL}=1",
            "--publish",
            f"127.0.0.1:{self.port}:{CONTAINER_PORT}",
            self.image,
            timeout=120,
        )
        if result.returncode != 0:
            self.fail("start", f"docker run failed: {result.stderr.strip()[-500:]}")
        self.started = True
        self.record("start", "pass", f"the container {self.name} started with the default settings of the image")

    def _state(self) -> tuple[str, str]:
        result = self.docker("inspect", "--format", "{{.State.Status}} {{.State.ExitCode}}", self.name, timeout=30)
        fields = result.stdout.split()
        if result.returncode != 0 or not fields:
            return "missing", ""
        return fields[0], fields[1] if len(fields) > 1 else ""

    def _wait_until_ready(self) -> None:
        started = self.clock()
        deadline = started + self.startup_timeout
        while True:
            state, exit_code = self._state()
            if state != "running":
                self.fail("ready", f"the container stopped before it was ready (state {state}, exit code {exit_code})")
            response = self.http("GET", self.url("/health"), timeout=30)
            if response.status == 200:
                break
            last = f"HTTP {response.status}" if response.status else (response.error or "no answer")
            if self.clock() >= deadline:
                self.fail(
                    "ready",
                    f"GET /health did not answer HTTP 200 within {self.startup_timeout:.0f} s (last result: {last})",
                )
            self.sleep(2)
        seconds = self.clock() - started
        self.details["ready_seconds"] = round(seconds, 1)
        self.record("ready", "pass", f"GET /health answered HTTP 200 after {seconds:.0f} s")

    def _check_health(self) -> None:
        statuses: dict[str, Any] = {}
        for path in ("/health", "/api/v1/health"):
            response = self.http("GET", self.url(path), timeout=60)
            body = response.json()
            if response.status != 200 or not isinstance(body, dict) or "status" not in body:
                self.fail("health", f"GET {path} answered HTTP {response.status} with body {response.body[:200]!r}")
            statuses[path] = body["status"]
        self.details["health_status"] = statuses
        deadline = self.clock() + self.health_timeout
        while True:
            result = self.docker("inspect", "--format", "{{json .State.Health}}", self.name, timeout=30)
            try:
                health = json.loads(result.stdout or "null")
            except ValueError:
                health = None
            if not isinstance(health, dict):
                self.fail("health", "the image has no HEALTHCHECK")
            state = health.get("Status")
            if state == "healthy":
                break
            if state == "unhealthy":
                log = health.get("Log") or [{}]
                output = str(log[-1].get("Output", "")).strip()[-300:]
                self.fail("health", f"the Docker HEALTHCHECK reports unhealthy: {output}")
            if self.clock() >= deadline:
                self.fail(
                    "health",
                    f"the Docker HEALTHCHECK did not report healthy within {self.health_timeout:.0f} s (status {state})",
                )
            self.sleep(3)
        self.details["docker_health"] = "healthy"
        described = ", ".join(f"{path}: {value}" for path, value in statuses.items())
        self.record("health", "pass", f"HTTP 200 ({described}); Docker HEALTHCHECK healthy")

    def _check_auth(self) -> None:
        probes = []
        wrong = []
        for method, path, payload in AUTH_PROBES:
            response = self.http(method, self.url(path), payload=payload, timeout=30)
            body = response.json()
            detail = body.get("detail") if isinstance(body, dict) else None
            probes.append({"request": f"{method} {path}", "status": response.status, "detail": detail})
            if response.status != 401:
                wrong.append(f"{method} {path} answered {response.status or response.error}")
        self.details["auth_probes"] = probes
        if wrong:
            self.fail(
                "auth", "a request without credentials was not refused with HTTP 401: " + "; ".join(wrong), probes=probes
            )
        described = "; ".join(f"{probe['request']}: HTTP {probe['status']}" for probe in probes)
        self.record("auth", "pass", f"requests without credentials refused ({described})", probes=probes)

    def _check_user(self) -> None:
        first = self.docker("exec", self.name, "cat", "/proc/1/status", timeout=30)
        uid = effective_uid(first.stdout) if first.returncode == 0 else None
        every = self.docker(
            "exec", self.name, "sh", "-c", "grep -h '^Uid:' /proc/[0-9]*/status 2>/dev/null || true", timeout=30
        )
        uids = sorted({value for value in map(effective_uid, every.stdout.splitlines()) if value is not None})
        runtime = self.docker("inspect", "--format", "{{.Config.User}}", self.name, timeout=30)
        user = runtime.stdout.strip() if runtime.returncode == 0 else ""
        self.details.update(uid=uid, process_uids=uids, runtime_user=user)
        if uid is None:
            self.fail("user", "the UID of process 1 could not be read")
        if uid == 0 or 0 in uids:
            self.fail("user", f"the container runs as root (process 1 UID {uid}, process UIDs {uids})")
        self.record("user", "pass", f"process 1 runs as UID {uid} (USER {user or 'not set'}); no process runs as root")

    def _logs(self) -> list[str]:
        result = self.docker("logs", "--tail", str(LOG_LINES), self.name, timeout=60)
        return f"{result.stdout}{result.stderr}".splitlines()[-LOG_LINES:]

    def _remove(self) -> None:
        result = self.docker("rm", "--force", self.name, timeout=120)
        self.details["removed"] = result.returncode == 0


def _escape_data(value: str) -> str:
    return value.replace("%", "%25").replace("\r", "%0D").replace("\n", "%0A")


def print_report(report: dict[str, Any]) -> None:
    github = os.environ.get("GITHUB_ACTIONS") == "true"
    print()
    print(f"== {report['title']}: {report['status'].upper()} ==")
    print(report.get("summary", ""))
    for step in report.get("steps", []):
        print(f"  {step['step']:<8} {step['status'].upper():<5} {step['detail']}")
    if report["status"] != "pass" and report.get("log_tail"):
        print("::group::Container log (last lines)" if github else "Container log (last lines):")
        for line in report["log_tail"]:
            print(line)
        if github:
            print("::endgroup::")
    if github and report["status"] != "pass":
        message = _escape_data("\n".join(report.get("problems", [])))
        print(f"::error title=Container Build Check::{message}", flush=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Container Build Check: build the image, start it with default settings and verify it."
    )
    parser.add_argument("--build", action="store_true", help="build the image first")
    parser.add_argument("--image", default="tenant-rag:verification", help="image name (default: %(default)s)")
    parser.add_argument("--context", default=".", help="build context (default: %(default)s)")
    parser.add_argument("--port", type=int, default=18000, help="host port on 127.0.0.1 (default: %(default)s)")
    parser.add_argument("--startup-timeout", type=float, default=300.0, help="seconds (default: %(default)s)")
    parser.add_argument("--health-timeout", type=float, default=180.0, help="seconds (default: %(default)s)")
    parser.add_argument("--report", type=Path, help="write the JSON report to this file")
    parser.add_argument("--keep", action="store_true", help="keep the container after the check")
    args = parser.parse_args(argv)
    check = ContainerCheck(
        image=args.image,
        context=args.context,
        port=args.port,
        startup_timeout=args.startup_timeout,
        health_timeout=args.health_timeout,
        build=args.build,
        keep=args.keep,
    )
    report = check.execute()
    print_report(report)
    if args.report is not None:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    return {"pass": 0, "fail": 1}.get(report["status"], 2)


if __name__ == "__main__":
    sys.exit(main())
