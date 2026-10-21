from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import threading
import unittest
from unittest.mock import patch
import urllib.error
import urllib.request

from code_repair.environment import RepairEnvironment
from code_repair.evaluation import RemoteEvaluator
from code_repair.execution import TrustedLocalBackend
from code_repair.service import EvaluationServer, TaskRegistry
from code_repair.tasks import load_task

ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / 'data/prototype'
TASK = DATASET / 'train/repair-001'
TOKEN = 'test-fixture-token-only-' + 'a' * 32


class ServiceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Only reviewed repository fixtures use local execution in these protocol tests.
        cls.registry = TaskRegistry([DATASET])
        cls.server = EvaluationServer(('127.0.0.1', 0), cls.registry, TrustedLocalBackend(), TOKEN)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.url = f'http://127.0.0.1:{cls.server.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=5)

    def client(self, token=TOKEN):
        return RemoteEvaluator(self.url, token, 'repair-001')

    def test_health_requires_authentication(self):
        with self.assertRaises(urllib.error.HTTPError) as error:
            self.client('wrong-' + 'x' * 32).health()
        self.assertEqual(error.exception.code, 401)
        health = self.client().health()
        self.assertEqual(health['task_count'], 20)
        self.assertFalse(health['container_isolation_configured'])
        self.assertNotIn(TOKEN, json.dumps(health))

    def test_public_feedback_and_private_response_minimization(self):
        task = load_task(TASK)
        public = self.client().check(task.starter_source, 'public')
        self.assertGreater(public['failed'], 0)
        self.assertTrue(public['failures'])
        private = self.client().check(task.starter_source, 'private')
        self.assertGreater(private['failed'], 0)
        self.assertEqual(set(private), {'status', 'tests', 'passed', 'failed', 'timed_out', 'elapsed_seconds'})
        reference = (TASK / 'reference/solution.py').read_text()
        self.assertEqual(self.client().check(reference, 'private')['failed'], 0)

    def test_public_only_loader_never_reads_private_or_reference_files(self):
        original = Path.read_text
        def guarded(path, *args, **kwargs):
            if path.name == 'private_tests.json' or 'reference' in path.parts:
                raise AssertionError('Client read a private asset')
            return original(path, *args, **kwargs)
        with patch.object(Path, 'read_text', guarded):
            task = load_task(TASK, include_private=False)
        self.assertEqual(task.private_cases, ())
        with self.assertRaises(ValueError):
            RepairEnvironment(task, backend=TrustedLocalBackend())

    def test_registry_does_not_read_reference_code(self):
        original_bytes, original_text = Path.read_bytes, Path.read_text
        def guard(method):
            def read(path, *args, **kwargs):
                if 'reference' in path.parts:
                    raise AssertionError('Evaluator read reference implementation')
                return method(path, *args, **kwargs)
            return read
        with patch.object(Path, 'read_bytes', guard(original_bytes)), patch.object(Path, 'read_text', guard(original_text)):
            self.assertEqual(len(TaskRegistry([DATASET]).tasks), 20)

    def test_registry_rejects_modified_assets(self):
        original = Path.read_bytes
        def changed(path):
            data = original(path)
            return data + b' ' if path.name == 'private_tests.json' else data
        with patch.object(Path, 'read_bytes', changed):
            with self.assertRaisesRegex(ValueError, 'checksum'):
                TaskRegistry([DATASET])

    def test_rejects_command_paths_unknown_tasks_and_bad_signature(self):
        source = load_task(TASK).starter_source
        payload = {'task_id': 'repair-001', 'source': source, 'mode': 'public'}
        for extra, expected in (({'command': 'echo unsafe'}, 400), ({'task_id': '../other'}, 404),
                                ({'source': 'def wrong(): return 1'}, 422), ({'mode': 'shell'}, 400)):
            with self.subTest(extra=extra), self.assertRaises(urllib.error.HTTPError) as error:
                self.client().request('/v1/evaluate', {**payload, **extra})
            self.assertEqual(error.exception.code, expected)

    def test_oversized_body_is_rejected_before_execution(self):
        with self.assertRaises(urllib.error.HTTPError) as error:
            self.client().request('/v1/evaluate', {'task_id': 'repair-001', 'source': 'x' * 65536, 'mode': 'public'})
        self.assertEqual(error.exception.code, 413)

    def test_capacity_failure_is_invalid_not_candidate_failure(self):
        slots = []
        while self.server.slots.acquire(blocking=False):
            slots.append(True)
        try:
            task = load_task(TASK, include_private=False)
            with RepairEnvironment(task, evaluator=self.client()) as env:
                result = env.step({'name': 'run_tests', 'arguments': {}})
                self.assertTrue(result.done)
                self.assertFalse(result.info['valid_episode'])
                self.assertEqual(result.reward, 0)
        finally:
            for _ in slots:
                self.server.slots.release()

    def test_parallel_same_task_episodes_do_not_share_edits_or_reward(self):
        reference = (TASK / 'reference/solution.py').read_text()
        def episode(repair):
            task = load_task(TASK, include_private=False)
            with RepairEnvironment(task, evaluator=self.client()) as env:
                workspace = str(env.workspace)
                if repair:
                    env.step({'name': 'write_file', 'arguments': {'path': 'solution.py', 'content': reference}})
                result = env.step({'final': 'done'})
                self.assertTrue(result.info['valid_episode'])
                self.assertEqual(env.step({'final': 'again'}).reward, 0)
                observed = json.dumps([env.observation(), env.trace])
                self.assertNotIn(TOKEN, observed)
                self.assertNotIn('private-01', observed)
                self.assertNotIn('private_tests.json', observed)
            self.assertFalse(Path(workspace).exists())
            return workspace, result.reward
        with ThreadPoolExecutor(max_workers=2) as pool:
            first, second = list(pool.map(episode, (True, False)))
        self.assertNotEqual(first[0], second[0])
        self.assertEqual((first[1], second[1]), (1, 0))

    def test_client_transport_error_does_not_reward(self):
        client = self.client()
        with patch.object(client, 'request', side_effect=urllib.error.URLError('fixture disconnected')):
            with RepairEnvironment(load_task(TASK, include_private=False), evaluator=client) as env:
                result = env.step({'final': 'done'})
        self.assertFalse(result.info['valid_episode'])
        self.assertEqual(result.reward, 0)

    def test_client_rejects_malformed_counts_and_status(self):
        client = self.client()
        for result in ({'status': 'completed', 'tests': 0, 'passed': 0, 'failed': 0},
                       {'status': 'completed', 'tests': 1, 'passed': True, 'failed': 0},
                       {'status': 'completed', 'tests': 2, 'passed': 2, 'failed': 1},
                       {'status': 'unknown', 'tests': 1, 'passed': 1, 'failed': 0}):
            with self.subTest(result=result), patch.object(client, 'request', return_value=result):
                self.assertEqual(client.check('unused', 'private')['status'], 'infrastructure_error')

    def test_configuration_rejects_exposed_bind_and_insecure_remote_url(self):
        with self.assertRaises(ValueError):
            EvaluationServer(('0.0.0.0', 0), self.registry, TrustedLocalBackend(), TOKEN)
        with self.assertRaises(ValueError):
            RemoteEvaluator('http://example.com', TOKEN, 'repair-001')
        with self.assertRaises(ValueError):
            RemoteEvaluator(self.url, 'short', 'repair-001')


if __name__ == '__main__':
    unittest.main()
