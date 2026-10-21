"""Manage this project's separate Mac test evaluator on loopback port 8766."""
import argparse
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from code_repair.evaluation import RemoteEvaluator


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('start','status','stop'))
    args=parser.parse_args()
    directory=ROOT/'runs/final_test'
    pidfile=directory/'evaluator_pid.json'
    tokenfile=ROOT/'runs/day6/evaluator_token'
    protocol=json.loads((ROOT/'training/final_test/evaluation_protocol.json').read_text())
    if args.action=='stop':
        if not pidfile.exists():
            print('No final-test evaluator PID record');return
        pid=json.loads(pidfile.read_text())['pid']
        state=subprocess.run(['ps','-p',str(pid),'-o','command='],capture_output=True,text=True)
        if state.returncode==0:
            if str(ROOT/'scripts/serve_final_test.py') not in state.stdout:
                raise ValueError('PID is not this project test evaluator')
            os.kill(pid,signal.SIGTERM)
        for _ in range(30):
            try:
                with socket.create_connection(('127.0.0.1',8766),timeout=0.3):
                    time.sleep(0.2)
            except ConnectionRefusedError:
                print('Final-test evaluator stopped; port 8766 closed');return
        raise ValueError('Port still open; inspect before further cleanup')
    token=tokenfile.read_text().strip()
    client=RemoteEvaluator('http://127.0.0.1:8766',token,protocol['tasks'][0]['task_id'])
    def health():
        result=client.health()
        if result.get('backend')!='docker' or not result.get('container_isolation_configured') or result.get('task_count')!=len(protocol['tasks']) or protocol['dataset_manifest_sha256'] not in result.get('dataset_manifest_sha256',[]):
            raise ValueError('Unexpected test evaluator identity')
        return result
    if args.action=='status':
        print(json.dumps(health(),indent=2));return
    try:
        with socket.create_connection(('127.0.0.1',8766),timeout=1):
            raise ValueError('Port 8766 occupied; use status to inspect before starting')
    except ConnectionRefusedError:
        pass
    directory.mkdir(parents=True,exist_ok=True)
    environment=os.environ.copy()
    environment['CODE_REPAIR_SERVICE_TOKEN']=token
    with (directory/'evaluator.log').open('ab') as log:
        process=subprocess.Popen([sys.executable,str(ROOT/'scripts/serve_final_test.py')],
            env=environment,cwd=ROOT,stdin=subprocess.DEVNULL,stdout=log,stderr=log,
            start_new_session=True)
    pidfile.write_text(json.dumps({'pid':process.pid})+'\n')
    for _ in range(40):
        if process.poll() is not None:
            raise ValueError('Test evaluator exited; inspect runs/final_test/evaluator.log')
        try:
            result=health()
            print(json.dumps(result,indent=2));return
        except OSError:
            time.sleep(0.5)
    raise ValueError('Readiness timeout; inspect runs/final_test/evaluator.log')


if __name__=='__main__':
    main()
