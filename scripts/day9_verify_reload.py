"""Verify lightweight weight/data restart; optimizer continuation is deliberately unavailable."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from code_repair.checkpoint_retention import completed_checkpoints
from day9_train import fingerprint


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--checkpoint-root',type=Path,default=Path('/root/zzh-day9-checkpoints'));args=p.parse_args()
    root=args.checkpoint_root.resolve();known={step:(path,info) for step,path,info in completed_checkpoints(root,fingerprint(ROOT))}
    if not {10,11}.issubset(known):raise ValueError('Completed pilot and weight-reload probe required')
    for phase in ('pilot','reload_probe'):
        status=json.loads((ROOT/'reports'/('day9_'+phase+'_execute_status.json')).read_text())
        if status['returncode']!=0 or status['run_fingerprint']!=fingerprint(ROOT):raise ValueError('Phase failed or identity changed')
        if status['overrides']['actor_rollout_ref.actor.checkpoint.load_contents']!=['model','extra']:
            raise ValueError('Lightweight load policy differs')
    import torch
    summaries={}
    for step,(path,info) in sorted(known.items()):
        if info['optimizer_state_saved'] or list(path.rglob('optim_world_size_*.pt')):
            raise ValueError('Unexpected optimizer checkpoint')
        extra=torch.load(path/'actor/extra_state_world_size_1_rank_0.pt',map_location='cpu',weights_only=False)
        scheduler=extra['lr_scheduler']
        if scheduler['last_epoch']!=step:raise ValueError('Scheduler step differs from saved training progress')
        summaries[step]={'saved_bytes':sum(info['files'].values()),'scheduler_last_epoch':scheduler['last_epoch'],
            'rng_state_present':'rng' in extra,'data_state_bytes':(path/'data.pt').stat().st_size}
    probe=json.loads((ROOT/'reports/day9_reload_probe_execute_status.json').read_text())
    evidence=json.loads((ROOT/'reports/day9_reload_probe_worker_evidence.json').read_text())
    if not evidence['complete'] or evidence['run_fingerprint']!=fingerprint(ROOT):raise ValueError('Matching native worker evidence required')
    if hashlib.sha256(Path(evidence['evidence_log']).read_bytes()).hexdigest()!=evidence['evidence_sha256']:
        raise ValueError('Native worker evidence changed')
    for source in evidence['sources']:
        if hashlib.sha256((ROOT/source['copy']).read_bytes()).hexdigest()!=source['sha256']:
            raise ValueError('Native worker raw log changed')
    log=Path(evidence['evidence_log']).read_text(errors='replace')
    updates=set(map(int,re.findall(r'training/global_step:(\d+)',log)))
    if (updates!={11} or 'Loaded model from' not in log or 'Loaded lr_scheduler from' not in log
            or 'Loaded optimizer from' in log or 'global_step_10' not in probe['overrides']['trainer.resume_from_path']):
        raise ValueError('Expected weight/extra reload and exactly update11')
    if 'no dataloader state found' in log.lower():raise ValueError('Data progress was reset')
    report={'complete':True,'checkpoint_root':str(root),'run_fingerprint':fingerprint(ROOT),
        'checkpoints':summaries,'only_update_11_executed_after_restart':True,
        'native_worker_evidence_sha256':evidence['evidence_sha256'],
        'model_scheduler_rng_and_data_files_present':True,
        'optimizer_state_saved':False,'optimizer_continuation_verified':False,
        'restart_semantics':'Weights/data/extra restored; Adam moments rebuilt. Not equivalent to uninterrupted training.',
        'bitwise_resume_guaranteed':False,'formal_225_updates_completed':False}
    (ROOT/'reports/day9_reload_verification.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
