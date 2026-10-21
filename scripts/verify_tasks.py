"""Offline starter/reference verification; no model, GPU, or external packages."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from code_repair.contracts import validate_candidate_source  # noqa: E402


def run_suite(workspace, entrypoint, mode, cases=None):
    try:
        result = subprocess.run(
            [sys.executable, "-I", "-B", str(ROOT / "scripts/_fixture_worker.py"),
             mode, str(workspace), entrypoint],
            input=json.dumps(cases) if cases is not None else "",
            text=True, capture_output=True, timeout=5, cwd=workspace)
    except subprocess.TimeoutExpired:
        return {"completed": False, "reason": "fixture_timeout"}
    if result.returncode:
        return {"completed": False, "reason": "worker_error",
                "log": result.stderr[-2000:]}
    try:
        return json.loads(result.stdout)
    except json.JSONDecodeError:
        return {"completed": False, "reason": "invalid_worker_response"}


def verify_task(task_dir):
    metadata = json.loads((task_dir / "task.json").read_text())
    cases = json.loads((task_dir / "private_tests.json").read_text())
    starter = (task_dir / "starter/solution.py").read_text()
    reference = (task_dir / "reference/solution.py").read_text()
    validate_candidate_source(starter, starter, metadata["entrypoint"])
    validate_candidate_source(reference, starter, metadata["entrypoint"])
    if len(cases) < 5 or len({case["id"] for case in cases}) != len(cases):
        raise ValueError("Private cases must have at least five unique IDs")
    report = {"task_id": metadata["task_id"], "source_id": metadata["source_id"],
              "split": metadata["split"], "bug_type": metadata["bug_type"]}
    for variant in ("starter", "reference"):
        with tempfile.TemporaryDirectory(prefix="code-repair-verify-") as directory:
            workspace = Path(directory)
            shutil.copyfile(task_dir / variant / "solution.py", workspace / "solution.py")
            shutil.copyfile(task_dir / "public_tests.py", workspace / "public_tests.py")
            report[variant] = {
                "public": run_suite(workspace, metadata["entrypoint"], "public"),
                "private": run_suite(workspace, metadata["entrypoint"], "private", cases)}
    checks = [report[variant][mode] for variant in ("starter", "reference")
              for mode in ("public", "private")]
    report["valid"] = (
        all(check["completed"] and check["tests"] > 0 for check in checks)
        and report["starter"]["public"]["failed"] > 0
        and report["starter"]["private"]["failed"] > 0
        and report["reference"]["public"]["failed"] == 0
        and report["reference"]["private"]["failed"] == 0)
    return report


def verify_dataset(dataset):
    manifest = json.loads((dataset / "manifest.json").read_text())
    if len(manifest["tasks"]) != 20:
        raise ValueError("Prototype must contain exactly 20 tasks")
    source_splits, task_ids = {}, set()
    digest = hashlib.sha256()
    for relative, expected in sorted(manifest["files"].items()):
        path = (dataset / relative).resolve()
        if not path.is_relative_to(dataset.resolve()):
            raise ValueError("Manifest path escapes dataset")
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            raise ValueError(f"Dataset resource changed: {relative}")
        digest.update(f"{relative}:{actual}\n".encode())
    reports = []
    for item in manifest["tasks"]:
        task_dir = (dataset / item["path"]).resolve()
        if not task_dir.is_relative_to(dataset.resolve()):
            raise ValueError("Task path escapes dataset")
        report = verify_task(task_dir)
        if report["task_id"] in task_ids:
            raise ValueError("Duplicate task ID")
        task_ids.add(report["task_id"])
        source = report["source_id"]
        if source in source_splits and source_splits[source] != report["split"]:
            raise ValueError("Source leaked across splits")
        source_splits[source] = report["split"]
        reports.append(report)
    split_counts = {split: sum(task["split"] == split for task in reports)
                    for split in ("train", "dev")}
    if split_counts != {"train": 10, "dev": 10}:
        raise ValueError("Prototype requires 10 train / 10 dev tasks")
    return {"schema_version": 1, "dataset_version": manifest["version"],
            "dataset_sha256": digest.hexdigest(), "python": sys.version.split()[0],
            "execution_scope": "trusted local fixtures; not a security sandbox",
            "total": len(reports), "valid": sum(task["valid"] for task in reports),
            "split_counts": split_counts, "tasks": reports}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=ROOT / "data/prototype")
    parser.add_argument("--output", type=Path, default=ROOT / "reports/prototype_verification.json")
    args = parser.parse_args()
    try:
        report = verify_dataset(args.dataset.resolve())
    except (OSError, ValueError, KeyError) as error:
        print(f"Verification error: {error}", file=sys.stderr)
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    for task in report["tasks"]:
        print(f"{'PASS' if task['valid'] else 'FAIL'} {task['task_id']} {task['split']} {task['bug_type']}")
    print(f"Valid tasks: {report['valid']}/{report['total']}; report: {args.output}")
    return 0 if report["valid"] == report["total"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
