"""Start/status the local Docker evaluator; keep its token outside model observations."""

import argparse
import json
import os
from pathlib import Path
import secrets
import signal
import socket
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from code_repair.evaluation import RemoteEvaluator


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('start', 'status', 'stop'))
    parser.add_argument('--dataset', type=Path, action='append', help='Explicit local train/dev dataset; default is prototype')
    args = parser.parse_args()
    directory = ROOT / 'runs/day6'
    token_path = directory / 'evaluator_token'
    if args.action == 'stop':
        pidfile = directory / 'evaluator_pid.json'
        if not pidfile.exists():
            raise SystemExit('No project evaluator PID record')
        pid = json.loads(pidfile.read_text())['pid']
        state = subprocess.run(['ps', '-p', str(pid), '-o', 'command='], capture_output=True, text=True)
        if state.returncode == 0:
            if str(ROOT / 'scripts/serve_evaluator.py') not in state.stdout:
                raise SystemExit('PID is not this project evaluator; refusing to stop')
            os.kill(pid, signal.SIGTERM)
        for _ in range(20):
            try:
                with socket.create_connection(('127.0.0.1', 8765), timeout=0.5):
                    time.sleep(0.2)
            except ConnectionRefusedError:
                print('Project evaluator stopped; port 8765 closed')
                return
        raise SystemExit('Evaluator port still open; inspect before further cleanup')
    if args.action == 'start':
        try:
            with socket.create_connection(('127.0.0.1', 8765), timeout=1):
                raise SystemExit('Port 8765 is occupied; inspect the existing listener first')
        except ConnectionRefusedError:
            pass
        if not token_path.exists():
            descriptor = os.open(token_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            with os.fdopen(descriptor, 'w') as stream:
                stream.write(secrets.token_urlsafe(48))
        environment = os.environ.copy()
        environment['CODE_REPAIR_SERVICE_TOKEN'] = token_path.read_text().strip()
        environment['PATH'] = '/Applications/Docker.app/Contents/Resources/bin:' + environment.get('PATH', os.defpath)
        image = json.loads((ROOT / 'SANDBOX_LOCK.json').read_text())['image']
        command = [sys.executable, str(ROOT / 'scripts/serve_evaluator.py'), '--image', image, '--port', '8765']
        for dataset in args.dataset or [ROOT / 'data/prototype']:
            command.extend(['--dataset', str(dataset.resolve())])
        with (directory / 'evaluator.log').open('ab') as output:
            process = subprocess.Popen(command, env=environment, cwd=ROOT,
                stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT, start_new_session=True)
        (directory / 'evaluator_pid.json').write_text(json.dumps({'pid': process.pid}) + '\n')
        for _ in range(20):
            if process.poll() is not None:
                raise SystemExit('Evaluator exited; inspect runs/day6/evaluator.log')
            try:
                health = RemoteEvaluator('http://127.0.0.1:8765', environment['CODE_REPAIR_SERVICE_TOKEN'], 'repair-001').health()
                print(json.dumps(health, indent=2))
                return
            except OSError:
                time.sleep(0.5)
        raise SystemExit('Evaluator readiness timed out')
    health = RemoteEvaluator('http://127.0.0.1:8765', token_path.read_text().strip(), 'repair-001').health()
    print(json.dumps(health, indent=2))


if __name__ == '__main__':
    main()
