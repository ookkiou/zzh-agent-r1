import ast
import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from code_repair.contracts import validate_candidate_source
from code_repair.dataset import (inspect_source, mutations, near_duplicate, native_json,
                                 parse_assertion, sha256, source_features, source_split)
from code_repair.tasks import extract_public_cases
from scripts.build_mbpp import OUTPUT, reviewed_cases
from scripts.verify_mbpp import safe_path, validate_single_mutation, verify_dataset


class ConversionTests(unittest.TestCase):
    def test_original_source_split_boundaries(self):
        for task_id, split in ((1, "prompt_only"), (10, "prompt_only"), (11, "test"),
                               (510, "test"), (511, "dev"), (600, "dev"),
                               (601, "train"), (974, "train")):
            self.assertEqual(source_split(task_id), split)
        for task_id in (0, 975):
            with self.assertRaises(ValueError):
                source_split(task_id)

    def test_literal_assertions_are_parsed_without_evaluation(self):
        self.assertEqual(parse_assertion("assert f([1, -2], 'a') == [False, None]", "f"),
                         {"args": [[1, -2], "a"], "expected": [False, None]})
        for text in ("assert f(__import__('os').system('echo bad')) == 0",
                     "assert f(x=1) == 1", "assert other(1) == 1", "assert f(1) > 0",
                     "assert f(1) == 1; print('side effect')"):
            with self.assertRaises(ValueError):
                parse_assertion(text, "f")

    def test_tuple_set_and_integer_dictionary_keys_are_not_silently_coerced(self):
        for text in ("assert f((1,2)) == 3", "assert f(1) == (1,2)",
                     "assert f({1:2}) == 2", "assert f(1) == {1,2}"):
            with self.assertRaises(ValueError):
                parse_assertion(text, "f")
        self.assertFalse(native_json(float("inf")))
        self.assertFalse(native_json(float("nan")))

    def test_source_eligibility_rejects_io_and_imports(self):
        for source in ("import os\ndef f(x): return x", "def f(x): return open(x).read()",
                       "def f(x): return x.__class__", "def f(x): return eval(x)",
                       "def f(x): return x\nf(1)"):
            with self.assertRaises(ValueError):
                inspect_source(source)
        entry, source = inspect_source("def f(x):\n return [n for n in x if n > 0]")
        self.assertEqual(entry, "f")
        self.assertIn("def f(x):", source)

    def test_alpha_renaming_detects_shadowed_builtin_variables(self):
        left = "def f(xs):\n sum=0\n for x in xs: sum+=x\n return sum"
        right = "def other(items):\n total=0\n for item in items: total+=item\n return total"
        self.assertEqual(near_duplicate(source_features(left), source_features(right)), "normalized_ast")

    def test_constant_only_task_variants_share_a_duplicate_cluster(self):
        left, right = "def f(n): return n * 2", "def g(value): return value * 3"
        self.assertEqual(near_duplicate(source_features(left), source_features(right)), "constant_abstracted_ast")

    def test_each_generated_mutation_changes_only_its_recorded_site(self):
        source = "def f(xs, n):\n total = 0\n if n > 0:\n  for i in range(n):\n   total += xs[i]\n return total\n"
        source = ast.unparse(ast.parse(source)) + "\n"
        candidates = mutations(source)
        self.assertEqual({item["bug_type"] for item in candidates},
                         {"boundary", "initialization", "index_slice", "missing_branch"})
        for item in candidates:
            validate_candidate_source(item["source"], source, "f")
            validate_single_mutation(source, item["source"], item["mutation"])
            self.assertGreater(item["mutation"]["line"], 0)

    def test_second_unrecorded_mutation_is_rejected(self):
        reference = "def f(x):\n total = 0\n return total + x\n"
        candidate = mutations(reference)[0]
        tampered = candidate["source"].replace("total + x", "total - x")
        with self.assertRaisesRegex(ValueError, "more or less"):
            validate_single_mutation(reference, tampered, candidate["mutation"])

    def test_public_renderer_matches_runtime_case_parser(self):
        from code_repair.dataset import render_public_tests
        cases = [{"id": "test_public_01", "args": [[1, 2]], "expected": 3},
                 {"id": "test_public_02", "args": [[]], "expected": 0}]
        self.assertEqual(extract_public_cases(render_public_tests("f", cases), "f"), cases)

    def test_private_inputs_are_distinct_and_disjoint_from_public(self):
        record = {"source_id": "example", "upstream_cases": [
            {"args": [1], "expected": 1}, {"args": [2], "expected": 2}, {"args": [3], "expected": 3}]}
        spec = {"cases": [{"id": f"case_{i}", "args": [i], "expected": i} for i in range(1, 9)]}
        public, private = reviewed_cases(record, spec)
        self.assertEqual(len(private), 6)
        self.assertFalse({json.dumps(case["args"]) for case in public}
                         & {json.dumps(case["args"]) for case in private})

    def test_path_escape_and_symlink_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(ValueError):
                safe_path(root, "../outside")
            (root / "link").symlink_to(root / "ordinary")
            with self.assertRaises(ValueError):
                safe_path(root, "link")


class FrozenDataTests(unittest.TestCase):
    def test_test_sources_are_disjoint_and_only_source_level_frozen(self):
        manifest = json.loads((OUTPUT / "manifest.json").read_text())
        freeze = json.loads((OUTPUT / "test_sources.lock.json").read_text())
        held_out = {row["source_id"] for row in freeze["sources"]}
        self.assertEqual(len(held_out), 50)
        self.assertTrue(all(source_split(row["upstream_task_id"]) == "test" for row in freeze["sources"]))
        self.assertFalse(held_out & (set(manifest["sources"]["train"]) | set(manifest["sources"]["dev"])))
        self.assertFalse(freeze["references_executed"])
        self.assertFalse(freeze["contract_review_complete"])
        self.assertFalse(freeze["test_tasks_generated"])

    def test_resource_tamper_is_rejected_before_execution(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "data"
            shutil.copytree(OUTPUT, target)
            manifest = json.loads((target / "manifest.json").read_text())
            path = target / manifest["tasks"][0]["path"] / "starter/solution.py"
            path.write_text(path.read_text() + "\n# unintended edit\n")
            with self.assertRaisesRegex(ValueError, "resource changed"):
                verify_dataset(target)

    def test_rehashed_private_expectation_still_must_match_reviewed_contract(self):
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "data"
            shutil.copytree(OUTPUT, target)
            manifest_path = target / "manifest.json"
            manifest = json.loads(manifest_path.read_text())
            relative = manifest["tasks"][0]["path"] + "/private_tests.json"
            path = target / relative
            cases = json.loads(path.read_text())
            cases[0]["expected"] = {"tampered": True}
            path.write_text(json.dumps(cases))
            manifest["files"][relative] = sha256(path.read_bytes())
            manifest_path.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError, "reviewed upstream"):
                verify_dataset(target)


if __name__ == "__main__":
    unittest.main()
