import ast
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from code_repair.checkpoint_retention import (MARKER, REQUIRED, completed_checkpoints,
    ensure_run_root, mark_checkpoint_complete, prepare_checkpoint_save,storage_budget)
from code_repair.dataset import sha256
from code_repair.dataset_v2 import expanded_mutations
from scripts.day9_storage import cache_candidates
from scripts.day9_train import build_overrides,hydra_override
from scripts.verify_mbpp import validate_single_mutation
from scripts.verify_mbpp_v2 import OUTPUT, verify_dataset

ROOT=Path(__file__).resolve().parents[1]


class Day9DataTests(unittest.TestCase):
    def test_expanded_mutations_have_one_recorded_ast_change(self):
        reference=ast.unparse(ast.parse('def f(x, y):\n return x + 2 if x > 3 and y > 4 else y - 2'))+'\n'
        variants=expanded_mutations(reference)
        self.assertTrue({'arithmetic','boolean_logic','numeric_constant'}.issubset({v['bug_type'] for v in variants}))
        for variant in variants:
            validate_single_mutation(reference,variant['source'],variant['mutation'])
        one=next(v for v in variants if v['bug_type']=='boolean_logic')
        with self.assertRaises(ValueError):
            validate_single_mutation(reference,one['source'].replace('x + 2','x + 3'),one['mutation'])

    def test_frozen_source_and_dev_boundaries_and_duplicate_regression(self):
        report=verify_dataset(execute=False)
        self.assertTrue(report['static_validation_complete'])
        self.assertEqual(report['source_counts'],{'train':74,'dev':14})
        manifest=json.loads((OUTPUT/'manifest.json').read_text())
        self.assertNotIn('mbpp-644',manifest['sources']['train'])
        self.assertTrue(report['all_104_parent_tasks_unchanged'])

    def test_rehashed_new_private_label_must_still_match_reviewed_contract(self):
        with tempfile.TemporaryDirectory() as temporary:
            dataset=Path(temporary)/'dataset';shutil.copytree(OUTPUT,dataset)
            manifest=json.loads((dataset/'manifest.json').read_text())
            task=next(r for r in manifest['tasks'] if '-x' in r['task_id'])
            relative=task['path']+'/private_tests.json';path=dataset/relative
            cases=json.loads(path.read_text());cases[0]['expected']='tampered answer'
            path.write_text(json.dumps(cases));manifest['files'][relative]=sha256(path.read_bytes())
            (dataset/'manifest.json').write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError,'independently reviewed contract'):
                verify_dataset(dataset,execute=False)

    def test_public_export_contains_only_model_inputs(self):
        public=ROOT/'runs/day9/public_data';manifest=json.loads((public/'manifest.json').read_text())
        self.assertEqual(len(manifest['tasks']),332)
        for row in manifest['tasks']:
            metadata=json.loads((public/row['path']/'task.json').read_text())
            self.assertEqual(set(metadata),{'task_id','source_id','split','entrypoint','instruction'})
        self.assertFalse(any('private' in n or 'reference' in n for n in manifest['files']))
        self.assertEqual({str(p.relative_to(public)) for p in public.rglob('*') if p.is_file()},set(manifest['files'])|{'manifest.json'})


class Day9RecoveryTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory();self.root=Path(self.temporary.name)/'formal'
        ensure_run_root(self.root,'test-run')

    def tearDown(self):self.temporary.cleanup()

    def checkpoint(self,step,omit=None):
        directory=self.root/f'global_step_{step}'
        for name in REQUIRED:
            if name==omit:continue
            path=directory/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'fixture')
        return directory

    def test_rotation_preserves_latest_during_next_write(self):
        for step in (10,11):
            self.checkpoint(step);mark_checkpoint_complete(self.root,'test-run',step)
        self.assertEqual(prepare_checkpoint_save(self.root,'test-run',20),[10])
        self.assertTrue((self.root/'global_step_11'/MARKER).exists())
        self.checkpoint(20);mark_checkpoint_complete(self.root,'test-run',20)
        self.assertEqual([s for s,_,_ in completed_checkpoints(self.root,'test-run')],[11,20])

    def test_extra_required_and_optimizer_forbidden_for_lightweight_completion(self):
        directory=self.checkpoint(10,omit='actor/extra_state_world_size_1_rank_0.pt')
        with self.assertRaisesRegex(ValueError,'Missing lightweight'):
            mark_checkpoint_complete(self.root,'test-run',10)
        (directory/REQUIRED[-1]).write_bytes(b'fixture')
        (directory/'actor/optim_world_size_1_rank_0.pt').write_bytes(b'unwanted state')
        with self.assertRaisesRegex(ValueError,'Optimizer state forbidden'):
            mark_checkpoint_complete(self.root,'test-run',10)

    def test_incomplete_checkpoint_is_preserved_and_blocks_rotation(self):
        self.checkpoint(10)
        with self.assertRaisesRegex(ValueError,'Incomplete checkpoint'):
            prepare_checkpoint_save(self.root,'test-run',20)
        self.assertTrue((self.root/'global_step_10').exists())

    def test_foreign_identity_and_unowned_checkpoints_are_rejected(self):
        with self.assertRaises(ValueError):ensure_run_root(self.root,'foreign')
        other=self.root.parent/'unowned';(other/'global_step_10').mkdir(parents=True)
        with self.assertRaises(ValueError):ensure_run_root(other,'test-run')

    def test_changed_file_or_symlink_refuses_deletion(self):
        directory=self.checkpoint(10);mark_checkpoint_complete(self.root,'test-run',10)
        path=directory/REQUIRED[0];path.write_bytes(b'changed size')
        with self.assertRaises(ValueError):prepare_checkpoint_save(self.root,'test-run',20)
        path.unlink();path.symlink_to(directory/'actor/model_world_size_1_rank_0.pt')
        with self.assertRaises(ValueError):completed_checkpoints(self.root,'test-run')
        self.assertTrue(directory.exists())

    def test_overwrite_is_rejected(self):
        self.checkpoint(10);mark_checkpoint_complete(self.root,'test-run',10)
        with self.assertRaises(ValueError):prepare_checkpoint_save(self.root,'test-run',10)

    def test_existing_owned_weights_count_toward_storage_budget(self):
        empty=storage_budget(self.root,'test-run',22)
        self.checkpoint(10);mark_checkpoint_complete(self.root,'test-run',10)
        occupied=storage_budget(self.root,'test-run',22)
        self.assertEqual(occupied['required_budget_gib'],22)
        self.assertGreaterEqual(occupied['checkpoint_budget_gib'],occupied['available_gib'])
        self.assertFalse(storage_budget(self.root,'test-run',10**9)['storage_ready'])

    def test_lightweight_state_and_phase_totals_configured(self):
        values,_=build_overrides(ROOT,self.root,'pilot')
        self.assertEqual(values['trainer.total_training_steps'],10)
        self.assertEqual(values['actor_rollout_ref.actor.checkpoint.save_contents'],['model','extra'])
        self.assertEqual(values['actor_rollout_ref.actor.checkpoint.load_contents'],['model','extra'])
        self.assertIsNone(values['trainer.max_actor_ckpt_to_keep'])
        self.assertEqual(values['actor_rollout_ref.actor.optim.lr_scheduler_type'],'constant')
        self.assertIn('day7/sft_warmup/merged',values['actor_rollout_ref.model.path'])
        plan=json.loads((ROOT/'training/day9/run_plan.json').read_text())
        self.assertEqual(300//4*plan['epochs'],plan['phases']['formal']['total_updates'])
        with self.assertRaises(ValueError):build_overrides(ROOT,self.root,'reload_probe')


class Day9StorageTests(unittest.TestCase):
    def test_numeric_ray_environment_values_remain_quoted_strings(self):
        key='+ray_kwargs.ray_init.runtime_env.env_vars.CODE_REPAIR_ZERO_SIGNAL_LIMIT'
        self.assertEqual(hydra_override(key,'5'),key+'="5"')
        self.assertEqual(hydra_override('trainer.total_training_steps',10),'trainer.total_training_steps=10')

    def test_cleanup_allowlist_excludes_weights_and_symlinks(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary).resolve()
            for name in ('.tmp/cache.whl','.tmp/partial.whl.part','wheels/installed.whl','models/keep.whl','wheels/model.pt','wheels/state.json'):
                path=root/name;path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(b'fixture')
            (root/'wheels/link.whl').symlink_to(root/'models/keep.whl')
            self.assertEqual({str(p.relative_to(root)) for p in cache_candidates(root)},
                {'.tmp/cache.whl','.tmp/partial.whl.part','wheels/installed.whl'})
            shutil.rmtree(root/'.tmp');(root/'.tmp').symlink_to(root/'models')
            with self.assertRaises(ValueError):cache_candidates(root)


if __name__=='__main__':unittest.main()
