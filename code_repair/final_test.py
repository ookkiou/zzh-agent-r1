"""Explicit held-out loaders; existing train/dev loaders remain unchanged."""
import hashlib
import json
from pathlib import Path

from .tasks import load_task

PUBLIC_KEYS = {'task_id','source_id','split','entrypoint','instruction'}


def verified_asset(root, relative, hashes):
    root=Path(root).resolve()
    path=root/relative
    if path.is_symlink() or not path.resolve().is_relative_to(root) or not path.is_file():
        raise ValueError('Unsafe/missing test asset')
    if hashlib.sha256(path.read_bytes()).hexdigest()!=hashes.get(relative):
        raise ValueError('Test asset checksum mismatch')
    return path


class FinalTestRegistry:
    """An explicit test-only registry whose caller supplies the frozen task allowlist."""
    def __init__(self, dataset, manifest_sha256, task_ids):
        root=Path(dataset).resolve()
        content=(root/'manifest.json').read_bytes()
        if hashlib.sha256(content).hexdigest()!=manifest_sha256:
            raise ValueError('Held-out manifest identity changed')
        manifest=json.loads(content)
        rows=manifest['tasks']
        if not task_ids or len(set(task_ids))!=len(task_ids) or len(rows)!=len(task_ids) or {r['task_id'] for r in rows}!=set(task_ids):
            raise ValueError('Held-out task allowlist mismatch')
        self.tasks={}
        self.manifest_hashes=[manifest_sha256]
        for row in rows:
            if row['split']!='test' or row['path']!='test/'+row['task_id']:
                raise ValueError('Test-only registry rejects other splits')
            for name in ('task.json','starter/solution.py','public_tests.py','private_tests.json'):
                verified_asset(root,row['path']+'/'+name,manifest['files'])
            metadata=json.loads((root/row['path']/'task.json').read_text())
            if any(metadata[k]!=row[k] for k in ('task_id','source_id','split')):
                raise ValueError('Test metadata/index mismatch')
            self.tasks[row['task_id']]=load_task(root/row['path'])


def load_final_public_task(root, task_id, manifest_sha256):
    root=Path(root).resolve()
    content=(root/'manifest.json').read_bytes()
    if hashlib.sha256(content).hexdigest()!=manifest_sha256:
        raise ValueError('Public test manifest changed')
    manifest=json.loads(content)
    matches=[r for r in manifest['tasks'] if r['task_id']==task_id]
    if len(matches)!=1:
        raise ValueError('Task not in held-out allowlist')
    row=matches[0]
    if row['split']!='test' or row['path']!='test/'+task_id:
        raise ValueError('Invalid held-out public task path')
    expected={r['path']+'/'+name for r in manifest['tasks']
        for name in ('task.json','starter/solution.py','public_tests.py')}
    if set(manifest['files'])!=expected:
        raise ValueError('Private or unexpected resource declared in public test export')
    for name in ('task.json','starter/solution.py','public_tests.py'):
        verified_asset(root,row['path']+'/'+name,manifest['files'])
    metadata=json.loads((root/row['path']/'task.json').read_text())
    if set(metadata)!=PUBLIC_KEYS or any(metadata[k]!=row[k] for k in ('task_id','source_id','split')):
        raise ValueError('Unexpected held-out public metadata')
    return load_task(root/row['path'],include_private=False)
