"""Held-out boundary checks: explicit opt-in, checksums and public/private isolation."""
import hashlib
import json
from pathlib import Path
import shutil
import tempfile
import unittest

from code_repair.final_test import FinalTestRegistry, load_final_public_task
from code_repair.service import TaskRegistry

ROOT=Path(__file__).resolve().parents[1]
DATA=ROOT/'data/mbpp_repair/test-v0.1'
PUBLIC=ROOT/'runs/final_test/public_data'


class HeldOutBoundaries(unittest.TestCase):
    def setUp(self):
        self.manifest=json.loads((DATA/'manifest.json').read_text())
        self.digest=hashlib.sha256((DATA/'manifest.json').read_bytes()).hexdigest()
        self.ids=[r['task_id'] for r in self.manifest['tasks']]

    def test_default_registry_still_rejects_test(self):
        with self.assertRaises(ValueError):
            TaskRegistry([DATA])

    def test_test_registry_requires_exact_allowlist(self):
        with self.assertRaises(ValueError):
            FinalTestRegistry(DATA,self.digest,self.ids[:-1])
        registry=FinalTestRegistry(DATA,self.digest,self.ids)
        self.assertEqual(set(registry.tasks),set(self.ids))

    def test_public_loader_has_no_private_cases_and_checks_manifest(self):
        digest=hashlib.sha256((PUBLIC/'manifest.json').read_bytes()).hexdigest()
        task=load_final_public_task(PUBLIC,self.ids[0],digest)
        self.assertFalse(task.private_cases)
        with self.assertRaises(ValueError):
            load_final_public_task(PUBLIC,self.ids[0],'0'*64)

    def altered_export(self, private_declaration=False):
        temporary=tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root=Path(temporary.name)/'public'
        shutil.copytree(PUBLIC,root)
        manifest=json.loads((root/'manifest.json').read_text())
        row=manifest['tasks'][0]
        if private_declaration:
            manifest['files'][row['path']+'/private_tests.json']='0'*64
        else:
            path=root/row['path']/'task.json'
            value=json.loads(path.read_text());value['mutation']={'answer':'not public'}
            path.write_text(json.dumps(value))
            manifest['files'][row['path']+'/task.json']=hashlib.sha256(path.read_bytes()).hexdigest()
        content=json.dumps(manifest).encode()
        (root/'manifest.json').write_bytes(content)
        return root,row['task_id'],hashlib.sha256(content).hexdigest()

    def test_even_rehashed_private_metadata_is_rejected(self):
        root,task_id,digest=self.altered_export()
        with self.assertRaises(ValueError):
            load_final_public_task(root,task_id,digest)

    def test_even_rehashed_private_file_declaration_is_rejected(self):
        root,task_id,digest=self.altered_export(private_declaration=True)
        with self.assertRaises(ValueError):
            load_final_public_task(root,task_id,digest)


if __name__=='__main__':
    unittest.main()
