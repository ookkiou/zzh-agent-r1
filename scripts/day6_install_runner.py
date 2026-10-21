"""Run a logged dependency install in the dedicated remote venv; never start training."""

from datetime import datetime, timezone
import json
import os
import signal
import shutil
from pathlib import Path
import subprocess
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
REPORT = ROOT / 'reports/day6_install_status.json'


def main():
    python = ROOT / '.venv/bin/python'
    if Path(sys.prefix).resolve() != (ROOT / '.venv').resolve():
        raise SystemExit('Run with the project dedicated venv')
    environment = os.environ.copy()
    environment.update({'PATH': str(python.parent) + ':/usr/local/cuda/bin:/root/miniconda3/bin:' + os.defpath,
                        'CUDA_HOME': '/usr/local/cuda', 'PIP_CACHE_DIR': '/root/autodl-tmp/.cache/pip',
                        'TMPDIR': str(ROOT / '.tmp'), 'MAX_JOBS': '4'})
    Path(environment['TMPDIR']).mkdir(exist_ok=True)
    status = {'started_at': datetime.now(timezone.utc).isoformat(), 'steps': [], 'complete': False,
              'training_performed': False, 'runtime_compatibility_verified': False}
    commands = [
        ('resolve', [str(python), '-m', 'pip', 'install', '--dry-run', '--report',
                     str(ROOT / 'reports/day6_resolve.json'), '--find-links', str(ROOT / 'wheels'),
                     '-r', str(ROOT / 'training/day6/requirements.in')]),
        ('install', [str(python), '-m', 'pip', 'install', '--report', str(ROOT / 'reports/day6_install.json'),
                     '--find-links', str(ROOT / 'wheels'), '-r', str(ROOT / 'training/day6/requirements.in')]),
        ('verl', [str(python), '-m', 'pip', 'install', '--no-deps', '-e', str(ROOT / 'runs/day6/verl')]),
        ('pip_check', [str(python), '-m', 'pip', 'check']),
    ]
    for name, command in commands:
        status['current_step'] = name
        REPORT.write_text(json.dumps(status, indent=2) + '\n')
        print(f'=== {name}: {datetime.now(timezone.utc).isoformat()} ===', flush=True)
        try:
            result = subprocess.run(command, cwd=ROOT, env=environment, timeout=2400)
            code = result.returncode
        except subprocess.TimeoutExpired:
            status['steps'].append({'name': name, 'returncode': 124})
            status['failed_step'] = name
            status['timeout_cleanup'] = 'terminate this dedicated runner process group'
            REPORT.write_text(json.dumps(status, indent=2) + '\n')
            if os.getpgrp() == os.getpid():
                os.killpg(os.getpid(), signal.SIGTERM)
            return 124
        status['steps'].append({'name': name, 'returncode': code})
        if code:
            status['failed_step'] = name
            REPORT.write_text(json.dumps(status, indent=2) + '\n')
            return code
        if name == 'resolve':
            # pip dry-run downloads are otherwise discarded before actual installation.
            wheels = ROOT / 'wheels'
            wheels.mkdir(exist_ok=True)
            for wheel in (ROOT / '.tmp').rglob('*.whl'):
                destination = wheels / wheel.name
                if not destination.exists() and zipfile.is_zipfile(wheel):
                    shutil.copyfile(wheel, destination)
    status.update({'complete': True, 'finished_at': datetime.now(timezone.utc).isoformat()})
    REPORT.write_text(json.dumps(status, indent=2) + '\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
