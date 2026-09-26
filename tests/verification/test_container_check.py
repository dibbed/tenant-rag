"""Container Build Check (REQ-MTS-CI-005): deterministic failures, and the container is always removed."""

from __future__ import annotations

import json
from typing import Any

import pytest

HEALTHY = '{"status": "healthy"}'
REFUSED = '{"detail": "Authentication required"}'
GOOD = {
    ("GET", "/health"): (200, HEALTHY),
    ("GET", "/api/v1/health"): (200, HEALTHY),
    ("POST", "/api/v1/query"): (401, REFUSED),
    ("POST", "/api/v1/documents/reset"): (401, REFUSED),
}


@pytest.fixture(scope="module")
def container_check(verification_script):
    return verification_script("container_check")


class FakeClock:
    """Every call is one second later."""

    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        self.now += 1.0
        return self.now


class FakeDocker:
    """Scripted answers of the docker command."""

    def __init__(self, module: Any, **options: Any) -> None:
        self.module = module
        self.calls: list[list[str]] = []
        self.options: dict[str, Any] = {
            "version": 0,
            "build": 0,
            "run": 0,
            "state": "running 0",
            "health": {"Status": "healthy"},
            "pid1_uid": 10001,
            "uids": (10001,),
            "user": "appuser",
        }
        self.options.update(options)

    def verbs(self) -> list[str]:
        return [call[1] for call in self.calls]

    def __call__(self, command: list[str], timeout: float | None = None, stream: bool = False) -> Any:
        self.calls.append(list(command))
        result = self.module.CommandResult
        verb = command[1]
        options = self.options
        if verb == "version":
            ok = options["version"] == 0
            return result(options["version"], "28.0.4\n" if ok else "", "" if ok else "Cannot connect to the Docker daemon")
        if verb == "build":
            return result(options["build"], "step 1/2\nstep 2/2", "" if options["build"] == 0 else "ERROR: failed to solve")
        if verb == "run":
            return result(options["run"], "abc123\n", "")
        if verb == "image":
            return result(0, f"{options['user']}\n", "")
        if verb == "inspect":
            template = command[3]
            if "State.Health" in template:
                return result(0, json.dumps(options["health"]) + "\n", "")
            if "State.Status" in template:
                return result(0, options["state"] + "\n", "")
            return result(0, f"{options['user']}\n", "")
        if verb == "exec":
            if command[3] == "cat":
                uid = options["pid1_uid"]
                return result(0, f"Name:\tpython\nUid:\t{uid}\t{uid}\t{uid}\t{uid}\n", "")
            return result(0, "".join(f"Uid:\t{uid}\t{uid}\t{uid}\t{uid}\n" for uid in options["uids"]), "")
        if verb == "logs":
            return result(0, "INFO startup complete\n", "")
        if verb == "rm":
            return result(0, "", "")
        raise AssertionError(f"unexpected docker command: {command}")


class FakeHttp:
    """Scripted HTTP answers by (method, path)."""

    def __init__(self, module: Any, responses: dict[tuple[str, str], tuple[int, str]]) -> None:
        self.module = module
        self.responses = responses

    def __call__(self, method: str, url: str, payload: Any = None, headers: Any = None, timeout: float = 30.0) -> Any:
        path = "/" + url.split("/", 3)[3]
        status, body = self.responses.get((method, path), (None, ""))
        return self.module.HttpResult(status, body, None if status else "connection refused")


def _execute(module: Any, docker: FakeDocker, http: Any) -> dict[str, Any]:
    check = module.ContainerCheck(
        image="tenant-rag:test",
        context=".",
        port=18000,
        startup_timeout=10,
        health_timeout=10,
        build=True,
        run=docker,
        http=http,
        sleep=lambda _seconds: None,
        clock=FakeClock(),
        name="tenant-rag-verification-test",
    )
    return check.execute()


def test_a_healthy_non_root_image_passes(container_check):
    docker = FakeDocker(container_check)
    report = _execute(container_check, docker, FakeHttp(container_check, GOOD))
    assert report["status"] == "pass"
    assert [step["step"] for step in report["steps"]] == ["build", "start", "ready", "health", "auth", "user"]
    assert report["details"]["uid"] == 10001
    assert [probe["status"] for probe in report["details"]["auth_probes"]] == [401, 401]
    assert docker.verbs()[-1] == "rm"


def test_a_failed_build_fails_without_starting_a_container(container_check):
    docker = FakeDocker(container_check, build=1)
    report = _execute(container_check, docker, FakeHttp(container_check, GOOD))
    assert report["status"] == "fail"
    assert report["steps"][-1]["step"] == "build"
    assert "failed to solve" in "\n".join(report["steps"][-1]["output_tail"])
    assert "run" not in docker.verbs()
    assert "rm" not in docker.verbs()


def test_a_container_that_exits_fails_with_its_log_and_is_removed(container_check):
    docker = FakeDocker(container_check, state="exited 1")
    report = _execute(container_check, docker, FakeHttp(container_check, GOOD))
    assert report["status"] == "fail"
    assert report["steps"][-1]["step"] == "ready"
    assert "exit code 1" in report["steps"][-1]["detail"]
    assert report["log_tail"] == ["INFO startup complete"]
    assert docker.verbs()[-1] == "rm"


def test_a_health_endpoint_that_never_answers_200_times_out(container_check):
    responses = GOOD | {("GET", "/health"): (503, '{"status": "unhealthy"}')}
    docker = FakeDocker(container_check)
    report = _execute(container_check, docker, FakeHttp(container_check, responses))
    assert report["status"] == "fail"
    assert report["steps"][-1]["step"] == "ready"
    assert "HTTP 503" in report["steps"][-1]["detail"]
    assert docker.verbs()[-1] == "rm"


def test_an_image_without_healthcheck_fails(container_check):
    docker = FakeDocker(container_check, health=None)
    report = _execute(container_check, docker, FakeHttp(container_check, GOOD))
    assert report["steps"][-1]["step"] == "health"
    assert "no HEALTHCHECK" in report["steps"][-1]["detail"]


def test_an_unhealthy_healthcheck_fails(container_check):
    health = {"Status": "unhealthy", "Log": [{"Output": "curl: (7) connection refused"}]}
    report = _execute(container_check, FakeDocker(container_check, health=health), FakeHttp(container_check, GOOD))
    assert report["status"] == "fail"
    assert "unhealthy" in report["steps"][-1]["detail"]


def test_a_request_without_credentials_that_is_accepted_fails(container_check):
    responses = GOOD | {("POST", "/api/v1/documents/reset"): (200, '{"success": true}')}
    docker = FakeDocker(container_check)
    report = _execute(container_check, docker, FakeHttp(container_check, responses))
    assert report["status"] == "fail"
    assert report["steps"][-1]["step"] == "auth"
    assert "POST /api/v1/documents/reset answered 200" in report["steps"][-1]["detail"]
    assert docker.verbs()[-1] == "rm"


@pytest.mark.parametrize(("pid1_uid", "uids"), [(0, (0,)), (10001, (0, 10001))])
def test_a_container_running_as_root_fails(container_check, pid1_uid, uids):
    docker = FakeDocker(container_check, pid1_uid=pid1_uid, uids=uids)
    report = _execute(container_check, docker, FakeHttp(container_check, GOOD))
    assert report["status"] == "fail"
    assert report["steps"][-1]["step"] == "user"
    assert "runs as root" in report["steps"][-1]["detail"]
    assert docker.verbs()[-1] == "rm"


def test_docker_not_available_is_an_error(container_check):
    docker = FakeDocker(container_check, version=1)
    report = _execute(container_check, docker, FakeHttp(container_check, GOOD))
    assert report["status"] == "error"
    assert docker.verbs() == ["version"]


def test_an_unexpected_error_still_removes_the_container(container_check):
    def broken_http(*_args: Any, **_kwargs: Any) -> Any:
        raise RuntimeError("network stack failure")

    docker = FakeDocker(container_check)
    report = _execute(container_check, docker, broken_http)
    assert report["status"] == "fail"
    assert report["steps"][-1]["step"] == "internal"
    assert docker.verbs()[-1] == "rm"


def test_effective_uid_reads_the_second_field(container_check):
    assert container_check.effective_uid("Name:\tx\nUid:\t1000\t10001\t10001\t10001\n") == 10001
    assert container_check.effective_uid("no uid here") is None
