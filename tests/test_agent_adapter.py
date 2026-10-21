import asyncio
import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import threading
import unittest
from unittest.mock import patch

from code_repair.agent_protocol import initial_messages, parse_action, parse_env_kwargs
from code_repair.agent_session import GeneratedTokens, InfrastructureUnavailable, RepairSession, run_trajectory
from code_repair.evaluation import LocalEvaluator
from code_repair.execution import TrustedLocalBackend
from code_repair.public_data import load_public_task
from code_repair.service import EvaluationServer, TaskRegistry
from code_repair.tasks import load_task

ROOT = Path(__file__).resolve().parents[1]
TASK = ROOT / 'data/prototype/train/repair-001'


class ProtocolTests(unittest.TestCase):
    def test_supported_complete_wrappers_and_final(self):
        text = '{"name":"run_tests","arguments":{}}'
        for wrapped in (text, '<tool_call>' + text + '</tool_call>', '```json\n' + text + '\n```<|im_end|>'):
            self.assertEqual(parse_action(wrapped), {'name': 'run_tests', 'arguments': {}})
        self.assertEqual(parse_action('{"final":"done"}'), {'final': 'done'})

    def test_rejects_forgery_ambiguous_json_and_prose(self):
        for text in ('{"ok":true,"output":"passed"}',
                '{"name":"run_tests","name":"write_file","arguments":{}}',
                '{"name":"write_file","arguments":{"content":NaN}}',
                'prefix {"final":"done"}', '```python\npass\n```',
                '<tool_call>{"final":"done"}</tool_call><tool_call>{"final":"done"}</tool_call>',
                'All tests passed.', '[{"final":"done"}]'):
            with self.subTest(text=text), self.assertRaises(ValueError):
                parse_action(text)

    def test_row_cannot_override_control_plane_or_budget(self):
        self.assertEqual(parse_env_kwargs('{"task_id":"repair-001"}'), {'task_id': 'repair-001'})
        for value in ({'task_id': 'a', 'token': 'x'}, {'task_id': 'a', 'max_steps': 99},
                      {'task_id': 'a', 'evaluator_url': 'http://attacker'}, {'task_id': 1}):
            with self.assertRaises(ValueError):
                parse_env_kwargs(value)


class SessionTests(unittest.TestCase):
    def session(self, **kwargs):
        task = load_task(TASK)
        value = RepairSession(task, LocalEvaluator(task, TrustedLocalBackend()), **kwargs)
        self.addCleanup(value.close)
        return value

    def test_raw_generation_preserved_and_private_material_absent(self):
        session = self.session()
        session.reset()
        text = '```json\n{"name":"read_file","arguments":{"path":"solution.py"}}\n```<|im_end|>'
        session.step(text)
        self.assertEqual(session.messages[-2], {'role': 'assistant', 'content': text[:-len('<|im_end|>')]})
        self.assertEqual(session.trace[-1]['model_text'], text)
        self.assertIn('<tool_response>', session.messages[-1]['content'])
        observed = json.dumps(session.observation())
        self.assertNotIn('private-01', observed)
        self.assertNotIn('reference/', observed)

    def test_invalid_generation_costs_step_and_does_not_finish_early(self):
        session = self.session()
        session.reset()
        result = session.step('{"ok":true,"output":"All tests passed"}')
        self.assertFalse(result.done)
        self.assertFalse(session.trace[-1]['parsed'])
        self.assertEqual(result.info['step_index'], 1)
        self.assertEqual((session.environment.workspace / 'solution.py').read_text(), session.task.starter_source)

    def test_known_fixture_patch_reward_and_final_are_once_only(self):
        session = self.session()
        session.reset()
        source = (TASK / 'reference/solution.py').read_text()  # authored fixture only, never a model-generated candidate
        session.step(json.dumps({'name': 'write_file', 'arguments': {'path': 'solution.py', 'content': source}}))
        result = session.step('{"final":"done"}')
        self.assertTrue(result.done)
        self.assertEqual(result.reward, 1)
        self.assertEqual(session.step('{"final":"again"}').reward, 0)

    def test_infrastructure_cannot_be_valid_zero_reward(self):
        session = self.session()
        session.reset()
        with patch.object(session.environment.evaluator, 'check', return_value={'status': 'infrastructure_error'}):
            with self.assertRaises(InfrastructureUnavailable):
                session.step('{"name":"run_tests","arguments":{}}')

    def test_runner_keeps_observation_tokens_in_next_prompt_and_cleans_workspace(self):
        session = self.session()
        responses = ['{"name":"read_file","arguments":{"path":"solution.py"}}', '{"final":"done"}']
        prompts = []
        async def encode(messages, tools):
            prompts.append(json.dumps(messages))
            return list(map(ord, prompts[-1]))
        async def generate(ids):
            return GeneratedTokens(list(map(ord, responses.pop(0))))
        steps, info, _ = asyncio.run(run_trajectory(session, encode, generate,
            lambda ids: ''.join(map(chr, ids)), max_prompt_length=50000, max_response_length=1000))
        self.assertEqual(len(steps), 2)
        self.assertIn('<tool_response>', prompts[1])
        self.assertTrue(all(s.response_mask == [1] * len(s.response_ids) for s in steps))
        self.assertTrue(all('<tool_response>' not in ''.join(map(chr, s.response_ids)) for s in steps))
        self.assertTrue(info['valid_episode'])
        self.assertTrue(session.environment.closed)
        self.assertFalse(session.environment.workspace.exists())

    def test_runner_failure_closes_workspace(self):
        session = self.session()
        async def encode(messages, tools):
            return [1]
        async def generate(ids):
            raise RuntimeError('generation failure')
        with self.assertRaisesRegex(RuntimeError, 'generation failure'):
            asyncio.run(run_trajectory(session, encode, generate, str,
                max_prompt_length=10, max_response_length=10))
        self.assertTrue(session.environment.closed)

    def test_empty_generation_does_not_become_trainable_row(self):
        session = self.session()
        async def encode(messages, tools):
            return [1]
        async def generate(ids):
            return GeneratedTokens([])
        with self.assertRaises(InfrastructureUnavailable):
            asyncio.run(run_trajectory(session, encode, generate, str,
                max_prompt_length=10, max_response_length=10))
        self.assertTrue(session.environment.closed)

    def test_context_limit_evaluates_patch_without_fabricating_response(self):
        session = self.session()
        count = [0]
        source = (TASK / 'reference/solution.py').read_text()
        response = json.dumps({'name': 'write_file', 'arguments': {'path': 'solution.py', 'content': source}})
        async def encode(messages, tools):
            count[0] += 1
            return [1] * (1 if count[0] == 1 else 100)
        async def generate(ids):
            return GeneratedTokens(list(map(ord, response)))
        steps, info, _ = asyncio.run(run_trajectory(session, encode, generate,
            lambda ids: ''.join(map(chr, ids)), max_prompt_length=10, max_response_length=1000))
        self.assertEqual(len(steps), 1)
        self.assertEqual(steps[0].reward, 1)
        self.assertEqual(info['termination_reason'], 'context_limit')
        self.assertEqual(len(session.trace), 1)


class PublicAndActualInterfaceTests(unittest.TestCase):
    def make_public(self, root):
        files = {}
        for name in ('task.json', 'starter/solution.py', 'public_tests.py'):
            path = root / 'train/repair-001' / name
            path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(TASK / name, path)
            files['train/repair-001/' + name] = hashlib.sha256(path.read_bytes()).hexdigest()
        manifest = {'tasks': [{'task_id': 'repair-001', 'source_id': 'authored-prototype-001',
                              'split': 'train', 'path': 'train/repair-001'}], 'files': files}
        (root / 'manifest.json').write_text(json.dumps(manifest))

    def test_public_export_has_no_private_cases_and_detects_tampering(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self.make_public(root)
            self.assertEqual(load_public_task(root, 'repair-001').private_cases, ())
            with self.assertRaises(ValueError):
                load_public_task(root, '../private')
            (root / 'train/repair-001/starter/solution.py').write_text('tampered')
            with self.assertRaises(ValueError):
                load_public_task(root, 'repair-001')

    def test_actual_pinned_agentenv_over_authenticated_http_fixture(self):
        sys.path.insert(0, str(ROOT / 'runs/day6/Agent-R1'))
        from agent_r1.env.base import AgentEnv, Action
        from code_repair.agent_r1_env import CodeRepairAgentEnv
        self.assertTrue(issubclass(CodeRepairAgentEnv, AgentEnv))
        token = 'fixture-control-credential-' * 3
        server = EvaluationServer(('127.0.0.1', 0), TaskRegistry([ROOT / 'data/prototype']),
                                  TrustedLocalBackend(), token)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            with tempfile.TemporaryDirectory() as directory:
                root = Path(directory)
                self.make_public(root)
                tokenfile = root / 'control-token'
                tokenfile.write_text(token)
                with patch.dict(os.environ, {'CODE_REPAIR_PUBLIC_DATA_DIR': str(root),
                    'CODE_REPAIR_TOKEN_FILE': str(tokenfile),
                    'CODE_REPAIR_EVALUATOR_URL': 'http://127.0.0.1:' + str(server.server_port)}):
                    env = AgentEnv.from_config('zzh_code_repair', task_id='repair-001')
                    try:
                        observation = env.reset(raw_prompt=[{'role': 'user', 'content': 'INJECTED_PRIVATE_TEXT'}])
                        self.assertNotIn('INJECTED_PRIVATE_TEXT', json.dumps(observation.messages))
                        self.assertNotIn(token, json.dumps(observation.messages))
                        source = (TASK / 'reference/solution.py').read_text()
                        action = Action(text=json.dumps({'name': 'write_file',
                            'arguments': {'path': 'solution.py', 'content': source}}))
                        asyncio.run(env.step(action))
                        observed, reward, done, info = asyncio.run(env.step(Action(text='{"final":"done"}')))
                        self.assertEqual(reward, 1)
                        self.assertTrue(done and info['valid_episode'])
                        self.assertTrue(env.session.environment.closed)
                        self.assertNotIn(token, json.dumps(observed.messages))
                        self.assertNotIn('private-01', json.dumps(observed.messages))
                    finally:
                        env.close()
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=3)


if __name__ == '__main__':
    unittest.main()
