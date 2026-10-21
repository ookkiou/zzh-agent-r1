import json
import os
from pathlib import Path
import shutil
import tempfile
import unittest
from unittest.mock import patch

from code_repair.environment import RepairEnvironment
from code_repair.execution import DockerBackend, ExecutionOutcome, TrustedLocalBackend, check_cases
from code_repair.tasks import load_task

ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / "data/prototype/train/repair-001"


class EnvironmentTests(unittest.TestCase):
    def make_env(self, **kwargs):
        env = RepairEnvironment(load_task(TASK), backend=TrustedLocalBackend(), **kwargs)
        env.reset()
        self.addCleanup(env.close)
        return env

    def reference(self):
        return (TASK / "reference/solution.py").read_text()

    def test_three_tools_and_final_reward(self):
        env = self.make_env()
        read = env.step({"name": "read_file", "arguments": {"path": "solution.py"}})
        self.assertEqual(read.tool_response["output"], env.task.starter_source)
        failed = env.step({"name": "run_tests", "arguments": {}})
        self.assertTrue(failed.tool_response["ok"])
        self.assertGreater(failed.tool_response["output"]["failed"], 0)
        written = env.step({"name": "write_file", "arguments": {"path": "solution.py", "content": self.reference()}})
        self.assertTrue(written.tool_response["ok"])
        passed = env.step({"name": "run_tests", "arguments": {}})
        self.assertEqual(passed.tool_response["output"]["failed"], 0)
        self.assertEqual([read.reward, failed.reward, written.reward, passed.reward], [0.0] * 4)
        terminal = env.step({"final": "done"})
        self.assertTrue(terminal.done)
        self.assertEqual(terminal.reward, 1.0)
        self.assertEqual(env.step({"final": "again"}).reward, 0.0)

    def test_step_budget_finalizes_current_patch(self):
        env = self.make_env(max_steps=1)
        result = env.step({"name": "write_file", "arguments": {"path": "solution.py", "content": self.reference()}})
        self.assertTrue(result.done)
        self.assertEqual(result.reward, 1.0)
        self.assertEqual(result.info["termination_reason"], "step_limit")

    def test_original_code_and_public_example_memorization_score_zero(self):
        env = self.make_env()
        self.assertEqual(env.step({"final": "done"}).reward, 0.0)
        env.reset()
        env.step({"name": "write_file", "arguments": {
            "path": "solution.py", "content": "def count_at_least(values, threshold):\n    return 2 if values else 0\n"}})
        public = env.step({"name": "run_tests", "arguments": {}})
        self.assertEqual(public.tool_response["output"]["failed"], 0)
        self.assertEqual(env.step({"final": "done"}).reward, 0.0)

    def test_rejected_writes_do_not_change_source_or_public_tests(self):
        env = self.make_env(max_steps=20)
        for name, args in (
            ("write_file", {"path": "public_tests.py", "content": "pass"}),
            ("write_file", {"path": "../solution.py", "content": "pass"}),
            ("write_file", {"path": "solution.py", "content": "def count_at_least(x):\n    return 1\n"}),
            ("write_file", {"path": "solution.py", "content": "def count_at_least(values, threshold):\n    return (\n"}),
            ("read_file", {"path": "private_tests.json"}),
            ("run_tests", {"command": "anything"}),
        ):
            with self.subTest(args=args):
                self.assertFalse(env.step({"name": name, "arguments": args}).tool_response["ok"])
                self.assertEqual((env.workspace / "solution.py").read_text(), env.task.starter_source)
                self.assertEqual((env.workspace / "public_tests.py").read_text(), env.task.public_test_source)

    def test_workspaces_do_not_share_edits_and_reset_restores_starter(self):
        first, second = self.make_env(), self.make_env()
        self.assertNotEqual(first.workspace, second.workspace)
        first.step({"name": "write_file", "arguments": {"path": "solution.py", "content": self.reference()}})
        self.assertEqual((second.workspace / "solution.py").read_text(), second.task.starter_source)
        old = first.workspace
        first.reset()
        self.assertFalse(old.exists())
        self.assertEqual((first.workspace / "solution.py").read_text(), first.task.starter_source)

    def test_private_material_never_enters_workspace_or_messages(self):
        env = self.make_env()
        self.assertEqual({item.name for item in env.workspace.iterdir()}, {"solution.py", "public_tests.py"})
        env.step({"final": "done"})
        observed = json.dumps(env.observation(), ensure_ascii=False)
        self.assertNotIn("private-01", observed)
        self.assertNotIn("reference/", observed)
        self.assertNotIn("private_tests", observed)

    def test_episode_timeout_prevents_late_patch(self):
        now = [0.0]
        env = self.make_env(clock=lambda: now[0], episode_timeout=1)
        now[0] = 2.0
        result = env.step({"name": "write_file", "arguments": {"path": "solution.py", "content": self.reference()}})
        self.assertTrue(result.done)
        self.assertEqual(result.reward, 0.0)
        self.assertEqual(result.info["termination_reason"], "episode_timeout")
        self.assertEqual((env.workspace / "solution.py").read_text(), env.task.starter_source)

    def test_backend_failure_marks_episode_invalid(self):
        env = self.make_env()
        with patch.object(env.backend, "execute", return_value=ExecutionOutcome("infrastructure_error")):
            result = env.step({"name": "run_tests", "arguments": {}})
        self.assertTrue(result.done)
        self.assertFalse(result.info["valid_episode"])
        self.assertEqual(result.reward, 0.0)

    def test_symlink_is_rejected_without_reading_target(self):
        env = self.make_env()
        source = env.workspace / "solution.py"
        source.unlink()
        source.symlink_to(TASK / "reference/solution.py")
        result = env.step({"name": "read_file", "arguments": {"path": "solution.py"}})
        self.assertFalse(result.tool_response["ok"])

    def test_context_manager_cleans_up_even_on_exception(self):
        env = RepairEnvironment(load_task(TASK), backend=TrustedLocalBackend())
        with self.assertRaisesRegex(RuntimeError, "intentional"):
            with env:
                workspace = env.workspace
                raise RuntimeError("intentional")
        self.assertFalse(workspace.exists())


class ExecutionTests(unittest.TestCase):
    def test_tuple_cannot_be_normalized_into_a_passing_list(self):
        result = check_cases(TrustedLocalBackend(), "def f(): return (1, 2)", "f",
                             [{"id": "list", "args": [], "expected": [1, 2]}])
        self.assertEqual(result["failed"], 1)
        self.assertEqual(result["failures"][0]["reason"], "TypeError")

    def test_infinite_loop_is_bounded(self):
        result = TrustedLocalBackend().execute("def f():\n    while True: pass\n", "f", [[]], timeout=0.2)
        self.assertEqual(result.status, "timeout")

    def test_native_output_flood_is_bounded(self):
        result = TrustedLocalBackend().execute(
            "import os\ndef f():\n    while True: os.write(1, b'x' * 4096)\n", "f", [[]], timeout=2)
        self.assertEqual(result.status, "output_limit")

    def test_worker_inputs_do_not_include_expected_results(self):
        source = "def f(x):\n    return x + 1\n"
        with patch("code_repair.execution.run_bounded") as run:
            run.return_value = ("completed", b'{"rows":[{"kind":"return","value":2}]}', "", 0, 0.1)
            result = check_cases(TrustedLocalBackend(), source, "f", [{"id": "secret", "args": [1], "expected": 2}])
        payload = json.loads(run.call_args.args[1])
        self.assertEqual(set(payload), {"source", "entrypoint", "inputs"})
        self.assertEqual(result["passed"], 1)

    def test_docker_requires_immutable_image_and_does_not_mount_host(self):
        with self.assertRaises(ValueError):
            DockerBackend("python:3.12-slim")
        command = DockerBackend("python@sha256:" + "a" * 64).command("test-container")
        for flag in ("--network=none", "--read-only", "--user=65534:65534", "--cap-drop=ALL", "--pull=never"):
            self.assertIn(flag, command)
        self.assertNotIn("--volume", command)
        self.assertNotIn("--mount", command)

    def test_missing_docker_is_an_infrastructure_failure(self):
        with patch("code_repair.execution.shutil.which", return_value=None):
            result = DockerBackend("python@sha256:" + "a" * 64).execute("def f(): return 1", "f", [[]])
        self.assertEqual(result.status, "infrastructure_error")

    @unittest.skipUnless(shutil.which("docker") and os.environ.get("CODE_REPAIR_DOCKER_IMAGE"),
                         "Docker and an explicit digest-pinned image are required")
    def test_real_container_execution(self):
        backend = DockerBackend(os.environ["CODE_REPAIR_DOCKER_IMAGE"])
        result = backend.execute("def f(x): return x + 1", "f", [[1]], timeout=10)
        self.assertEqual(result.status, "completed")
        self.assertEqual(result.rows[0]["value"], 2)


if __name__ == "__main__":
    unittest.main()
