"""Verify formal development data and a frozen, unexecuted test-source cohort."""

import argparse
import ast
from collections import Counter
import copy
import json
from pathlib import Path
import re
import sys
import warnings

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from code_repair.contracts import validate_candidate_source
from code_repair.dataset import (near_duplicate, native_json, normalize_record, replace_at,
                                 sha256, source_features, source_split)
from code_repair.execution import TrustedLocalBackend, check_cases
from code_repair.tasks import load_task
from scripts.build_mbpp import OUTPUT, PIPELINE_FILES, SELECTION_SEED, TEST_SOURCES, reviewed_cases
from scripts.fetch_mbpp import DESTINATION, verify_snapshot
from scripts.mbpp_specs import SPECS


def safe_path(dataset, relative):
    path = dataset / relative
    if path.is_symlink() or not path.resolve().is_relative_to(dataset.resolve()):
        raise ValueError("Dataset path is a symlink or escapes its root")
    return path


def validate_single_mutation(reference, starter, mutation):
    before, after = ast.parse(reference), ast.parse(starter)
    path = mutation["ast_path"]
    if not path or not mutation["single_location"]:
        raise ValueError("Mutation must identify exactly one AST location")
    original, changed = before, after
    try:
        for part in path:
            original = original[part] if type(part) is int else getattr(original, part)
            changed = changed[part] if type(part) is int else getattr(changed, part)
        if ast.dump(original) != mutation["before"] or ast.dump(changed) != mutation["after"]:
            raise ValueError("Recorded mutation does not match source")
        replace_at(before, path, copy.deepcopy(changed))
    except (IndexError, AttributeError, TypeError) as error:
        raise ValueError("Invalid mutation path") from error
    if ast.dump(before) != ast.dump(after) or ast.dump(original) == ast.dump(changed):
        raise ValueError("Candidate changes more or less than the recorded one location")


def verify_dataset(dataset=OUTPUT):
    warnings.filterwarnings("ignore", category=SyntaxWarning)
    dataset = Path(dataset).resolve()
    lock = verify_snapshot()
    manifest = json.loads((dataset / "manifest.json").read_text())
    if manifest["source_lock_sha256"] != sha256(json.dumps(lock, ensure_ascii=False, indent=2) + "\n"):
        raise ValueError("Upstream source lock differs from dataset provenance")
    if set(manifest["pipeline_files"]) != set(PIPELINE_FILES):
        raise ValueError("Incomplete converter provenance")
    for relative, digest in manifest["pipeline_files"].items():
        if sha256((ROOT / relative).read_bytes()) != digest:
            raise ValueError(f"Converter changed: {relative}; explicitly create a new data version")
    expected_files = set(manifest["files"]) | {"manifest.json"}
    actual_files = {str(path.relative_to(dataset)) for path in dataset.rglob("*") if path.is_file()}
    if actual_files != expected_files:
        raise ValueError("Dataset has missing or undeclared assets")
    digest_lines = []
    for relative, expected in sorted(manifest["files"].items()):
        actual = sha256(safe_path(dataset, relative).read_bytes())
        if actual != expected:
            raise ValueError(f"Dataset resource changed: {relative}")
        digest_lines.append(f"{relative}:{actual}\n")
    raw = {row["task_id"]: row for row in map(json.loads, (DESTINATION / "mbpp.jsonl").read_text().splitlines())}
    backend = TrustedLocalBackend()
    reports, task_ids, sources, all_assets = [], set(), {}, set()
    for item in manifest["tasks"]:
        path = safe_path(dataset, item["path"])
        metadata = json.loads((path / "task.json").read_text())
        task = load_task(path)
        reference = (path / "reference/solution.py").read_text()
        match = re.fullmatch(r"mbpp-(\d{3})-m\d{2}", task.task_id)
        if not match or task.task_id in task_ids:
            raise ValueError("Invalid or duplicate task ID")
        task_ids.add(task.task_id)
        task_id = int(match[1])
        record = normalize_record(raw[task_id])
        split = source_split(task_id)
        if split not in ("train", "dev") or task_id not in SPECS:
            raise ValueError("Unreviewed or held-out source entered development tasks")
        if any(item[key] != metadata[key] for key in ("task_id", "source_id", "split", "bug_type")):
            raise ValueError("Task index differs from metadata")
        if metadata["split"] != split or metadata["source_id"] != record["source_id"]:
            raise ValueError("Original source split changed")
        if item["path"] != f"{split}/{task.task_id}" or task.entrypoint != record["entrypoint"]:
            raise ValueError("Task path or entrypoint changed")
        source = metadata["source"]
        if (reference != record["reference"] or source["commit"] != lock["commit"]
                or source["repository"] != lock["repository"] or source["task_id"] != task_id
                or source["reference_sha256"] != sha256(reference)
                or source["raw_code_sha256"] != sha256(raw[task_id]["code"])):
            raise ValueError("Reference/source provenance mismatch")
        public, private = reviewed_cases(record, SPECS[task_id])
        expected_instruction = (record["instruction"] + "\n\n精确输入域与验收约定：" + SPECS[task_id]["domain"]
                                + f"\n修复 solution.py 中的 {record['entrypoint']} 函数，保留签名。")
        if (metadata["domain"] != SPECS[task_id]["domain"] or task.instruction != expected_instruction
                or metadata["public_cases"] != len(public) or metadata["private_cases"] != len(private)
                or metadata["review_status"] != "agent_reviewed_not_human_signed_off"):
            raise ValueError("Task requirement differs from reviewed contract")
        if list(task.public_cases) != public or list(task.private_cases) != private:
            raise ValueError("Task cases differ from reviewed upstream and regression inputs")
        if not all(native_json(case) for case in [*public, *private]):
            raise ValueError("Cases require native JSON types")
        validate_candidate_source(reference, task.starter_source, task.entrypoint)
        validate_single_mutation(reference, task.starter_source, metadata["mutation"])
        result = {"task_id": task.task_id, "source_id": record["source_id"], "split": split,
                  "bug_type": metadata["bug_type"]}
        for name, source_text in (("reference", reference), ("starter", task.starter_source)):
            result[name] = {mode: check_cases(backend, source_text, task.entrypoint, cases)
                            for mode, cases in (("public", public), ("private", private))}
        checks = [result[variant][mode] for variant in ("reference", "starter") for mode in ("public", "private")]
        result["valid"] = (all(check["status"] == "completed" and check["tests"] > 0 for check in checks)
                           and all(result["reference"][mode]["failed"] == 0 for mode in ("public", "private"))
                           and all(result["starter"][mode]["failed"] > 0 for mode in ("public", "private")))
        reports.append(result)
        sources[task_id] = record
        all_assets.update(f"{item['path']}/{name}" for name in (
            "task.json", "starter/solution.py", "reference/solution.py", "public_tests.py", "private_tests.json"))
    if set(manifest["files"]) != all_assets | {"selection_report.json", "test_sources.lock.json"}:
        raise ValueError("Manifest must cover exactly five resources per task and the two source reports")
    counts = dict(Counter(item["split"] for item in reports))
    source_lists = {split: sorted(row["source_id"] for row in sources.values() if row["split"] == split)
                    for split in ("train", "dev")}
    if (counts != manifest["task_counts"] or source_lists != manifest["sources"]
            or {split: len(items) for split, items in source_lists.items()} != manifest["source_counts"]
            or dict(Counter(item["bug_type"] for item in reports)) != manifest["bug_counts"]):
        raise ValueError("Manifest counts differ from verified tasks")

    freeze = json.loads((dataset / "test_sources.lock.json").read_text())
    if (freeze["source_count"] != TEST_SOURCES or len(freeze["sources"]) != TEST_SOURCES
            or manifest["frozen_test_sources"] != TEST_SOURCES or freeze["version"] != manifest["version"]
            or freeze["source_commit"] != lock["commit"]
            or freeze["source_file_sha256"] != lock["files"]["mbpp.jsonl"]["sha256"]
            or freeze["selection_seed"] != SELECTION_SEED
            or freeze["stage"] != "source_cohort_only" or freeze["references_executed"]
            or freeze["test_tasks_generated"] or freeze["selection_uses_model_results"]
            or freeze["cases_expanded"] or freeze["contract_review_complete"]):
        raise ValueError("Invalid test source freeze")
    occupied = []
    selection = json.loads((dataset / "selection_report.json").read_text())
    reviewed_ids = [int(row["source_id"].split("-")[1]) for row in selection["reviewed_sources"]]
    if len(set(reviewed_ids)) != len(reviewed_ids) or not set(sources).issubset(reviewed_ids):
        raise ValueError("Inconsistent source review index")
    for task_id in reviewed_ids:
        if task_id not in SPECS or source_split(task_id) not in ("train", "dev"):
            raise ValueError("Invalid development source review")
        row = normalize_record(raw[task_id])
        occupied.append((row["source_id"], source_features(row["reference"])))
    frozen_ids = set()
    for source in freeze["sources"]:
        task_id = source["upstream_task_id"]
        if task_id in frozen_ids or source_split(task_id) != "test":
            raise ValueError("Duplicate or misplaced test source")
        frozen_ids.add(task_id)
        row = normalize_record(raw[task_id])
        features = source_features(row["reference"])
        for key in ("source_id", "raw_code_sha256", "reference_sha256"):
            if source[key] != row[key]:
                raise ValueError("Frozen test source changed")
        if any(source[key] != features[key] for key in ("normalized_sha256", "shape_sha256")):
            raise ValueError("Frozen test source fingerprint changed")
        occupied.append((row["source_id"], features))
    prototype = ROOT / "data/prototype"
    for item in json.loads((prototype / "manifest.json").read_text())["tasks"]:
        features = source_features((prototype / item["path"] / "reference/solution.py").read_text())
        for source_id, other in occupied:
            if near_duplicate(features, other):
                raise ValueError(f"Formal source overlaps prototype: {source_id}")
    for index, (source_id, features) in enumerate(occupied):
        for other_id, other in occupied[index + 1:]:
            if near_duplicate(features, other):
                raise ValueError(f"Duplicate selected sources: {source_id} / {other_id}")
    complete = (len(reports) > 0 and all(item["valid"] for item in reports)
                and manifest["source_counts"]["train"] >= 30 and manifest["source_counts"]["dev"] >= 10)
    return {"schema_version": 1, "stage": "day-2-3", "complete": complete,
            "dataset_version": manifest["version"], "dataset_sha256": sha256("".join(digest_lines)),
            "manifest_sha256": sha256((dataset / "manifest.json").read_bytes()),
            "source_commit": lock["commit"], "python": sys.version.split()[0],
            "execution_scope": "reviewed known local fixtures; not a security sandbox",
            "total": len(reports), "valid": sum(item["valid"] for item in reports),
            "task_counts": counts, "source_counts": manifest["source_counts"],
            "bug_counts": manifest["bug_counts"], "frozen_test_source_count": len(frozen_ids),
            "test_references_executed": False, "test_contract_review_complete": False,
            "human_review_complete": False, "final_training_size_reached": False,
            "checks": {"upstream_hashes_verified": True, "resource_hashes_verified": True,
                       "source_splits_inherited": True, "single_ast_mutation_verified": True,
                       "public_private_inputs_disjoint": True, "dedup_including_prototypes_passed": True,
                       "test_sources_frozen": True, "test_sources_not_executed": True},
            "tasks": reports}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=OUTPUT)
    parser.add_argument("--output", type=Path, default=ROOT / "reports/mbpp_verification.json")
    args = parser.parse_args()
    try:
        report = verify_dataset(args.dataset)
    except (OSError, ValueError, KeyError) as error:
        print(f"Verification error: {error}", file=sys.stderr)
        return 2
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    print(f"Valid tasks: {report['valid']}/{report['total']}; {report['task_counts']}")
    print(f"Original sources: {report['source_counts']}; frozen test sources: {report['frozen_test_source_count']}")
    print(f"Day 2–3 initial data acceptance: {report['complete']}")
    return 0 if report["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
