"""Continue the already-started bounded pilot through verified weight reload and formal GRPO."""
from datetime import datetime,timezone
import argparse
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import time

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
sys.path.insert(0,str(ROOT/'scripts'))
from day9_train import fingerprint


def validate_updates(log,expected,require_gradient=True):
    rows={}
    for line in log.splitlines():
        match=re.search(r'training/global_step:(\d+)',line)
        if match:
            if int(match[1]) in rows:raise ValueError('Duplicate completed update in phase log')
            values={key:float(value) for key,value in re.findall(r'([\w/]+):(-?(?:\d+\.?\d*|\.\d+)(?:e[+-]?\d+)?)',line)}
            rows[int(match[1])]=values
    if set(rows)!=set(expected):raise ValueError('Completed optimizer update range differs from planned phase')
    for row in rows.values():
        if not all(key in row and math.isfinite(row[key]) for key in ('actor/pg_loss','actor/kl_loss','actor/grad_norm','timing_s/step')):
            raise ValueError('Missing/nonfinite actual training metrics')
    if require_gradient and not any(row['actor/grad_norm']>0 for row in rows.values()):raise ValueError('No nonzero gradient in phase')
    return rows


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--continue-after-reload',action='store_true');args=p.parse_args()
    plan=json.loads((ROOT/'training/day9/run_plan.json').read_text())
    run_fingerprint=fingerprint(ROOT);start=time.monotonic();python=str(ROOT/'.venv/bin/python')
    report_path=ROOT/'reports/day9_pipeline_status.json'
    report={'run_fingerprint':run_fingerprint,'status':'waiting_for_pilot','formal_225_updates_complete':False,
        'optimizer_state_saved':False,'optimizer_continuation_verified':False,
        'grpo_ability_improvement_proven':False,'test_executed':False}

    def record(status):
        report.update({'status':status,'recorded_at':datetime.now(timezone.utc).isoformat(),'elapsed_seconds':round(time.monotonic()-start,2)})
        temporary=report_path.with_suffix('.tmp');temporary.write_text(json.dumps(report,indent=2)+'\n');temporary.replace(report_path)

    def telemetry(phase):
        query=subprocess.run(['nvidia-smi','--query-gpu=memory.used,utilization.gpu','--format=csv,noheader,nounits'],capture_output=True,text=True)
        with (ROOT/'reports/day9_gpu_samples.jsonl').open('a') as stream:
            stream.write(json.dumps({'time':datetime.now(timezone.utc).isoformat(),'phase':phase,'nvml_used_mib_utilization_percent':query.stdout.strip()})+'\n')

    def wait_idle():
        for _ in range(36):
            result=subprocess.run(['nvidia-smi','--query-compute-apps=pid','--format=csv,noheader'],capture_output=True,text=True)
            if result.returncode==0 and not result.stdout.strip():return
            time.sleep(5)
        raise ValueError('GPU did not become idle; no unrelated process will be stopped')

    def run_phase(phase):
        wait_idle();record(phase)
        with (ROOT/'reports'/('day9_'+phase+'_controller.log')).open('ab') as stream:
            process=subprocess.Popen([python,str(ROOT/'scripts/day9_train.py'),'execute','--phase',phase],
                cwd=ROOT,stdin=subprocess.DEVNULL,stdout=stream,stderr=subprocess.STDOUT)
            (ROOT/'reports'/('day9_'+phase+'_pid.json')).write_text(json.dumps({'pid':process.pid,'phase':phase})+'\n')
            while process.poll() is None:
                telemetry(phase);record(phase);time.sleep(10)
        if process.returncode:raise ValueError(phase+' failed with exit '+str(process.returncode))
        status=json.loads((ROOT/'reports'/('day9_'+phase+'_execute_status.json')).read_text())
        if status['returncode']!=0 or status['run_fingerprint']!=run_fingerprint:raise ValueError('Phase identity/status mismatch')
        return status

    def evidence(phase):
        from day9_collect_evidence import collect
        result=collect(phase)
        return Path(result['evidence_log']).read_text(errors='replace')

    record('waiting_for_pilot')
    try:
        pilot_pid=json.loads((ROOT/'reports/day9_pilot_pid.json').read_text())['pid']
        while True:
            status_path=ROOT/'reports/day9_pilot_execute_status.json'
            if status_path.exists():
                status=json.loads(status_path.read_text())
                if status['run_fingerprint']==run_fingerprint:
                    if status['returncode']!=0:raise ValueError('Pilot failed; formal training was not started')
                    break
            command=Path('/proc')/str(pilot_pid)/'cmdline'
            if not command.exists() or b'day9_train.py' not in command.read_bytes():raise ValueError('Pilot exited without matching successful status')
            if time.monotonic()-start>plan['phases']['pilot']['max_wall_seconds']+90:raise TimeoutError('Pilot wait exceeded its bound')
            telemetry('pilot');record('waiting_for_pilot');time.sleep(10)
        rows=validate_updates(Path(status['log']).read_text(errors='replace'),range(1,11))
        audits=[json.loads(line) for line in (Path(plan['checkpoint_root'])/'training_batch_audit.jsonl').read_text().splitlines()]
        pilot_audits=[r for r in audits if r['global_step']<=10]
        if ([r['global_step'] for r in pilot_audits]!=list(range(1,11))
                or not all(r['trajectory_count']==16 and r['group_count']==4 for r in audits)
                or not sum(r['mixed_reward_groups'] for r in pilot_audits)):
            raise ValueError('Pilot actual trajectory batches/relative reward signal failed')
        mean=sum(r['timing_s/step'] for r in rows.values())/len(rows)
        report['pilot_mean_seconds_per_update']=round(mean,2)
        report['rough_remaining_update_hours_excluding_initialization_and_checkpoint_io']=round((225-11)*mean/3600,2)
        if not args.continue_after_reload:run_phase('reload_probe')
        validate_updates(evidence('reload_probe'),[11],require_gradient=False)
        verified=subprocess.run([python,str(ROOT/'scripts/day9_verify_reload.py')],cwd=ROOT,capture_output=True,text=True)
        (ROOT/'reports/day9_reload_verification.log').write_text(verified.stdout+verified.stderr)
        if verified.returncode:raise ValueError('Actual lightweight reload verification failed')
        report['weight_reload_verified']=True
        formal=run_phase('formal')
        validate_updates(evidence('formal'),range(12,226))
        report['formal_225_updates_complete']=True
        record('formal_updates_completed')
    except Exception as error:
        report['failure']=str(error);record('stopped_for_inspection');print(str(error),flush=True);return 1
    return 0


if __name__=='__main__':raise SystemExit(main())
