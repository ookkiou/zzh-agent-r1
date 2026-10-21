"""Read current Day9 metrics and save a compact, explicitly partial training snapshot."""
from datetime import datetime,timezone
import json
from pathlib import Path
import re
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
from day9_train import fingerprint


def main():
    plan=json.loads((ROOT/'training/day9/run_plan.json').read_text());fp=fingerprint(ROOT)
    updates={};phases={}
    for phase in ('pilot','reload_probe','formal'):
        records=sorted((ROOT/'runs/day9/launch').glob(phase+'-execute-*.json'),key=lambda p:p.stat().st_mtime)
        record=None
        for path in records[-1:]:
            record=json.loads(path.read_text())
            if record['run_fingerprint']!=fp:continue
            log=ROOT/'reports'/('day9_'+phase+'_execute_'+record['attempt']+'.log')
            if log.exists():
                for line in log.read_text(errors='replace').splitlines():
                    match=re.search(r'training/global_step:(\d+)',line)
                    if match:
                        values={k:float(v) for k,v in re.findall(r'([\w/]+):(-?(?:\d+\.?\d*|\.\d+)(?:e[+-]?\d+)?)',line)}
                        updates[int(match[1])]={k:values[k] for k in ('actor/pg_loss','actor/kl_loss','actor/grad_norm','timing_s/step') if k in values}
            phases[phase]={'attempt':record['attempt'],'returncode':record.get('returncode'),'log':str(log)}
        evidence=ROOT/'reports'/('day9_'+phase+'_worker_evidence.json')
        if evidence.exists():
            info=json.loads(evidence.read_text())
            if info['complete'] and info['run_fingerprint']==fp and record and info.get('attempt',record['attempt'])==record['attempt']:
                for line in Path(info['evidence_log']).read_text(errors='replace').splitlines():
                    match=re.search(r'training/global_step:(\d+)',line)
                    if match:
                        values={k:float(v) for k,v in re.findall(r'([\w/]+):(-?(?:\d+\.?\d*|\.\d+)(?:e[+-]?\d+)?)',line)}
                        updates[int(match[1])]={k:values[k] for k in ('actor/pg_loss','actor/kl_loss','actor/grad_norm','timing_s/step') if k in values}
    checkpoint_root=Path(plan['checkpoint_root']);audit_file=checkpoint_root/'training_batch_audit.jsonl'
    audits=[json.loads(line) for line in audit_file.read_text().splitlines()] if audit_file.exists() else []
    consumed=[r for r in audits if r['global_step'] in updates]
    pipeline_path=ROOT/'reports/day9_pipeline_status.json'
    pipeline=json.loads(pipeline_path.read_text()) if pipeline_path.exists() else {}
    gpu=subprocess.run(['nvidia-smi','--query-gpu=memory.used,utilization.gpu','--format=csv,noheader'],capture_output=True,text=True)
    report={'recorded_at':datetime.now(timezone.utc).isoformat(),'run_fingerprint':fp,
        'complete':pipeline.get('formal_225_updates_complete',False),'pipeline_status':pipeline.get('status','not_started'),
        'completed_optimizer_updates':sorted(updates),'updates':updates,'target_total_updates':225,
        'audited_batches_before_optimizer':len(audits),'episodes_in_completed_updates':sum(r['trajectory_count'] for r in consumed),
        'mixed_reward_groups_in_completed_updates':sum(r['mixed_reward_groups'] for r in consumed),
        'train_successes_in_completed_updates':sum(t['reward'] for r in consumed for t in r['trajectories']),
        'train_metric_is_not_dev_or_test_result':True,'phases':phases,
        'gpu_snapshot':gpu.stdout.strip(),'checkpoint_root':str(checkpoint_root),
        'checkpoint_storage_available_gib':round(shutil.disk_usage(checkpoint_root).free/1024**3,2),
        'optimizer_state_saved':False,'weight_reload_verified':pipeline.get('weight_reload_verified',False),
        'optimizer_continuation_verified':False,'test_executed':False,'grpo_ability_improvement_proven':False}
    pause=ROOT/'reports/day9_pause_status.json'
    if pipeline.get('status')=='paused_by_user' and pause.exists():
        paused=json.loads(pause.read_text())
        report.update({'paused_by_user':True,'resume_checkpoint_step':paused['latest_complete_checkpoint'],
            'uncheckpointed_completed_updates':paused.get('uncheckpointed_completed_updates',[]),
            'next_update_on_resume':paused['latest_complete_checkpoint']+1})
    temporary=ROOT/'reports/day9_training_snapshot.tmp';temporary.write_text(json.dumps(report,indent=2)+'\n')
    temporary.replace(ROOT/'reports/day9_training_snapshot.json')
    print(json.dumps({k:v for k,v in report.items() if k not in ('updates','phases')},indent=2))


if __name__=='__main__':main()
