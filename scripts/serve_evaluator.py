"""Start the Docker-only evaluator on loopback; no local execution fallback."""

import argparse
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from code_repair.execution import DockerBackend
from code_repair.service import EvaluationServer, TaskRegistry


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--image", required=True, help="Pre-pulled Python image pinned by digest")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--dataset", type=Path, action="append", help="Defaults to formal train/dev data")
    args = parser.parse_args()
    token = os.environ.get("CODE_REPAIR_SERVICE_TOKEN", "")
    if len(token) < 32:
        parser.error("Set CODE_REPAIR_SERVICE_TOKEN to a random token of at least 32 characters")
    backend = DockerBackend(args.image)
    readiness = backend.execute("def readiness(): return True", "readiness", [[]], timeout=10)
    if readiness.status != "completed" or readiness.rows[0].get("value") is not True:
        parser.error("Docker backend is unavailable; run verify_sandbox.py first")
    registry = TaskRegistry(args.dataset or [ROOT / "data/mbpp_repair/v0.1"])
    with EvaluationServer(("127.0.0.1", args.port), registry, backend, token) as server:
        print(f"Evaluator listening on 127.0.0.1:{server.server_port}; {len(registry.tasks)} train/dev tasks", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
