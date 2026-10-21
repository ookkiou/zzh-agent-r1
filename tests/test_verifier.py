import json
from pathlib import Path
import shutil
import tempfile
import unittest

from scripts.verify_tasks import ROOT, run_suite, verify_dataset, verify_task


class VerifierTests(unittest.TestCase):
    def test_twenty_distinct_sources_and_four_bug_categories(self):
        manifest = json.loads((ROOT / "data/prototype/manifest.json").read_text())
        metadata = [json.loads((ROOT / "data/prototype" / item["path"] / "task.json").read_text())
                    for item in manifest["tasks"]]
        self.assertEqual(len({task["source_id"] for task in metadata}), 20)
        for split in ("train", "dev"):
            self.assertEqual(sum(task["split"] == split for task in metadata), 10)
        for category in ("boundary", "index_slice", "initialization", "missing_branch"):
            self.assertEqual(sum(task["bug_type"] == category for task in metadata), 5)

    def test_dataset_tampering_is_rejected_before_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "dataset"
            shutil.copytree(ROOT / "data/prototype", target)
            (target / "train/repair-001/starter/solution.py").write_text("raise RuntimeError()\n")
            with self.assertRaisesRegex(ValueError, "resource changed"):
                verify_dataset(target)

    def test_non_defective_starter_cannot_be_accepted_as_a_bug_task(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "task"
            shutil.copytree(ROOT / "data/prototype/train/repair-001", target)
            shutil.copyfile(target / "reference/solution.py", target / "starter/solution.py")
            report = verify_task(target)
            self.assertFalse(report["valid"])
            self.assertEqual(report["starter"]["private"]["failed"], 0)

    def test_private_cases_reject_a_patch_that_only_passes_public_examples(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            (workspace / "solution.py").write_text(
                "def count_at_least(values, threshold):\n    return 2 if values else 0\n")
            task = ROOT / "data/prototype/train/repair-001"
            shutil.copyfile(task / "public_tests.py", workspace / "public_tests.py")
            public = run_suite(workspace, "count_at_least", "public")
            private = run_suite(workspace, "count_at_least", "private",
                                json.loads((task / "private_tests.json").read_text()))
            self.assertTrue(public["completed"])
            self.assertEqual(public["failed"], 0)
            self.assertGreater(private["failed"], 0)

    def test_private_checker_rejects_integer_in_place_of_boolean(self):
        with tempfile.TemporaryDirectory() as directory:
            workspace = Path(directory)
            (workspace / "solution.py").write_text("def f():\n    return 1\n")
            result = run_suite(workspace, "f", "private",
                               [{"id": "boolean", "args": [], "expected": True}])
            self.assertEqual(result["failed"], 1)

    def test_empty_acceptance_cases_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "task"
            shutil.copytree(ROOT / "data/prototype/train/repair-001", target)
            (target / "private_tests.json").write_text("[]\n")
            with self.assertRaisesRegex(ValueError, "at least five"):
                verify_task(target)


if __name__ == "__main__":
    unittest.main()
