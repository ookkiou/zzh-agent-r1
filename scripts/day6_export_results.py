"""Export small diagnostics and configs; exclude weights, credentials and task resources."""

import hashlib
import json
from pathlib import Path
import tarfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    files = list((ROOT / 'reports').glob('day6_*.json')) + list((ROOT / 'reports').glob('day6_*.log'))
    files += [ROOT / 'training/day6/requirements.linux.lock.txt']
    for stage in ('single', 'tool'):
        directory = ROOT / 'runs/day6-smoke' / stage
        files += [directory / 'launch.json']
        files += list((directory / 'rollouts').glob('*.jsonl'))
    archive = ROOT / 'runs/day6/day6-results.tar.gz'
    files = [p for p in sorted(set(files)) if p.is_file() and not p.is_symlink()
             and p.name != 'day6_results_archive.json']
    with tarfile.open(archive, 'w:gz') as tar:
        for path in files:
            tar.add(path, arcname=str(path.relative_to(ROOT)), recursive=False)
    print(json.dumps({'path': str(archive), 'sha256': hashlib.sha256(archive.read_bytes()).hexdigest(),
                      'files': len(files), 'bytes': archive.stat().st_size,
                      'weights_and_credentials_included': False}))


if __name__ == '__main__':
    main()
