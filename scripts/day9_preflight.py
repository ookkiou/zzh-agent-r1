"""Linux CPU preflight: public data, tokenizer lengths, runtime identity and storage gates."""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from code_repair.agent_protocol import initial_messages
from code_repair.contracts import TOOL_SCHEMAS
from code_repair.public_data import load_public_task
from code_repair.checkpoint_retention import storage_budget
from day9_train import fingerprint


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--checkpoint-root',type=Path,default=Path('/root/zzh-day9-checkpoints'));args=p.parse_args()
    if sys.platform!='linux':raise SystemExit('Linux CPU/GPU instance required; no model inference performed')
    checks={}
    identity=json.loads((ROOT/'runs/day9/input_identity.json').read_text())
    plan=json.loads((ROOT/'training/day9/run_plan.json').read_text())
    public=ROOT/'runs/day9/public_data';manifest=json.loads((public/'manifest.json').read_text())
    checks['public_manifest_identity']=hashlib.sha256((public/'manifest.json').read_bytes()).hexdigest()==identity['public_manifest_sha256']
    checks['run_plan_identity']=hashlib.sha256((ROOT/'training/day9/run_plan.json').read_bytes()).hexdigest()==identity['run_plan_sha256']
    for name,digest in identity['runtime_core_sha256'].items():
        checks['source/'+name]=hashlib.sha256((ROOT/name).read_bytes()).hexdigest()==digest
    for split in ('train','dev'):
        checks[split+'_rows_identity']=hashlib.sha256((ROOT/'runs/day9'/(split+'.jsonl')).read_bytes()).hexdigest()==identity[split+'_jsonl_sha256']
    lock=json.loads((ROOT/'TRAINING_SOURCE_LOCK.json').read_text())
    for name,digest in lock['agent_r1']['reviewed_files_sha256'].items():
        checks['upstream/'+name]=hashlib.sha256((ROOT/'runs/day6/Agent-R1'/name).read_bytes()).hexdigest()==digest
    model_manifest=json.loads((ROOT/'reports/day7_sft_checkpoint_manifest.json').read_text())
    for name,value in model_manifest['files'].items():
        if name.startswith('merged/'):
            checks['sft/'+name]=hashlib.sha256((ROOT/'runs/day7/sft_warmup'/name).read_bytes()).hexdigest()==value['sha256']
    from transformers import AutoTokenizer
    import pandas as pd
    import code_repair.day9_audit
    tokenizer=AutoTokenizer.from_pretrained(ROOT/'runs/day7/sft_warmup/merged',local_files_only=True)
    metadata_keys={'task_id','source_id','split','entrypoint','instruction'}
    lengths=[]
    for row in manifest['tasks']:
        task=load_public_task(public,row['task_id'])
        if set(json.loads((public/row['path']/'task.json').read_text()))!=metadata_keys:
            raise ValueError('Non-public metadata exported')
        ids=tokenizer.apply_chat_template(initial_messages(task),tools=TOOL_SCHEMAS,tokenize=True,add_generation_prompt=True)
        lengths.append(len(ids))
    checks['all_332_initial_tool_prompts_fit']=len(lengths)==332 and max(lengths)<=4096
    for split,expected in [('train',300),('dev',32)]:
        data=pd.read_parquet(ROOT/'runs/day9'/(split+'.parquet'))
        checks[split+'_parquet_rows']=len(data)==expected
        if not all(json.loads(v).keys()=={'task_id'} for v in data['env_kwargs']):raise ValueError('Control fields in dataset')
    declared=set(manifest['files'])|{'manifest.json'}
    checks['public_export_exact_allowlist']={str(p.relative_to(public)) for p in public.rglob('*') if p.is_file()}==declared
    for name,digest in manifest['files'].items():
        if hashlib.sha256((public/name).read_bytes()).hexdigest()!=digest:raise ValueError('Public export checksum mismatch')
    resolved=json.loads((ROOT/'reports/day9_pilot_resolve_status.json').read_text())
    checks['actual_hydra_config_resolved']=resolved['returncode']==0 and resolved['run_fingerprint']==fingerprint(ROOT)
    docker=json.loads((ROOT/'reports/day9_docker_data_validation.json').read_text())
    checks['all_data_docker_validated']=docker['complete'] and docker['manifest_sha256']==identity['dataset_manifest_sha256']
    checkpoint_root=args.checkpoint_root.resolve()
    budget=storage_budget(checkpoint_root,fingerprint(ROOT),plan['minimum_free_gib'])
    storage_ready=budget['storage_ready']
    result=subprocess.run(['nvidia-smi','--query-gpu=name,memory.total','--format=csv,noheader'],capture_output=True,text=True)
    gpu_available=result.returncode==0 and bool(result.stdout.strip())
    active=subprocess.run(['nvidia-smi','--query-compute-apps=pid,process_name','--format=csv,noheader'],capture_output=True,text=True)
    gpu_idle=active.returncode==0 and not active.stdout.strip()
    versions={name:importlib.metadata.version(name) for name in ('torch','transformers','vllm','ray','peft')}
    report={'cpu_preparation_complete':all(checks.values()),'checks':checks,
        'ready_for_gpu_pilot':all(checks.values()) and storage_ready and gpu_available and gpu_idle,
        'run_fingerprint':fingerprint(ROOT),'checkpoint_root':str(checkpoint_root),
        **budget,'optimizer_state_saved':False,
        'gpu_available':gpu_available,'gpu_idle':gpu_idle,'gpu':result.stdout.strip(),
        'versions':versions,'max_initial_prompt_tokens':max(lengths),
        'source_files':identity['runtime_core_sha256'],'training_performed':False,
        'optimizer_recovery_verified':False,'test_executed':False}
    (ROOT/'reports/day9_remote_preflight.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k not in ('checks','source_files')},indent=2))
    if not report['cpu_preparation_complete']:raise SystemExit(1)


if __name__=='__main__':main()
