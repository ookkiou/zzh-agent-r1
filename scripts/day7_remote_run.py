"""Bounded remote preflight and background diagnostics; never starts optimizer updates."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('preflight', 'start-diagnostics', 'status'))
    args = parser.parse_args()
    environment = os.environ.copy()
    python = ROOT / '.venv/bin/python'
    environment.update({'PYTHONPATH': str(ROOT) + ':' + str(ROOT / 'runs/day6/Agent-R1'),
        'PATH': str(python.parent) + ':/usr/local/cuda/bin:/root/miniconda3/bin:' + os.defpath,
        'CUDA_HOME': '/usr/local/cuda', 'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1',
        'OMP_NUM_THREADS': '4', 'TOKENIZERS_PARALLELISM': 'false',
        'CODE_REPAIR_PUBLIC_DATA_DIR': str(ROOT / 'runs/day7/public_data'),
        'CODE_REPAIR_TOKEN_FILE': str(ROOT / 'runs/day6/evaluator_token'),
        'CODE_REPAIR_EVALUATOR_URL': 'http://127.0.0.1:18765'})
    if args.action == 'preflight':
        overlay = json.loads((ROOT / 'runs/day7/overlay_manifest.json').read_text())
        for name, digest in overlay['files'].items():
            if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest:
                raise SystemExit('Uploaded overlay checksum mismatch: ' + name)
        commands = [('day6_preflight.py', ['--probe-training-stack', '--output', str(ROOT / 'reports/day7_host_preflight.json')], 900),
                    ('day7_prepare.py', ['--parquet-only'], 120), ('day7_trainer_probe.py', [], 180)]
        status = {'complete': False, 'training_performed': False, 'steps': []}
        for name, arguments, timeout in commands:
            try:
                result = subprocess.run([str(python), str(ROOT / 'scripts' / name), *arguments],
                    cwd=ROOT, env=environment, timeout=timeout)
                code = result.returncode
            except subprocess.TimeoutExpired:
                code = 124
            status['steps'].append({'name': name, 'returncode': code})
            status['complete'] = code == 0 and len(status['steps']) == len(commands)
            (ROOT / 'reports/day7_remote_preflight.json').write_text(json.dumps(status, indent=2) + '\n')
            if code:
                raise SystemExit(code)
        return
    log = ROOT / 'reports/day7_diagnostics.log'
    if args.action == 'status':
        for name in ('day7_remote_preflight.json', 'day7_model_diagnostics.json'):
            path = ROOT / 'reports' / name
            if path.exists():
                value = json.loads(path.read_text())
                print(name, json.dumps({k: value[k] for k in ('complete', 'failure', 'train', 'dev',
                    'learning_signal_present_in_train') if k in value}))
        if log.exists():
            print('\n'.join(log.read_text(errors='replace').splitlines()[-8:]))
        return
    readiness = ROOT / 'reports/day7_remote_preflight.json'
    if not readiness.exists() or not json.loads(readiness.read_text())['complete']:
        raise SystemExit('Successful remote preflight required before diagnostics')
    pidfile = ROOT / 'reports/day7_diagnostics_pid.json'
    if pidfile.exists():
        pid = json.loads(pidfile.read_text())['pid']
        cmdline = Path('/proc') / str(pid) / 'cmdline'
        if cmdline.exists() and b'day7_diagnose.py' in cmdline.read_bytes():
            raise SystemExit('Diagnostics are already running')
    with log.open('ab') as stream:
        process = subprocess.Popen([str(python), str(ROOT / 'scripts/day7_diagnose.py')], cwd=ROOT,
            env=environment, stdin=subprocess.DEVNULL, stdout=stream, stderr=subprocess.STDOUT,
            start_new_session=True)
    pidfile.write_text(json.dumps({'pid': process.pid}) + '\n')
    print('Bounded diagnostics started', process.pid)


if __name__ == '__main__':
    main()
