"""Scripted known-fixture episodes; no model. Default backend requires Docker."""

import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from code_repair.environment import RepairEnvironment  # noqa: E402
from code_repair.execution import DockerBackend, TrustedLocalBackend  # noqa: E402
from code_repair.tasks import load_task  # noqa: E402
from code_repair.evaluation import RemoteEvaluator  # noqa: E402


def run_scenario(task_dir, backend, *, repair, trace_root, service_url=None, token=None):
    task = load_task(task_dir, include_private=service_url is None)
    evaluator = RemoteEvaluator(service_url, token, task.task_id) if service_url else None
    env = RepairEnvironment(task, backend=backend, evaluator=evaluator)
    rewards = []
    with env:
        rewards.append(env.step({"name": "read_file", "arguments": {"path": "solution.py"}}).reward)
        initial = env.step({"name": "run_tests", "arguments": {}})
        rewards.append(initial.reward)
        public_initial_failed = bool(initial.tool_response and initial.tool_response["ok"]
                                     and initial.tool_response["output"]["failed"] > 0)
        if repair and not env.done:
            # Reference loaded only by this trusted script; never by the env or its tools.
            reference = (task_dir / "reference/solution.py").read_text(encoding="utf-8")
            written = env.step({"name": "write_file", "arguments": {"path": "solution.py", "content": reference}})
            rewards.append(written.reward)
            if not env.done:
                checked = env.step({"name": "run_tests", "arguments": {}})
                rewards.append(checked.reward)
        terminal = env.step({"final": "完成本次脚本检查。"})
        rewards.append(terminal.reward)
        repeated = env.step({"final": "再次结束，不应重复发放奖励。"})
        scenario = {"reward": sum(rewards), "terminal_reward": terminal.reward,
                    "repeated_terminal_reward": repeated.reward, "done": terminal.done,
                    "valid_episode": terminal.info["valid_episode"],
                    "termination_reason": terminal.info["termination_reason"],
                    "public_initial_failed": public_initial_failed}
        trace = list(env.trace)
        workspace = env.workspace
    scenario["workspace_removed"] = not workspace.exists()
    scenario["valid"] = (scenario["done"] and scenario["valid_episode"]
                         and scenario["reward"] == (1.0 if repair else 0.0)
                         and repeated.reward == 0.0 and public_initial_failed
                         and scenario["workspace_removed"])
    destination = trace_root / task.task_id
    destination.mkdir(parents=True, exist_ok=True)
    filename = "repaired.jsonl" if repair else "original.jsonl"
    (destination / filename).write_text("".join(json.dumps(event, ensure_ascii=False) + "\n" for event in trace))
    return scenario


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backend", choices=("docker", "trusted-local", "remote"), default="docker")
    parser.add_argument("--dataset", choices=("prototype", "mbpp"), default="prototype")
    parser.add_argument("--service-url", default="http://127.0.0.1:8765")
    parser.add_argument("--image", help="Pre-pulled Python image pinned as repository@sha256:digest")
    parser.add_argument("--output", type=Path, default=ROOT / "reports/episode_verification.json")
    parser.add_argument("--traces", type=Path, default=ROOT / "runs/prototype-episodes")
    args = parser.parse_args()
    if args.backend == "docker" and not args.image:
        parser.error("Docker requires --image; trusted-local is only for the authored scripted fixtures")
    token = os.environ.get("CODE_REPAIR_SERVICE_TOKEN")
    health = None
    if args.backend == "remote":
        health = RemoteEvaluator(args.service_url, token, "health").health()
        if health.get("backend") != "docker" or health.get("container_isolation_configured") is not True:
            parser.error("Scripted remote acceptance requires the Docker-only service")
        DockerBackend(health["image"])  # Check immutable image syntax too.
        backend = None
    else:
        backend = DockerBackend(args.image) if args.backend == "docker" else TrustedLocalBackend()
    dataset = ROOT / ("data/prototype" if args.dataset == "prototype" else "data/mbpp_repair/v0.1")
    manifest = json.loads((dataset / "manifest.json").read_text())
    rows = []
    for item in manifest["tasks"]:
        task_dir = dataset / item["path"]
        remote = {"service_url": args.service_url, "token": token} if health else {}
        original = run_scenario(task_dir, backend, repair=False, trace_root=args.traces, **remote)
        repaired = run_scenario(task_dir, backend, repair=True, trace_root=args.traces, **remote)
        valid = original["valid"] and repaired["valid"]
        rows.append({"task_id": item["task_id"], "original": original, "repaired": repaired, "valid": valid})
        print(f"{'PASS' if valid else 'FAIL'} {item['task_id']} original={original['reward']} repaired={repaired['reward']}", flush=True)
    report = {"schema_version": 1, "backend": "remote-docker" if health else backend.name,
              "container_isolation": True if health else backend.isolated,
              "image": health["image"] if health else getattr(backend, "image", None),
              "dataset": args.dataset, "public_only_client": bool(health),
              "uses_model": False, "uses_reference_patches": True,
              "total_tasks": len(rows), "total_episodes": 2 * len(rows),
              "valid_tasks": sum(row["valid"] for row in rows), "tasks": rows,
              "complete": all(row["valid"] for row in rows)}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(f"Valid tasks: {report['valid_tasks']}/{report['total_tasks']}; {report['total_episodes']} scripted episodes")
    return 0 if report["valid_tasks"] == report["total_tasks"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
