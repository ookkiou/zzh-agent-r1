"""Loopback-only trusted evaluation control plane; production CLI uses Docker only."""

import hashlib
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import math
from pathlib import Path
import threading

from .contracts import ContractError, validate_candidate_source
from .execution import check_cases
from .tasks import load_task

MAX_REQUEST_BYTES = 65536


class TaskRegistry:
    def __init__(self, datasets):
        self.tasks, self.manifest_hashes = {}, []
        for directory in datasets:
            root = Path(directory).resolve()
            manifest_bytes = (root / "manifest.json").read_bytes()
            manifest = json.loads(manifest_bytes)
            self.manifest_hashes.append(hashlib.sha256(manifest_bytes).hexdigest())
            for item in manifest["tasks"]:
                split = item.get("split", Path(item["path"]).parts[0])
                if split not in ("train", "dev"):
                    raise ValueError("Evaluation service currently permits train/dev tasks only")
                task_dir = root / item["path"]
                if not task_dir.resolve().is_relative_to(root):
                    raise ValueError("Task path escapes dataset")
                # The service never opens reference/solution.py.
                for name in ("task.json", "starter/solution.py", "public_tests.py", "private_tests.json"):
                    relative = item["path"] + "/" + name
                    path = root / relative
                    if path.is_symlink() or not path.resolve().is_relative_to(root):
                        raise ValueError("Task resource escapes dataset")
                    if hashlib.sha256(path.read_bytes()).hexdigest() != manifest["files"][relative]:
                        raise ValueError("Task resource checksum mismatch")
                task = load_task(task_dir)
                metadata = json.loads((task_dir / "task.json").read_text())
                if metadata['split'] != split or any(metadata[key] != item[key] for key in
                        ("task_id", "source_id") if key in item):
                    raise ValueError("Task index mismatch")
                if task.task_id in self.tasks:
                    raise ValueError("Duplicate task ID")
                self.tasks[task.task_id] = task
        if not self.tasks:
            raise ValueError("Registry cannot be empty")


class EvaluationServer(ThreadingHTTPServer):
    daemon_threads = True

    def __init__(self, address, registry, backend, token, *, test_timeout=5, concurrency=4):
        if address[0] != "127.0.0.1":
            raise ValueError("Bind the service to 127.0.0.1; remote clients must use an SSH tunnel")
        if not isinstance(token, str) or len(token) < 32:
            raise ValueError("Service token must contain at least 32 characters")
        if type(concurrency) is not int or not 1 <= concurrency <= 32:
            raise ValueError("Concurrency must be an integer between 1 and 32")
        if not math.isfinite(test_timeout) or not 0 < test_timeout <= 30:
            raise ValueError("Execution timeout must be positive and at most 30 seconds")
        self.registry, self.backend, self.token = registry, backend, token
        self.test_timeout = test_timeout
        self.slots = threading.BoundedSemaphore(concurrency)
        super().__init__(address, EvaluationHandler)


class EvaluationHandler(BaseHTTPRequestHandler):
    def setup(self):
        super().setup()
        self.connection.settimeout(15)

    def log_message(self, *args):
        pass  # Never log candidate source, private cases or authorization headers.

    def reply(self, status, payload):
        content = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("Connection", "close")
        self.end_headers()
        try:
            self.wfile.write(content)
        except (BrokenPipeError, ConnectionResetError):
            pass
        self.close_connection = True

    def authorized(self):
        supplied = self.headers.get("Authorization", "")
        if not hmac.compare_digest(supplied.encode(), ("Bearer " + self.server.token).encode()):
            self.reply(401, {"error": "unauthorized"})
            return False
        return True

    def do_GET(self):
        if not self.authorized():
            return
        if self.path != "/health":
            self.reply(404, {"error": "not_found"})
            return
        self.reply(200, {"status": "ok", "api_version": 1, "backend": self.server.backend.name,
                         "container_isolation_configured": self.server.backend.isolated,
                         "image": getattr(self.server.backend, "image", None),
                         "task_count": len(self.server.registry.tasks),
                         "dataset_manifest_sha256": self.server.registry.manifest_hashes})

    def do_POST(self):
        if not self.authorized():
            return
        if self.path != "/v1/evaluate":
            self.reply(404, {"error": "not_found"})
            return
        try:
            length = int(self.headers.get("Content-Length", "-1"))
        except ValueError:
            length = -1
        if not 0 < length <= MAX_REQUEST_BYTES or self.headers.get("Transfer-Encoding"):
            self.reply(413, {"error": "request_size_or_framing_invalid"})
            return
        if self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
            self.reply(415, {"error": "requires_json"})
            return
        try:
            content = self.rfile.read(length)
            if len(content) != length:
                raise ValueError("Incomplete body")
            data = json.loads(content, parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
            if (not isinstance(data, dict) or set(data) != {"task_id", "source", "mode"}
                    or not all(isinstance(data[key], str) for key in data)
                    or data["mode"] not in ("public", "private")):
                raise ValueError("Invalid fields")
        except (OSError, ValueError):
            self.reply(400, {"error": "invalid_request"})
            return
        task = self.server.registry.tasks.get(data["task_id"])
        if task is None:
            self.reply(404, {"error": "unknown_task"})
            return
        try:
            validate_candidate_source(data["source"], task.starter_source, task.entrypoint)
        except ContractError:
            self.reply(422, {"error": "invalid_source_or_signature"})
            return
        if not self.server.slots.acquire(blocking=False):
            self.reply(503, {"error": "execution_capacity_exhausted"})
            return
        try:
            cases = task.public_cases if data["mode"] == "public" else task.private_cases
            result = check_cases(self.server.backend, data["source"], task.entrypoint,
                                 cases, timeout=self.server.test_timeout)
            if data["mode"] == "private":
                result = {key: result[key] for key in (
                    "status", "tests", "passed", "failed", "timed_out", "elapsed_seconds")}
            self.reply(200, result)
        except (OSError, ValueError):
            self.reply(503, {"error": "evaluation_infrastructure_error"})
        finally:
            self.server.slots.release()
