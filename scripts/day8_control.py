"""Control this project's bounded Day8 GPU jobs."""
import argparse
import json
import os
from pathlib import Path
import subprocess

ROOT=Path(__file__).resolve().parents[1]
JOBS={'baseline':('day8_baseline.py',[]),'config':('day8_smoke.py',[]),
      'smoke':('day8_smoke.py',['--execute']),'checkpoint':('day8_checkpoint_verify.py',[])}


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action',choices=('start','status'))
    parser.add_argument('--job',choices=JOBS,default='baseline')
    args=parser.parse_args()
    if args.action=='status':
        for name in ('baseline_base','baseline_sft','smoke_status','checkpoint_verification'):
            path=ROOT/'reports'/('day8_'+name+'.json')
            if path.exists():
                report=json.loads(path.read_text())
                print(name,json.dumps({k:report[k] for k in ('complete','returncode','success_rate','valid_coverage','failure') if k in report}),
                    'episodes',len(report.get('episodes',[])))
        log=ROOT/'reports'/('day8_'+args.job+'.log')
        if log.exists():
            print('\n'.join(log.read_text(errors='replace').splitlines()[-5:])[-4000:])
        return
    for job,(script,_) in JOBS.items():
        pidfile=ROOT/'reports'/('day8_'+job+'_pid.json')
        if pidfile.exists():
            command=Path('/proc')/str(json.loads(pidfile.read_text())['pid'])/'cmdline'
            if command.exists() and script.encode() in command.read_bytes():
                raise SystemExit('A Day8 job is already running: '+job)
    python=ROOT/'.venv/bin/python'
    environment=os.environ.copy()
    environment.update({'PYTHONPATH':str(ROOT)+':'+str(ROOT/'runs/day6/Agent-R1'),
        'PATH':str(python.parent)+':/usr/local/cuda/bin:/root/miniconda3/bin:'+os.defpath,
        'CUDA_HOME':'/usr/local/cuda','HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1',
        'OMP_NUM_THREADS':'4','TOKENIZERS_PARALLELISM':'false',
        'CODE_REPAIR_PUBLIC_DATA_DIR':str(ROOT/'runs/day7/public_data'),
        'CODE_REPAIR_TOKEN_FILE':str(ROOT/'runs/day6/evaluator_token'),
        'CODE_REPAIR_EVALUATOR_URL':'http://127.0.0.1:18765',
        'CODE_REPAIR_TRACE_DIR':str(ROOT/'runs/day8/smoke_traces')})
    script,arguments=JOBS[args.job]
    with (ROOT/'reports'/('day8_'+args.job+'.log')).open('ab') as stream:
        process=subprocess.Popen([str(python),str(ROOT/'scripts'/script),*arguments],
            cwd=ROOT,env=environment,stdin=subprocess.DEVNULL,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
    (ROOT/'reports'/('day8_'+args.job+'_pid.json')).write_text(json.dumps({'pid':process.pid})+'\n')
    print('Started bounded Day8',args.job,process.pid)


if __name__=='__main__':
    main()
