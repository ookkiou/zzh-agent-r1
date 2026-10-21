"""Extract measured update metrics from the completed native trainer console log."""
import json
import math
from pathlib import Path
import re

ROOT=Path(__file__).resolve().parents[1]


def main():
    log=(ROOT/'reports/day8_smoke.log').read_text(errors='replace')
    log=re.sub(r'\x1b\[[0-9;]*m','',log)
    rows={}
    for line in log.splitlines():
        match=re.search(r'training/global_step:(\d+)',line)
        if match:
            values={key:float(value) for key,value in re.findall(r'([a-zA-Z_][a-zA-Z_0-9/.-]*):(-?\d+(?:\.\d+)?(?:[eE][+-]?\d+)?)',line)}
            rows[int(match.group(1))]=values
    if set(rows)!={1,2,3,4,5} or any(not math.isfinite(v) for row in rows.values() for v in row.values()):
        raise ValueError('Five finite native update rows required')
    durations=[rows[i]['timing_s/step'] for i in range(1,6)]
    audits=[json.loads(line) for line in (ROOT/'runs/day8/smoke/training_batch_audit.jsonl').read_text().splitlines()]
    success_rates={row['global_step']:sum(t['reward'] for t in row['trajectories'])/len(row['trajectories']) for row in audits}
    training_keys=('actor/pg_loss','actor/kl_loss','actor/grad_norm','critic/score/mean','critic/score/trajectory/mean',
        'timing_s/gen','timing_s/update_actor','timing_s/step',
        'memory/max_memory_allocated_gb','memory/max_memory_reserved_gb','memory/cpu_memory_used_gb')
    report={'complete':True,'algorithm':'GRPO, custom repair recipe, SFT initialization',
        'updates':{i:{k:v for k,v in row.items() if k in training_keys} for i,row in rows.items()},
        'audited_train_episode_success_rate_by_update':success_rates,
        'mixed_reward_groups_by_update':{row['global_step']:row['mixed_reward_groups'] for row in audits},
        'updates_without_relative_reward_signal':[row['global_step'] for row in audits if row['mixed_reward_groups']==0],
        'reward_metric_scope':'critic/score/mean is step-level; use audited episode rates or critic/score/trajectory/mean for whole episodes',
        'sum_update_seconds':sum(durations),'mean_seconds_per_update':sum(durations)/5,
        'mean_seconds_per_update_excluding_first':sum(durations[1:])/4,
        'first_update_seconds':durations[0],
        'timing_scope':'Native timing_s/step; excludes initialization, checkpoint export and baseline evaluation',
        'memory_scope':'Reported PyTorch worker counters; not whole-device NVML peak',
        'formal_training':False,'grpo_generalization_improvement_evaluated':False}
    (ROOT/'reports/day8_training_report.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
