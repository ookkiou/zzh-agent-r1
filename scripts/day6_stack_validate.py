"""After a successful installation, validate kernels, imports, data and Hydra only."""

import json
import os
from pathlib import Path
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]


def main():
    report_path = ROOT / 'reports/day6_stack_validation_status.json'
    report = {'complete': False, 'training_performed': False, 'steps': []}
    def save():
        report_path.write_text(json.dumps(report, indent=2) + '\n')
    save()
    deadline = time.monotonic() + 1800
    while True:
        status = json.loads((ROOT / 'reports/day6_install_status.json').read_text())
        if status.get('failed_step'):
            raise SystemExit('Dependency installation failed; do not validate partially installed stack')
        if status.get('complete'):
            break
        if time.monotonic() > deadline:
            raise SystemExit('Installation still incomplete after bounded wait')
        time.sleep(10)
    environment = os.environ.copy()
    environment.update({'PATH': str(ROOT / '.venv/bin') + ':/usr/local/cuda/bin:/root/miniconda3/bin:' + os.defpath,
                        'CUDA_HOME': '/usr/local/cuda', 'OMP_NUM_THREADS': '4',
                        'TOKENIZERS_PARALLELISM': 'false'})
    stages = [('flash_attention', ['day6_install_flashattn.py'], 240),
              ('imports_and_cuda', ['day6_preflight.py', '--probe-training-stack'], 900),
              ('gsm8k_data', ['day6_prepare_gsm8k.py'], 120),
              ('single_hydra', ['day6_smoke.py'], 120)]
    for name, arguments, timeout in stages:
        report['current_step'] = name
        save()
        print('VALIDATE', name, flush=True)
        try:
            result = subprocess.run([sys.executable, str(ROOT / 'scripts' / arguments[0]), *arguments[1:]],
                        cwd=ROOT, env=environment, timeout=timeout)
            code = result.returncode
        except subprocess.TimeoutExpired:
            code = 124
        report['steps'].append({'name': name, 'returncode': code})
        if code:
            report['failed_step'] = name
            save()
            return code
    report['complete'] = True
    save()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
