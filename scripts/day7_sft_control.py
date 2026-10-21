"""Launch bounded SFT fallback and paired diagnostics, retaining the original baseline."""
import argparse
import json
import os
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('warmup', 'diagnostics', 'status'))
    args = parser.parse_args()
    if args.action == 'status':
        for stem in ('day7_sft_warmup', 'day7_sft_diagnostics'):
            path = ROOT / 'reports' / (stem + '.json')
            if path.exists():
                report = json.loads(path.read_text())
                print(stem, json.dumps({k: report[k] for k in ('complete', 'failure', 'train', 'dev') if k in report}))
                if 'updates' in report:
                    print('updates', len(report['updates']), 'last', report['updates'][-1:] )
            log = ROOT / 'reports' / (stem + '.log')
            if log.exists():
                print('\n'.join(log.read_text(errors='replace').splitlines()[-4:]))
        return
    python = ROOT / '.venv/bin/python'
    environment = os.environ.copy()
    environment.update({'PYTHONPATH': str(ROOT) + ':' + str(ROOT / 'runs/day6/Agent-R1'),
        'PATH': str(python.parent) + ':/usr/local/cuda/bin:/root/miniconda3/bin:' + os.defpath,
        'CUDA_HOME': '/usr/local/cuda', 'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1',
        'OMP_NUM_THREADS': '4', 'TOKENIZERS_PARALLELISM': 'false',
        'CODE_REPAIR_PUBLIC_DATA_DIR': str(ROOT / 'runs/day7/public_data'),
        'CODE_REPAIR_TOKEN_FILE': str(ROOT / 'runs/day6/evaluator_token'),
        'CODE_REPAIR_EVALUATOR_URL': 'http://127.0.0.1:18765'})
    stem = 'day7_sft_warmup' if args.action == 'warmup' else 'day7_sft_diagnostics'
    for other in ('day7_sft_warmup', 'day7_sft_diagnostics'):
        pidfile = ROOT / 'reports' / (other + '_pid.json')
        if pidfile.exists():
            cmdline = Path('/proc') / str(json.loads(pidfile.read_text())['pid']) / 'cmdline'
            if cmdline.exists() and any(script in cmdline.read_bytes() for script in (b'day7_sft_warmup.py', b'day7_diagnose.py')):
                raise SystemExit('Another bounded Day7 GPU job is already running')
    script = 'day7_sft_warmup.py' if args.action == 'warmup' else 'day7_diagnose.py'
    arguments = [] if args.action == 'warmup' else ['--sft-only']
    with (ROOT / 'reports' / (stem + '.log')).open('ab') as stream:
        process = subprocess.Popen([str(python), str(ROOT / 'scripts' / script), *arguments],
            cwd=ROOT, env=environment, stdin=subprocess.DEVNULL, stdout=stream,
            stderr=subprocess.STDOUT, start_new_session=True)
    (ROOT / 'reports' / (stem + '_pid.json')).write_text(json.dumps({'pid': process.pid}) + '\n')
    print('Started bounded', stem, process.pid)


if __name__ == '__main__':
    main()
