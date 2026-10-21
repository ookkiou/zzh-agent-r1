import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from scripts import day9_collect_evidence as collector


class NativeEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.temporary=tempfile.TemporaryDirectory();self.root=Path(self.temporary.name).resolve()
        (self.root/'reports').mkdir();(self.root/'runs/day9').mkdir(parents=True)
        (self.root/'runs/day9/input_identity.json').write_text('{}')
        (self.root/'reports/day7_sft_checkpoint_manifest.json').write_text('{}')
        self.fp=hashlib.sha256(b'{}\n{}').hexdigest()
        self.ray=self.root/'ray';self.logs=self.ray/'session_2026-10-15_test/logs';self.logs.mkdir(parents=True)
        self.forwarded=self.root/'forwarded.log'
        self.forwarded.write_text('(TaskRunner pid=123)\n(WorkerDict pid=124)\n')
        self.native=self.logs/'worker-test-01000000-123.out'
        (self.logs/'worker-test-01000000-124.err').write_text('Loaded model from global_step_10\nLoaded lr_scheduler from state\n')
        self.original_glob=Path.glob
        def mapped_glob(path,pattern):
            return self.original_glob(self.ray if path==Path('/tmp/ray') else path,pattern)
        self.root_patch=patch.object(collector,'ROOT',self.root);self.root_patch.start()
        self.glob_patch=patch.object(Path,'glob',mapped_glob);self.glob_patch.start()

    def tearDown(self):
        self.glob_patch.stop();self.root_patch.stop();self.temporary.cleanup()

    def status(self,phase,steps,code=0):
        record={'returncode':code,'run_fingerprint':self.fp,'log':str(self.forwarded),'attempt':'test-attempt'}
        (self.root/'reports'/('day9_'+phase+'_execute_status.json')).write_text(json.dumps(record))
        self.native.write_text(str(self.root)+'\n'+'\n'.join('training/global_step:'+str(s) for s in steps))

    def test_missing_forwarded_tail_is_recovered_from_unmodified_native_files(self):
        self.status('reload_probe',[11]);report=collector.collect('reload_probe')
        self.assertTrue(report['phase_completed']);self.assertEqual(report['missing_from_forwarded_console'],[11])
        self.assertEqual(report['attempt'],'test-attempt')
        for source in report['sources']:
            self.assertEqual((self.root/source['copy']).read_bytes(),Path(source['remote_source']).read_bytes())

    def test_wrong_or_ambiguous_native_evidence_is_rejected(self):
        self.status('reload_probe',[12])
        with self.assertRaises(ValueError):collector.collect('reload_probe')
        self.status('reload_probe',[11]);self.forwarded.write_text('(TaskRunner pid=123)\n(TaskRunner pid=999)')
        with self.assertRaises(ValueError):collector.collect('reload_probe')

    def test_partial_formal_evidence_requires_explicit_matching_user_pause(self):
        self.status('formal',[12,13],code=-6)
        with self.assertRaises(ValueError):collector.collect('formal')
        with self.assertRaises(ValueError):collector.collect('formal',True)
        (self.root/'reports/day9_pause_status.json').write_text(json.dumps({'user_requested_pause':True,'run_fingerprint':self.fp}))
        report=collector.collect('formal',True)
        self.assertFalse(report['phase_completed']);self.assertTrue(report['user_requested_pause'])
        self.assertEqual(report['actual_updates'],[12,13])
        self.status('formal',[12,14],code=-6)
        with self.assertRaises(ValueError):collector.collect('formal',True)


if __name__=='__main__':unittest.main()
