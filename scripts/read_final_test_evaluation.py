"""Read the independent final-test evaluation without changing the remote process."""
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PROBE = r'''
from datetime import datetime, timezone
import hashlib, json, subprocess
from pathlib import Path
root=Path('/root/autodl-tmp/agent-r1-day6')
pidfile=root/'runs/final_test/evaluation.pid'
pid=int(pidfile.read_text().strip()) if pidfile.exists() else None
cmdfile=Path('/proc')/str(pid)/'cmdline'
cmd=cmdfile.read_bytes() if cmdfile.exists() else b''
running=b'evaluate_final_test.py' in cmd
receipt=root/'reports/final_test_eval_inputs.json'
identity=json.loads(receipt.read_text()) if receipt.exists() else None
protocol_path=root/'training/final_test/evaluation_protocol.json'
protocol=json.loads(protocol_path.read_text())
if hashlib.sha256(protocol_path.read_bytes()).hexdigest()!='4b5fde7d02ac238d26fc4ed4cebcbb4d882ddfc0e85a530ab333cadc311742eb':
    raise ValueError('Final-test protocol identity mismatch')
if identity and identity.get('protocol_sha256')!='4b5fde7d02ac238d26fc4ed4cebcbb4d882ddfc0e85a530ab333cadc311742eb':
    raise ValueError('Final-test input receipt identity mismatch')
expected={(r['task_id'],seed) for r in protocol['tasks'] for seed in protocol['seeds']}
stages={}
for stage in ('sft','step70'):
    path=root/'reports'/('final_test_eval_'+stage+'.json')
    if path.exists():
        d=json.loads(path.read_text())
        if identity is None or d.get('inputs')!=identity:
            raise ValueError('Evaluation input identity mismatch')
        rows=d['episodes']
        pairs={(r['task_id'],r['seed']) for r in rows}
        if len(pairs)!=len(rows) or not pairs.issubset(expected) or not all(r['valid_episode'] for r in rows):
            raise ValueError('Duplicate or invalid evaluated episodes')
        if d['complete'] and pairs!=expected:
            raise ValueError('Completed stage lacks full final-test coverage')
        stages[stage]={'completed':len(rows),'target':126,'complete':d['complete'],
            'successes_so_far':sum(r['reward']==1 for r in rows),
            'invalid_attempts':len(d['invalid_attempts']),
            'episode_seconds':sum(r['elapsed_seconds'] for r in rows)}
    else:
        stages[stage]={'completed':0,'target':126,'complete':False}
comparison_path=root/'reports/final_test_eval_comparison.json'
comparison=None
if comparison_path.exists():
    d=json.loads(comparison_path.read_text())
    if d.get('inputs')!=identity:
        raise ValueError('Comparison identity mismatch')
    comparison={k:d.get(k) for k in ('complete','sft_successes','step70_successes',
        'sft_success_rate','step70_success_rate','delta_percentage_points',
        'paired_improved_episodes','paired_regressed_episodes',
        'statistical_significance_evaluated','test_executed','formal_225_updates_complete','by_seed')}
log=root/'reports/final_test_eval.log'
tail=log.read_text(errors='replace').splitlines()[-8:] if log.exists() else []
gpu=subprocess.run(['nvidia-smi','--query-gpu=memory.used,memory.total,utilization.gpu',
    '--format=csv,noheader'],capture_output=True,text=True,timeout=10)
print(json.dumps({'observed_at':datetime.now(timezone.utc).isoformat(),'pid':pid,
    'running':running,'stages':stages,'comparison':comparison,'log_tail':tail,
    'gpu':gpu.stdout.strip(),'test_executed':any(r['completed']>0 for r in stages.values()),
    'final_test_complete':bool(comparison and comparison.get('complete')),
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
    target=ROOT/'reports/final_test_live_evaluation.json'
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
