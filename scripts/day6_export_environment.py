"""Record the actual Linux venv, including inherited base packages, after pip check."""

import hashlib
import importlib.metadata
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    check = subprocess.run([sys.executable, '-m', 'pip', 'check'], capture_output=True, text=True, timeout=60)
    if check.returncode:
        raise SystemExit(check.stdout + check.stderr)
    freeze = subprocess.run([sys.executable, '-m', 'pip', 'freeze', '--all'],
                            capture_output=True, text=True, check=True, timeout=60).stdout
    path = ROOT / 'training/day6/requirements.linux.lock.txt'
    path.write_text('# AutoDL Linux Python 3.12; includes inherited torch/CUDA base packages.\n'
                    '# Inventory snapshot; editable verl path is host-specific.\n' + freeze)
    report = {'complete': True, 'day6_complete': False, 'python': sys.version,
        'pip_check': check.stdout.strip(), 'freeze_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        'packages': {name: importlib.metadata.version(name)
                     for name in sorted({d.metadata['Name'] for d in importlib.metadata.distributions()})},
        'scripts_sha256': {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
                            for p in sorted((ROOT / 'scripts').glob('day6_*.py'))}}
    (ROOT / 'reports/day6_environment.lock.json').write_text(json.dumps(report, indent=2, sort_keys=True) + '\n')
    print('Installed environment recorded; pip check passed')


if __name__ == '__main__':
    main()
