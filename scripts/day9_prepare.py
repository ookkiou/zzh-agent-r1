"""Export redacted public resources and frozen formal-run inputs; never export private labels."""
import argparse
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from code_repair.agent_protocol import initial_messages
from code_repair.dataset import sha256
from code_repair.public_data import load_public_task


PUBLIC_METADATA_KEYS=('task_id','source_id','split','entrypoint','instruction')


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--parquet-only',action='store_true');args=p.parse_args()
    output=ROOT/'runs/day9';output.mkdir(exist_ok=True)
    if args.parquet_only:
        import pandas as pd
        for split in ('train','dev'):
            rows=[json.loads(x) for x in (output/(split+'.jsonl')).read_text().splitlines()]
            for row in rows:
                if set(json.loads(row['env_kwargs']))!={'task_id'}:raise ValueError('Control-plane overrides in rows')
            pd.DataFrame(rows).to_parquet(output/(split+'.parquet'),index=False)
        print('Prepared public train/dev parquet')
        return
    dataset=ROOT/'data/mbpp_repair/v0.2';manifest=json.loads((dataset/'manifest.json').read_text())
    report=json.loads((ROOT/'reports/day9_data_validation.json').read_text())
    if not report['complete'] or report['manifest_sha256']!=sha256((dataset/'manifest.json').read_bytes()):
        raise ValueError('Verified v0.2 required')
    public=output/'public_data';files={};tasks=[]
    parent=json.loads((ROOT/'data/mbpp_repair/v0.1/manifest.json').read_text())
    teacher=json.loads((ROOT/'reports/day7_sft_data.json').read_text())
    for row in manifest['tasks']:
        path=dataset/row['path'];meta=json.loads((path/'task.json').read_text())
        redacted={k:meta[k] for k in PUBLIC_METADATA_KEYS}
        assets={'task.json':json.dumps(redacted,ensure_ascii=False,indent=2)+'\n',
            'starter/solution.py':(path/'starter/solution.py').read_text(),
            'public_tests.py':(path/'public_tests.py').read_text()}
        for name,content in assets.items():
            relative=row['path']+'/'+name;destination=public/relative
            destination.parent.mkdir(parents=True,exist_ok=True);destination.write_text(content)
            files[relative]=sha256(content)
        tasks.append({k:row[k] for k in ('task_id','source_id','split','path')})
    public_manifest={'schema_version':1,'source_manifest_sha256':report['manifest_sha256'],
        'parent_manifest_sha256':manifest['parent_manifest_sha256'],'tasks':tasks,'files':files,
        'redacted_task_metadata_keys':list(PUBLIC_METADATA_KEYS)}
    (public/'manifest.json').write_text(json.dumps(public_manifest,ensure_ascii=False,indent=2)+'\n')
    if {str(p.relative_to(public)) for p in public.rglob('*') if p.is_file()}!=set(files)|{'manifest.json'}:
        raise ValueError('Unexpected/missing public export files')
    dev_identity=[]
    for split in ('train','dev'):
        rows=[]
        for index,row in enumerate(r for r in tasks if r['split']==split):
            task=load_public_task(public,row['task_id'])
            rows.append({'data_source':'zzh_code_repair/v0.2','agent_name':'zzh_code_repair_day9',
                'prompt':initial_messages(task),'env_kwargs':json.dumps({'task_id':task.task_id}),
                'reward_model':{'style':'rule','ground_truth':''},
                'extra_info':{k:row[k] for k in ('task_id','source_id','split')}|
                    {'index':index,'sft_seen_source':row['source_id'] in teacher['source_ids']}})
            if split=='dev':
                old=next(r for r in parent['tasks'] if r['task_id']==task.task_id)
                old_task=load_public_task(ROOT/'runs/day7/public_data',task.task_id)
                if initial_messages(old_task)!=initial_messages(task) or old_task.starter_source!=task.starter_source or old_task.public_test_source!=task.public_test_source:
                    raise ValueError('Frozen dev model inputs changed')
                dev_identity.append({'task_id':task.task_id,'messages_sha256':sha256(json.dumps(initial_messages(task),ensure_ascii=False)),
                    'starter_sha256':sha256(task.starter_source),'public_tests_sha256':sha256(task.public_test_source)})
        (output/(split+'.jsonl')).write_text(''.join(json.dumps(row,ensure_ascii=False)+'\n' for row in rows))
    plan_path=ROOT/'training/day9/run_plan.json'
    identity={'dataset_version':manifest['version'],'dataset_manifest_sha256':report['manifest_sha256'],
        'public_manifest_sha256':sha256((public/'manifest.json').read_bytes()),
        'train_jsonl_sha256':sha256((output/'train.jsonl').read_bytes()),
        'dev_jsonl_sha256':sha256((output/'dev.jsonl').read_bytes()),
        'run_plan_sha256':sha256(plan_path.read_bytes()),'dev_model_inputs_unchanged':True,
        'dev_identity':dev_identity,'runtime_core_sha256':{f:sha256((ROOT/f).read_bytes()) for f in
            ('code_repair/agent_protocol.py','code_repair/agent_session.py','code_repair/contracts.py','code_repair/environment.py',
             'code_repair/day8_flow.py','code_repair/day8_audit.py','code_repair/day9_audit.py',
             'code_repair/checkpoint_retention.py','scripts/day9_train.py')}}
    (output/'input_identity.json').write_text(json.dumps(identity,indent=2)+'\n')
    summary={'complete':True,'formal_training_performed':False,'train_tasks':300,'train_sources':manifest['source_counts']['train'],
        'dev_tasks':32,'dev_sources':14,'dev_model_inputs_unchanged':True,'private_tests_exported':False,
        'reference_code_exported':False,'mutation_metadata_exported':False,
        'public_files':len(files)+1,'dataset_manifest_sha256':report['manifest_sha256'],
        'input_identity_sha256':sha256((output/'input_identity.json').read_bytes()),'test_executed':False}
    (ROOT/'reports/day9_preparation.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps(summary,indent=2))


if __name__=='__main__':main()
