"""Result accounting must reject incomplete/duplicate runs and retain regressions."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'scripts'))
spec = importlib.util.spec_from_file_location('application_comparison',ROOT/'scripts/compare_zzhclaw_repair.py')
comparison = importlib.util.module_from_spec(spec)
spec.loader.exec_module(comparison)


class ApplicationComparisonTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        (self.root/'reports').mkdir()
        self.protocol = self.root/'protocol.json'
        self.recipe = {'tasks':[{'task_id':'dev-a'},{'task_id':'dev-b'}], 'seeds':[17],
            'model_sha256':{'sft':'sft-hash','step70':'candidate-hash'},
            'migration_caveat':'different backend; same application protocol'}
        self.protocol.write_text(json.dumps(self.recipe))
        self.inputs = {'protocol_sha256':comparison.digest(self.protocol),'scope':'dev'}
        for stage, values in [('sft',[1,1]),('step70',[0,1])]:
            self.save(stage,values)

    def save(self, stage, values, complete=True):
        data = {'complete':complete, 'inputs':{**self.inputs,'stage':stage,
            'model_sha256':self.recipe['model_sha256'][stage]},'invalid_attempts':[],
            'episodes':[{'task_id':task,'seed':17,'reward':reward,
                'terminal':{'valid_episode':True}} for task,reward in zip(['dev-a','dev-b'],values)]}
        path = self.root/'reports'/f'day13_{stage}_dev.json'
        path.write_text(json.dumps(data))
        return path

    def run_comparison(self):
        with patch.object(comparison,'ROOT',self.root), patch.object(comparison,'PROTOCOL',self.protocol), contextlib.redirect_stdout(io.StringIO()):
            comparison.main()
        return json.loads((self.root/'reports/day14_application_comparison.json').read_text())

    def test_negative_migration_result_is_preserved(self):
        report = self.run_comparison()
        self.assertEqual(report['delta_percentage_points'],-50)
        self.assertEqual(report['paired_improved'],0)
        self.assertEqual(report['paired_regressed'],1)
        self.assertFalse(report['final_test'])
        self.assertFalse(report['formal_225_updates_complete'])

    def test_incomplete_run_cannot_be_compared(self):
        self.save('step70',[1],complete=False)
        with self.assertRaisesRegex(ValueError,'Incomplete'):
            self.run_comparison()

    def test_duplicate_episode_cannot_count_toward_coverage(self):
        path = self.save('step70',[1,1])
        report = json.loads(path.read_text())
        report['episodes'][1] = report['episodes'][0]
        path.write_text(json.dumps(report))
        with self.assertRaisesRegex(ValueError,'Coverage'):
            self.run_comparison()

    def test_changed_recipe_is_rejected(self):
        self.protocol.write_text(self.protocol.read_text()+'\n')
        with self.assertRaisesRegex(ValueError,'changed'):
            self.run_comparison()


if __name__ == '__main__':
    unittest.main()
