"""Start this project's bounded-scope reverse SSH tunnel to the local evaluator."""

import json
import argparse
import os
from pathlib import Path
import subprocess
import signal
import time

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', nargs='?', choices=('start', 'stop'), default='start')
    args = parser.parse_args()
    pidfile = ROOT / 'runs/day6/tunnel_pid.json'
    if pidfile.exists():
        pid = json.loads(pidfile.read_text())['pid']
        state = subprocess.run(['ps', '-p', str(pid), '-o', 'command='], capture_output=True, text=True)
        if state.returncode == 0 and '127.0.0.1:18765:127.0.0.1:8765' in state.stdout:
            if args.action == 'stop':
                os.kill(pid, signal.SIGTERM)
                print('Project evaluator tunnel stopped', pid)
                return
            print('Project evaluator tunnel already running', pid)
            return
        if state.returncode == 0:
            raise SystemExit('Recorded PID is not the project tunnel; refusing to change it')
    if args.action == 'stop':
        print('Project evaluator tunnel already stopped')
        return
    command = ['ssh', '-i', str(ROOT / 'runs/ssh/autodl_day6_ed25519'), '-p', '37105',
        '-o', 'IdentitiesOnly=yes', '-o', 'BatchMode=yes', '-o', 'StrictHostKeyChecking=yes',
        '-o', 'ExitOnForwardFailure=yes', '-o', 'ServerAliveInterval=30', '-o', 'ServerAliveCountMax=3',
        '-N', '-T', '-R', '127.0.0.1:18765:127.0.0.1:8765', 'root@connect.westc.seetacloud.com']
    with (ROOT / 'runs/day6/tunnel.log').open('ab') as log:
        process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=log, stderr=log,
                                   start_new_session=True)
    time.sleep(2)
    if process.poll() is not None:
        raise SystemExit('Tunnel exited; inspect runs/day6/tunnel.log')
    pidfile.write_text(json.dumps({'pid': process.pid}) + '\n')
    print('Project evaluator tunnel started', process.pid)


if __name__ == '__main__':
    main()
