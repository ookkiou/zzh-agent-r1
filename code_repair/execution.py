"""Bounded execution backends. Local backend is ONLY for authored fixtures."""

from dataclasses import dataclass
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import threading
import time
import uuid


WORKER = r'''
import contextlib, json, sys
emit = json.dumps
output = sys.stdout
payload = json.load(sys.stdin)
def validate_value(value):
    if type(value) in (str, int, float, bool, type(None)):
        emit(value, allow_nan=False)
    elif type(value) is list:
        for item in value: validate_value(item)
    elif type(value) is dict and all(type(key) is str for key in value):
        for item in value.values(): validate_value(item)
    else:
        raise TypeError("Candidate output must use native JSON types")
class Discard:
    def write(self, text): return len(text)
    def flush(self): pass
rows = []
with contextlib.redirect_stdout(Discard()), contextlib.redirect_stderr(Discard()):
    namespace = {"__name__": "candidate", "__file__": "/tmp/solution.py"}
    try:
        exec(compile(payload["source"], "solution.py", "exec"), namespace)
        function = namespace[payload["entrypoint"]]
        load_error = None
    except BaseException as error:
        load_error = type(error).__name__
    for args in payload["inputs"]:
        try:
            if load_error:
                rows.append({"kind": "exception", "error": load_error})
            else:
                value = function(*args)
                validate_value(value)
                emit(value, allow_nan=False)
                rows.append({"kind": "return", "value": value})
        except BaseException as error:
            rows.append({"kind": "exception", "error": type(error).__name__})
output.write(emit({"rows": rows}, allow_nan=False))
output.flush()
'''


@dataclass(frozen=True)
class ExecutionOutcome:
    status: str
    rows: tuple = ()
    detail: str = ""
    elapsed_seconds: float = 0.0


def _kill_group(process):
    try:
        if os.name == "posix":
            os.killpg(process.pid, signal.SIGKILL)
        else:
            process.kill()
    except ProcessLookupError:
        pass


def run_bounded(command, payload, timeout, output_limit=8192):
    """Drain bounded pipes; kill the process group on timeout/output flood."""
    started = time.monotonic()
    environment = {"PATH": os.environ.get("PATH", os.defpath), "LANG": "C.UTF-8"}
    for name in ("DOCKER_HOST", "DOCKER_CONTEXT", "DOCKER_CONFIG"):
        if name in os.environ:
            environment[name] = os.environ[name]
    try:
        process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, env=environment,
                                   start_new_session=os.name == "posix")
    except OSError as error:
        return "infrastructure_error", b"", str(error), None, time.monotonic() - started
    buffers = [bytearray(), bytearray()]
    exceeded = threading.Event()

    def drain(pipe, buffer):
        while True:
            try:
                chunk = os.read(pipe.fileno(), 4096)
            except OSError:
                break
            if not chunk:
                break
            remaining = output_limit - len(buffer)
            if remaining > 0:
                buffer.extend(chunk[:remaining])
            if len(chunk) > remaining:
                exceeded.set()
                _kill_group(process)
                break

    def send():
        try:
            process.stdin.write(payload)
            process.stdin.close()
        except (BrokenPipeError, OSError):
            pass

    threads = [threading.Thread(target=drain, args=(pipe, buffer), daemon=True)
               for pipe, buffer in zip((process.stdout, process.stderr), buffers)]
    threads.append(threading.Thread(target=send, daemon=True))
    for thread in threads:
        thread.start()
    status = "completed"
    try:
        process.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        status = "timeout"
    finally:
        _kill_group(process)
        process.wait(timeout=2)
        for thread in threads:
            thread.join(timeout=2)
        for pipe in (process.stdin, process.stdout, process.stderr):
            if not pipe.closed:
                pipe.close()
    if exceeded.is_set():
        status = "output_limit"
    return status, bytes(buffers[0]), bytes(buffers[1]).decode(errors="replace"), \
        process.returncode, time.monotonic() - started


def _outcome(result, expected_count, *, docker=False):
    status, stdout, stderr, returncode, elapsed = result
    if status != "completed":
        return ExecutionOutcome(status, detail=stderr[-1000:], elapsed_seconds=elapsed)
    if docker and returncode in (125, 126, 127):
        return ExecutionOutcome("infrastructure_error", detail=stderr[-1000:], elapsed_seconds=elapsed)
    if returncode:
        return ExecutionOutcome("candidate_error", detail=stderr[-1000:], elapsed_seconds=elapsed)
    try:
        data = json.loads(stdout)
        rows = data["rows"]
        if not isinstance(rows, list) or len(rows) != expected_count:
            raise ValueError("Wrong case result count")
        for row in rows:
            if row.get("kind") == "return" and set(row) == {"kind", "value"}:
                json.dumps(row["value"], allow_nan=False)
            elif (row.get("kind") == "exception" and set(row) == {"kind", "error"}
                  and isinstance(row["error"], str)):
                continue
            else:
                raise ValueError("Malformed case result")
    except (ValueError, KeyError, TypeError, AttributeError) as error:
        return ExecutionOutcome("candidate_error", detail=str(error), elapsed_seconds=elapsed)
    return ExecutionOutcome("completed", tuple(rows), elapsed_seconds=elapsed)


def _payload(source, entrypoint, inputs):
    # The worker receives inputs, never expected outputs or private test source.
    value = json.dumps({"source": source, "entrypoint": entrypoint, "inputs": inputs}, allow_nan=False).encode()
    if len(value) > 262144:
        raise ValueError("Execution request too large")
    return value


class TrustedLocalBackend:
    """Explicit opt-in for known repository fixtures, never model outputs."""
    name = "trusted-local"
    isolated = False

    def execute(self, source, entrypoint, inputs, timeout=5):
        return _outcome(run_bounded([sys.executable, "-I", "-B", "-c", WORKER],
                                   _payload(source, entrypoint, inputs), timeout), len(inputs))


class DockerBackend:
    """No host mounts/network; requires an already pulled digest-pinned image."""
    name = "docker"
    isolated = True

    def __init__(self, image):
        if not isinstance(image, str) or not re.fullmatch(r"[^\s]+@sha256:[0-9a-f]{64}", image):
            raise ValueError("Docker image must be pinned by sha256 digest")
        self.image = image

    def command(self, name):
        return ["docker", "run", "--rm", "--pull=never", "--name", name, "-i",
                "--network=none", "--read-only", "--user=65534:65534", "--cap-drop=ALL",
                "--security-opt=no-new-privileges", "--pids-limit=32", "--memory=256m",
                "--memory-swap=256m", "--cpus=1", "--tmpfs=/tmp:rw,nosuid,noexec,size=16m",
                "--workdir=/tmp", self.image, "python", "-I", "-B", "-c", WORKER]

    def execute(self, source, entrypoint, inputs, timeout=5):
        if not shutil.which("docker"):
            return ExecutionOutcome("infrastructure_error", detail="docker executable unavailable")
        name = "code-repair-" + uuid.uuid4().hex
        try:
            result = run_bounded(self.command(name), _payload(source, entrypoint, inputs), timeout)
            return _outcome(result, len(inputs), docker=True)
        finally:
            # Killing the CLI alone does not necessarily stop its container.
            try:
                subprocess.run(["docker", "rm", "-f", name], timeout=5,
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except (OSError, subprocess.TimeoutExpired):
                pass


def strict_equal(actual, expected):
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, list):
        return len(actual) == len(expected) and all(strict_equal(a, b) for a, b in zip(actual, expected))
    if isinstance(expected, dict):
        return actual.keys() == expected.keys() and all(strict_equal(actual[k], v) for k, v in expected.items())
    return actual == expected


def check_cases(backend, source, entrypoint, cases, timeout=5):
    if not cases:
        raise ValueError("Cannot accept zero tests")
    outcome = backend.execute(source, entrypoint, [case["args"] for case in cases], timeout)
    if outcome.status != "completed":
        return {"status": outcome.status, "tests": len(cases), "passed": 0,
                "failed": len(cases), "failures": [], "timed_out": outcome.status == "timeout",
                "elapsed_seconds": outcome.elapsed_seconds}
    failures = []
    for case, row in zip(cases, outcome.rows):
        if row["kind"] != "return" or not strict_equal(row["value"], case["expected"]):
            failures.append({"id": case["id"], "reason": row.get("error", "wrong_result")})
    return {"status": "completed", "tests": len(cases), "passed": len(cases) - len(failures),
            "failed": len(failures), "failures": failures, "timed_out": False,
            "elapsed_seconds": outcome.elapsed_seconds}
