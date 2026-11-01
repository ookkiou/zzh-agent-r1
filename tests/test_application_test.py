"""Application test accounting: completeness, pairing, failures and frozen inputs."""
import copy
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import compare_application_test as comparison
import prepare_application_test as preparation


class ApplicationTestAccounting(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        protocol = Path(directory.name) / 'protocol.json'
        protocol.write_text('{}')
        patched = patch.object(comparison, 'PROTOCOL', protocol)
        patched.start()
        self.addCleanup(patched.stop)
        self.recipe = {'tasks': [{'task_id': 'a', 'source_id': 'source-a'},
            {'task_id': 'b', 'source_id': 'source-b'}], 'seeds': [17],
            'models': {s: {'sha256': s + '-hash', 'remote_path': '/' + s} for s in ('sft', 'step70')},
            'profile': 'code-repair-v1', 'backend': 'vllm-0.11-token-completions',
            'max_steps': 6, 'max_prompt_length': 4096, 'max_response_length': 512,
            'included_sources': 2, 'excluded_sources': 8, 'caveat': 'existing cohort, new backend'}
        self.reports = {}
        for stage, rewards in [('sft', [1, 1]), ('step70', [0, 1])]:
            episodes = []
            for row, reward in zip(self.recipe['tasks'], rewards):
                episodes.append({**row, 'seed': 17, 'reward': reward, 'split': 'test',
                    'profile': self.recipe['profile'], 'backend': self.recipe['backend'],
                    'model': 'zzh-repair-' + stage, 'final_test': True,
                    'decisions': 1, 'prompt_tokens': [10], 'response_tokens': [5],
                    'elapsed_seconds': 1.2,
                    'trace': [{'model_text': '{"final":"done"}', 'action': {'final': 'done'},
                               'parsed': True, 'contract_valid': True}],
                    'terminal': {'valid_episode': True, 'termination_reason': 'final',
                        'acceptance': {'status': 'completed', 'tests': 1, 'failed': 1 - reward}}})
            self.reports[stage] = {'complete': True, 'final_test': True, 'fresh_blind_test': False,
                'scripted_fixture': False, 'training_performed': False, 'expected_episodes': 2,
                'successes': sum(rewards), 'episodes': episodes, 'invalid_attempts': [],
                'inputs': {'protocol_sha256': comparison.digest(protocol), 'scope': 'test',
                    'stage': stage, 'model_sha256': stage + '-hash', 'model_path': '/' + stage,
                    'inference_url': 'http://127.0.0.1:18000', 'evaluator_url': 'http://127.0.0.1:8766',
                    'initial_prompts_sha256': 'same-prompts'}}

    def test_negative_result_and_seed_counts_are_preserved(self):
        result = comparison.summarize(self.recipe, self.reports)
        self.assertEqual(result['delta_percentage_points'], -50)
        self.assertEqual(result['paired_improved'], 0)
        self.assertEqual(result['paired_regressed'], 1)
        self.assertEqual(result['by_seed'], {'17': {'sft': 2, 'step70': 1}})
        self.assertFalse(result['fresh_blind_test'])

    def test_incomplete_cannot_be_reported_as_complete(self):
        self.reports['step70']['complete'] = False
        with self.assertRaisesRegex(ValueError, 'Incomplete'):
            comparison.summarize(self.recipe, self.reports)

    def test_partial_valid_report_can_resume(self):
        report = self.reports['step70']
        report['complete'] = False
        report['episodes'] = report['episodes'][:1]
        table = comparison.validate_report(report, self.recipe, 'step70', require_complete=False)
        self.assertEqual(set(table), {('a', 17)})  # A valid failure remains completed.

    def test_duplicate_cannot_fill_missing_coverage(self):
        self.reports['step70']['episodes'][1] = copy.deepcopy(self.reports['step70']['episodes'][0])
        with self.assertRaisesRegex(ValueError, 'Duplicate'):
            comparison.summarize(self.recipe, self.reports)

    def test_infrastructure_failure_is_not_counted(self):
        self.reports['step70']['episodes'][0]['terminal']['valid_episode'] = False
        with self.assertRaisesRegex(ValueError, 'Invalid episode'):
            comparison.summarize(self.recipe, self.reports)

    def test_forged_reward_is_rejected(self):
        self.reports['step70']['episodes'][0]['reward'] = 1
        with self.assertRaisesRegex(ValueError, 'Reward'):
            comparison.summarize(self.recipe, self.reports)

    def test_forged_action_record_is_rejected(self):
        self.reports['step70']['episodes'][0]['trace'][0]['action'] = {'final': 'changed'}
        with self.assertRaisesRegex(ValueError, 'Raw action'):
            comparison.summarize(self.recipe, self.reports)

    def test_changed_model_or_backend_is_rejected(self):
        self.reports['step70']['inputs']['model_sha256'] = 'wrong'
        with self.assertRaisesRegex(ValueError, 'identity'):
            comparison.summarize(self.recipe, self.reports)

    def test_changed_prompt_tokenization_between_models_is_rejected(self):
        self.reports['step70']['inputs']['initial_prompts_sha256'] = 'different'
        with self.assertRaisesRegex(ValueError, 'tokenizer differs'):
            comparison.summarize(self.recipe, self.reports)

    def test_invalid_attempt_is_separate_from_valid_episode_count(self):
        self.reports['step70']['invalid_attempts'].append({'task_id': 'a', 'seed': 17,
                                                         'error_type': 'ConnectionResetError'})
        result = comparison.summarize(self.recipe, self.reports)
        self.assertEqual(result['metrics']['step70']['invalid_attempts'], 1)
        self.assertEqual(result['episodes_per_model'], 2)
        self.assertEqual(result['step70_successes'], 1)


class ApplicationTestPreparation(unittest.TestCase):
    def test_existing_test_cohort_and_runtime_validate(self):
        recipe = preparation.build(preparation.DEFAULT_APP)
        self.assertEqual(recipe['episodes_per_model'], 126)
        self.assertEqual(len(recipe['tasks']), 42)
        self.assertEqual(recipe['seeds'], [17, 29, 43])
        self.assertFalse(recipe['fresh_blind_test'])

    def test_changed_runtime_is_rejected(self):
        recipe = preparation.build(preparation.DEFAULT_APP)
        recipe['core_files_sha256'] = {**recipe['core_files_sha256'],
                                      'code_repair/agent_session.py': 'wrong'}
        with self.assertRaisesRegex(ValueError, 'differs from frozen test'):
            preparation.validate_resources(recipe)


if __name__ == '__main__':
    unittest.main()
