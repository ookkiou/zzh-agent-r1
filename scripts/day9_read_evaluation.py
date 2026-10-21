"""Read the current paired dev evaluation without changing the remote process."""
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PROBE = r'''
from datetime import datetime, timezone
import json, subprocess
from pathlib import Path
root=Path('/root/autodl-tmp/agent-r1-day6')
pidfile=root/'runs/day9/eval_step70.pid'
pid=int(pidfile.read_text().strip()) if pidfile.exists() else None
cmdfile=Path('/proc')/str(pid)/'cmdline'
cmd=cmdfile.read_bytes() if cmdfile.exists() else b''
running=b'day9_evaluate_step70.py' in cmd
receipt=root/'reports/day9_eval_step70_inputs.json'
identity=json.loads(receipt.read_text()) if receipt.exists() else None
stages={}
for stage in ('sft','step70'):
    path=root/'reports'/('day9_eval_step70_'+stage+'.json')
    if path.exists():
        d=json.loads(path.read_text())
        if identity is None or d.get('inputs')!=identity:
            raise ValueError('Evaluation input identity mismatch')
        rows=d['episodes']
        pairs={(r['task_id'],r['seed']) for r in rows}
        if len(pairs)!=len(rows) or not all(r['valid_episode'] for r in rows):
            raise ValueError('Duplicate or invalid evaluated episodes')
        stages[stage]={'completed':len(rows),'target':96,'complete':d['complete'],
            'successes_so_far':sum(r['reward']==1 for r in rows),
            'invalid_attempts':len(d['invalid_attempts']),
            'episode_seconds':sum(r['elapsed_seconds'] for r in rows)}
    else:
        stages[stage]={'completed':0,'target':96,'complete':False}
comparison_path=root/'reports/day9_eval_step70_comparison.json'
comparison=None
if comparison_path.exists():
    d=json.loads(comparison_path.read_text())
    if d.get('inputs')!=identity:
        raise ValueError('Comparison identity mismatch')
    comparison={k:d.get(k) for k in ('complete','sft_successes','step70_successes',
        'sft_success_rate','step70_success_rate','delta_percentage_points',
        'paired_improved_episodes','paired_regressed_episodes',
        'statistical_significance_evaluated','test_executed','formal_225_updates_complete')}
log=root/'reports/day9_eval_step70.log'
tail=log.read_text(errors='replace').splitlines()[-8:] if log.exists() else []
gpu=subprocess.run(['nvidia-smi','--query-gpu=memory.used,memory.total,utilization.gpu',
    '--format=csv,noheader'],capture_output=True,text=True,timeout=10)
print(json.dumps({'observed_at':datetime.now(timezone.utc).isoformat(),'pid':pid,
    'running':running,'stages':stages,'comparison':comparison,'log_tail':tail,
    'gpu':gpu.stdout.strip(),'test_executed':False,
    'formal_225_updates_complete':False},ensure_ascii=False))
'''


def main():
    command=['ssh','-i',str(ROOT/'runs/ssh/autodl_day6_ed25519'),'-p','37856',
        '-o','IdentitiesOnly=yes','-o','BatchMode=yes','-o','StrictHostKeyChecking=yes',
        '-o','ConnectTimeout=10','-o','ServerAliveInterval=10','-o','ServerAliveCountMax=2',
        'root@connect.westc.seetacloud.com',
        '/root/autodl-tmp/agent-r1-day6/.venv/bin/python -B -']
    result=subprocess.run(command,input=PROBE,text=True,capture_output=True,timeout=45)
    if result.returncode:
        print(json.dumps({'read_success':False,'ssh_returncode':result.returncode,
            'error':result.stderr[-1200:]},ensure_ascii=False))
        return 1
    report=json.loads(result.stdout)
    target=ROOT/'reports/day9_live_evaluation.json'
    if target.exists():
        previous=json.loads(target.read_text())
        report['previous_observation']={k:previous.get(k) for k in ('observed_at','pid','stages')}
    temporary=target.with_suffix('.tmp')
    temporary.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    temporary.replace(target)
    print(json.dumps(report,ensure_ascii=False,indent=2))
    return 0


if __name__=='__main__':
    sys.exit(main())
