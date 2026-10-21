"""Local fixture evaluator and authenticated client for a separate Docker service."""

import json
import math
import urllib.error
import urllib.parse
import urllib.request

from .execution import check_cases


class LocalEvaluator:
    def __init__(self, task, backend):
        if not task.private_cases:
            raise ValueError("Local evaluation requires private cases; use RemoteEvaluator for public-only tasks")
        self.task, self.backend = task, backend
        self.name = backend.name

    def check(self, source, mode, timeout=5):
        if mode not in ("public", "private"):
            raise ValueError("Unknown evaluation mode")
        cases = self.task.public_cases if mode == "public" else self.task.private_cases
        return check_cases(self.backend, source, self.task.entrypoint, cases, timeout=timeout)


class RemoteEvaluator:
    """Control-plane client. This object and its token must never enter model observations."""
    name = "remote-docker"

    def __init__(self, base_url, token, task_id):
        url = urllib.parse.urlsplit(base_url)
        if (url.scheme not in ("http", "https") or not url.hostname or url.username or url.password
                or url.query or url.fragment or url.path not in ("", "/")):
            raise ValueError("Use a service origin URL without credentials, query or path")
        if url.scheme == "http" and url.hostname not in ("127.0.0.1", "localhost", "::1"):
            raise ValueError("Remote HTTP requires an SSH tunnel; otherwise use HTTPS")
        if not isinstance(token, str) or len(token) < 32:
            raise ValueError("Service token must contain at least 32 characters")
        if not isinstance(task_id, str):
            raise ValueError("task_id must be a string")
        self.base_url, self.token, self.task_id = base_url.rstrip("/"), token, task_id
        # A loopback service must not be sent through shell proxy environment variables.
        self.opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

    def request(self, path, payload=None, timeout=20):
        data = None if payload is None else json.dumps(payload, ensure_ascii=False, allow_nan=False).encode()
        request = urllib.request.Request(self.base_url + path, data=data, headers={
            "Authorization": "Bearer " + self.token, "Content-Type": "application/json"})
        try:
            with self.opener.open(request, timeout=timeout) as response:
                content = response.read(131073)
                if len(content) > 131072:
                    raise ValueError("Service response exceeds limit")
                return json.loads(content, parse_constant=lambda value: (_ for _ in ()).throw(ValueError(value)))
        except urllib.error.HTTPError as error:
            error.close()
            raise

    def health(self):
        return self.request("/health", timeout=5)

    def check(self, source, mode, timeout=5):
        if mode not in ("public", "private"):
            raise ValueError("Unknown evaluation mode")
        try:
            result = self.request("/v1/evaluate", {"task_id": self.task_id, "source": source, "mode": mode},
                                  timeout=timeout + 15)
            if result["status"] not in ("completed", "timeout", "candidate_error", "output_limit", "infrastructure_error"):
                raise ValueError("Unknown execution status")
            tests, passed, failed = (result[key] for key in ("tests", "passed", "failed"))
            if (any(type(value) is not int or value < 0 for value in (tests, passed, failed))
                    or passed + failed != tests or (result["status"] == "completed" and tests == 0)):
                raise ValueError("Invalid result counts")
            if not math.isfinite(result.get("elapsed_seconds", 0)):
                raise ValueError("Invalid timing")
            return result
        except (OSError, urllib.error.URLError, ValueError, KeyError, TypeError):
            return {"status": "infrastructure_error", "tests": 0, "passed": 0, "failed": 0,
                    "failures": [], "timed_out": False, "elapsed_seconds": 0.0}
