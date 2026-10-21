"""Launch or inspect this project's bounded Day9 phase, independent of the SSH session."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from day9_train import fingerprint


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=('start','status'))
    p.add_argument('--phase',choices=('pilot','reload_probe','formal'),default='pilot')
    args=p.parse_args()
    if args.action=='status':
        for phase in ('pilot','reload_probe','formal'):
            path=ROOT/'reports'/('day9_'+phase+'_pid.json')
            if path.exists():
                info=json.loads(path.read_text());command=Path('/proc')/str(info['pid'])/'cmdline'
                print(phase,'running',command.exists() and b'day9_train.py' in command.read_bytes())
            status=ROOT/'reports'/('day9_'+phase+'_execute_status.json')
            if status.exists():
                report=json.loads(status.read_text())
                if report['run_fingerprint']==fingerprint(ROOT):
                    print(phase,'returncode',report['returncode'],'elapsed_seconds',round(report['elapsed_seconds'],2))
        pipeline=ROOT/'reports/day9_pipeline_status.json'
        if pipeline.exists():print('pipeline',json.loads(pipeline.read_text())['status'])
        return
    for path in (ROOT/'reports').glob('day9_*_pid.json'):
        info=json.loads(path.read_text());command=Path('/proc')/str(info['pid'])/'cmdline'
        if command.exists() and b'day9_train.py' in command.read_bytes():raise SystemExit('Another Day9 phase is active')
    python=ROOT/'.venv/bin/python';env=os.environ.copy()
    env['PYTHONPATH']=str(ROOT)+':'+str(ROOT/'runs/day6/Agent-R1')
    log=ROOT/'reports'/('day9_'+args.phase+'_controller.log')
    with log.open('ab') as stream:
        process=subprocess.Popen([str(python),str(ROOT/'scripts/day9_train.py'),'execute','--phase',args.phase],
            cwd=ROOT,env=env,stdin=subprocess.DEVNULL,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
    (ROOT/'reports'/('day9_'+args.phase+'_pid.json')).write_text(json.dumps({'pid':process.pid,'phase':args.phase})+'\n')
    print('Started bounded Day9',args.phase,process.pid)


if __name__=='__main__':main()
