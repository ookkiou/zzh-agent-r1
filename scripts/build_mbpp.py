"""Build reviewed MBPP repair tasks and freeze an independent test-source cohort.

Offline after fetch_mbpp.py. Executes ONLY explicitly reviewed known fixtures,
never arbitrary upstream records or model-generated code.
"""

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import sys
import warnings

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from code_repair.contracts import validate_candidate_source
from code_repair.dataset import (mutations, near_duplicate, native_json, normalize_record,
                                 render_public_tests, sha256, source_features, source_split)
from code_repair.execution import TrustedLocalBackend, check_cases
from scripts.fetch_mbpp import DESTINATION, verify_snapshot
from scripts.mbpp_specs import REVIEW_EXCLUSIONS, SPECS

VERSION = "mbpp-repair@0.1.0"
OUTPUT = ROOT / "data/mbpp_repair/v0.1"
TEST_SOURCES = 50
MAX_VARIANTS = 3
SELECTION_SEED = "mbpp-repair-test-sources-v1"
PIPELINE_FILES = ("code_repair/dataset.py", "code_repair/contracts.py", "code_repair/execution.py",
                  "scripts/fetch_mbpp.py", "scripts/build_mbpp.py", "scripts/mbpp_specs.py")


def json_text(value):
    return json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n"


def reviewed_cases(record, spec):
    public = [{"id": f"test_public_{i:02d}", **case}
              for i, case in enumerate(record["upstream_cases"][:2], 1)]
    private = [{"id": "upstream_holdout", **record["upstream_cases"][2]}, *spec["cases"]]
    public_inputs = {json.dumps(case["args"], sort_keys=True) for case in public}
    seen, accepted = set(), []
    for case in private:
        key = json.dumps(case["args"], sort_keys=True)
        if key in public_inputs or key in seen:
            continue
        if not native_json(case["args"]) or not native_json(case["expected"]):
            raise ValueError("Reviewed case is not native JSON")
        seen.add(key)
        accepted.append(case)
    if len(accepted) < 5 or len(spec["cases"]) < 6:
        raise ValueError(f"Insufficient distinct private regression cases: {record['source_id']}")
    return public, accepted


def find_duplicate(features, occupied):
    for source_id, other in occupied:
        reason = near_duplicate(features, other)
        if reason:
            return {"matched_source_id": source_id, "reason": reason}
    return None


def choose_mutations(record, public, private, backend):
    grouped = defaultdict(list)
    for item in mutations(record["reference"]):
        grouped[item["bug_type"]].append(item)
    # Try one location from each category before trying further same-category sites.
    ordered = []
    for index in range(max(map(len, grouped.values()), default=0)):
        ordered.extend(grouped[kind][index] for kind in sorted(grouped) if index < len(grouped[kind]))
    accepted, rejected, behaviors = [], [], set()
    for item in ordered:
        validate_candidate_source(item["source"], record["reference"], record["entrypoint"])
        public_result = check_cases(backend, item["source"], record["entrypoint"], public, timeout=0.5)
        if public_result["status"] != "completed" or not public_result["failed"]:
            rejected.append({"mutation": item["mutation"], "reason": "not_a_completed_public_failure"})
            continue
        private_result = check_cases(backend, item["source"], record["entrypoint"], private, timeout=0.5)
        if private_result["status"] != "completed" or not private_result["failed"]:
            rejected.append({"mutation": item["mutation"], "reason": "not_a_completed_private_failure"})
            continue
        # Collapse candidates with the same observed failures; this does NOT prove semantic equivalence.
        behavior = json.dumps([public_result["failures"], private_result["failures"]], sort_keys=True)
        if behavior in behaviors:
            rejected.append({"mutation": item["mutation"], "reason": "same_observed_failure_pattern"})
            continue
        behaviors.add(behavior)
        accepted.append({**item, "verification": {"public": public_result, "private": private_result}})
        if len(accepted) == MAX_VARIANTS:
            break
    return accepted, rejected


def build_resources():
    warnings.filterwarnings("ignore", category=SyntaxWarning)
    lock = verify_snapshot()
    raw_records = [json.loads(line) for line in (DESTINATION / "mbpp.jsonl").read_text().splitlines()]
    if len({row["task_id"] for row in raw_records}) != len(raw_records):
        raise ValueError("Duplicate upstream source IDs")
    records, audit = {}, []
    for raw in sorted(raw_records, key=lambda row: row["task_id"]):
        task_id = raw["task_id"]
        reason = REVIEW_EXCLUSIONS.get(task_id)
        try:
            if reason:
                raise ValueError("review_exclusion: " + reason)
            record = normalize_record(raw)
        except (SyntaxError, ValueError, TypeError, KeyError) as error:
            audit.append({"source_id": f"mbpp-{task_id:03d}", "split": source_split(task_id),
                          "status": "excluded", "reason": str(error)})
            continue
        record["features"] = source_features(record["reference"])
        records[task_id] = record
        audit.append({"source_id": record["source_id"], "split": record["split"],
                      "status": "statically_eligible", "executed": False})

    # Existing prototype sources have already been inspected during development.
    prototype = ROOT / "data/prototype"
    prototype_manifest = json.loads((prototype / "manifest.json").read_text())
    occupied = [(f"prototype:{item['task_id']}", source_features(
        (prototype / item["path"] / "reference/solution.py").read_text()))
        for item in prototype_manifest["tasks"]]
    resources, tasks, source_reports, duplicates = {}, [], [], []
    backend = TrustedLocalBackend()
    for task_id, spec in sorted(SPECS.items()):
        if source_split(task_id) not in ("train", "dev"):
            raise ValueError("Test sources cannot enter train/dev contract development")
        if task_id not in records:
            raise ValueError(f"Reviewed source is incompatible with converter: {task_id}")
        record = records[task_id]
        duplicate = find_duplicate(record["features"], occupied)
        if duplicate:
            duplicates.append({"source_id": record["source_id"], "split": record["split"], **duplicate})
            continue
        public, private = reviewed_cases(record, spec)
        reference_results = {"public": check_cases(backend, record["reference"], record["entrypoint"], public),
                             "private": check_cases(backend, record["reference"], record["entrypoint"], private)}
        if any(result["status"] != "completed" or result["failed"] for result in reference_results.values()):
            raise ValueError(f"Reviewed reference contradicts contract: {record['source_id']} {reference_results}")
        for result in reference_results.values():
            result.pop("elapsed_seconds", None)
        variants, rejected = choose_mutations(record, public, private, backend)
        source_reports.append({"source_id": record["source_id"], "split": record["split"],
                               "domain": spec["domain"], "review_note": spec["review_note"],
                               "review_status": "agent_reviewed_not_human_signed_off",
                               "reference": reference_results, "accepted_variants": len(variants),
                               "rejected_candidates": rejected})
        # Reserve reviewed sources even if mutation filtering produces no valid tasks.
        occupied.append((record["source_id"], record["features"]))
        for index, variant in enumerate(variants, 1):
            task_name = f"{record['source_id']}-m{index:02d}"
            relative = f"{record['split']}/{task_name}"
            instruction = (record["instruction"] + "\n\n精确输入域与验收约定：" + spec["domain"]
                           + f"\n修复 solution.py 中的 {record['entrypoint']} 函数，保留签名。")
            metadata = {"task_id": task_name, "source_id": record["source_id"], "split": record["split"],
                        "entrypoint": record["entrypoint"], "instruction": instruction,
                        "bug_type": variant["bug_type"], "mutation": variant["mutation"],
                        "source": {"repository": lock["repository"], "commit": lock["commit"],
                                   "task_id": task_id, "raw_code_sha256": record["raw_code_sha256"],
                                   "reference_sha256": record["reference_sha256"]},
                        "domain": spec["domain"], "review_status": "agent_reviewed_not_human_signed_off",
                        "public_cases": len(public), "private_cases": len(private)}
            assets = {"task.json": json_text(metadata), "starter/solution.py": variant["source"],
                      "reference/solution.py": record["reference"],
                      "public_tests.py": render_public_tests(record["entrypoint"], public),
                      "private_tests.json": json_text(private)}
            resources.update({f"{relative}/{name}": content for name, content in assets.items()})
            tasks.append({"task_id": task_name, "source_id": record["source_id"], "split": record["split"],
                          "bug_type": variant["bug_type"], "path": relative})
        print(f"REVIEW {record['source_id']} {record['split']}: {len(variants)} valid mutations", flush=True)

    # Reserve sources without running test references, mutations, or any model.
    test_pool = [record for record in records.values() if record["split"] == "test" and mutations(record["reference"])]
    test_pool.sort(key=lambda row: sha256(f"{SELECTION_SEED}:{row['source_id']}"))
    frozen, test_duplicates = [], []
    for record in test_pool:
        duplicate = find_duplicate(record["features"], occupied)
        if duplicate:
            test_duplicates.append({"source_id": record["source_id"], **duplicate})
            continue
        frozen.append({key: record[key] for key in (
            "source_id", "upstream_task_id", "raw_code_sha256", "reference_sha256")}
            | {"normalized_sha256": record["features"]["normalized_sha256"],
               "shape_sha256": record["features"]["shape_sha256"]})
        occupied.append((record["source_id"], record["features"]))
        if len(frozen) == TEST_SOURCES:
            break
    if len(frozen) != TEST_SOURCES:
        raise ValueError("Insufficient distinct test sources; do not pad with duplicate tasks")
    freeze = {"schema_version": 1, "version": VERSION, "stage": "source_cohort_only",
              "source_commit": lock["commit"], "source_file_sha256": lock["files"]["mbpp.jsonl"]["sha256"],
              "selection_seed": SELECTION_SEED, "selection_uses_model_results": False,
              "references_executed": False, "cases_expanded": False,
              "contract_review_complete": False, "test_tasks_generated": False,
              "source_count": len(frozen), "sources": frozen}
    resources["test_sources.lock.json"] = json_text(freeze)
    selection = {"schema_version": 1, "version": VERSION, "source_records": len(raw_records),
                 "statically_eligible": len(records), "source_audit": audit,
                 "reviewed_sources": source_reports, "review_exclusions": REVIEW_EXCLUSIONS,
                 "duplicates_excluded": duplicates, "test_duplicates_excluded": test_duplicates,
                 "dedup_policy": {"normalized_ast": True, "constant_abstracted_ast": True,
                                  "ast_token_similarity_threshold": 0.92,
                                  "includes_prototype_sources": True,
                                  "semantic_equivalence_guaranteed": False}}
    resources["selection_report.json"] = json_text(selection)
    sources = {split: sorted({item["source_id"] for item in tasks if item["split"] == split})
               for split in ("train", "dev")}
    manifest = {"schema_version": 1, "version": VERSION, "source_lock_sha256": sha256(json_text(lock)),
                "pipeline_files": {name: sha256((ROOT / name).read_bytes()) for name in PIPELINE_FILES},
                "split_policy": {"train": [601, 974], "dev": [511, 600], "test": [11, 510],
                                 "prompt_only": [1, 10]},
                "task_counts": dict(Counter(task["split"] for task in tasks)),
                "source_counts": {split: len(items) for split, items in sources.items()},
                "bug_counts": dict(Counter(task["bug_type"] for task in tasks)),
                "sources": sources, "tasks": tasks, "frozen_test_sources": len(frozen),
                "files": {path: sha256(content) for path, content in sorted(resources.items())}}
    resources["manifest.json"] = json_text(manifest)
    return resources


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Rebuild and compare without overwriting")
    args = parser.parse_args()
    resources = build_resources()
    # Measured timing is volatile; reports omit it to permit deterministic rebuilds.
    problems = []
    for relative, content in resources.items():
        path = OUTPUT / relative
        if path.exists():
            if path.read_text() != content:
                problems.append(f"changed: {relative}")
        elif args.check:
            problems.append(f"missing: {relative}")
    unexpected = {str(path.relative_to(OUTPUT)) for path in OUTPUT.rglob("*") if path.is_file()} - resources.keys()
    problems.extend(f"unexpected: {path}" for path in sorted(unexpected))
    if problems:
        print("\n".join(problems))
        return 1
    if not args.check:
        for relative, content in resources.items():
            path = OUTPUT / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
    manifest = json.loads(resources["manifest.json"])
    print(f"{'Checked' if args.check else 'Built'} {manifest['task_counts']} tasks; "
          f"{manifest['source_counts']} original sources; frozen test sources={TEST_SOURCES}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
