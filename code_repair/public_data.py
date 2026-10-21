"""Load an allowlisted public-only task export; never read private cases or references."""

import hashlib
import json
from pathlib import Path

from .tasks import load_task


def load_public_task(root, task_id):
    root = Path(root).resolve()
    manifest = json.loads((root / 'manifest.json').read_text())
    matches = [row for row in manifest['tasks'] if row['task_id'] == task_id]
    if len(matches) != 1:
        raise ValueError('Task ID is not in public train/dev manifest')
    row = matches[0]
    directory = (root / row['path']).resolve()
    if row['split'] not in ('train', 'dev') or not directory.is_relative_to(root):
        raise ValueError('Invalid public task path or split')
    for name in ('task.json', 'starter/solution.py', 'public_tests.py'):
        path = directory / name
        relative = row['path'] + '/' + name
        if (path.is_symlink() or not path.resolve().is_relative_to(root)
                or hashlib.sha256(path.read_bytes()).hexdigest() != manifest['files'].get(relative)):
            raise ValueError('Public resource checksum or path mismatch')
    metadata = json.loads((directory / 'task.json').read_text())
    if any(metadata[key] != row[key] for key in ('task_id', 'source_id', 'split')):
        raise ValueError('Public task index mismatch')
    return load_task(directory, include_private=False)
