"""Re-run and record the concrete Day 1 acceptance criteria."""

import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from code_repair.contracts import TOOL_SCHEMAS  # noqa: E402
from scripts.verify_tasks import verify_dataset  # noqa: E402


def main():
    generated = subprocess.run([sys.executable, str(ROOT / "scripts/build_prototype.py"), "--check"],
                               capture_output=True, text=True)
    verification = verify_dataset(ROOT / "data/prototype")
    lock = json.loads((ROOT / "UPSTREAM_LOCK.json").read_text())
    schemas = {item["function"]["name"]: item["function"]["parameters"] for item in TOOL_SCHEMAS}
    criteria = {
        "twenty_verified_tasks": verification["total"] == verification["valid"] == 20,
        "ten_train_ten_dev": verification["split_counts"] == {"train": 10, "dev": 10},
        "generated_resources_match": generated.returncode == 0,
        "each_reference_passes_and_starter_fails": all(item["valid"] for item in verification["tasks"]),
        "three_tool_schemas_fixed": set(schemas) == {"read_file", "write_file", "run_tests"}
            and schemas["read_file"]["required"] == ["path"]
            and schemas["write_file"]["required"] == ["path", "content"]
            and schemas["run_tests"]["properties"] == {},
        "model_and_algorithm_selected": lock["model"]["repository"] == "Qwen/Qwen2.5-Coder-1.5B-Instruct"
            and lock["algorithm"] == "grpo",
        "upstream_commit_pinned": len(lock["agent_r1"]["commit"]) == 40
            and all(character in "0123456789abcdef" for character in lock["agent_r1"]["commit"]),
    }
    report = {"schema_version": 1, "stage": "day-1", "complete": all(criteria.values()),
              "criteria": criteria, "dataset_sha256": verification["dataset_sha256"],
              "contract_sha256": hashlib.sha256((ROOT / "code_repair/contracts.py").read_bytes()).hexdigest(),
              "upstream_lock": lock, "verification_report": "reports/prototype_verification.json"}
    reports = ROOT / "reports"
    reports.mkdir(exist_ok=True)
    (reports / "prototype_verification.json").write_text(json.dumps(verification, ensure_ascii=False, indent=2) + "\n")
    (reports / "day1_acceptance.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n")
    for criterion, passed in criteria.items():
        print(f"{'PASS' if passed else 'FAIL'} {criterion}")
    print(f"Day 1 complete: {report['complete']}")
    return 0 if report["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
