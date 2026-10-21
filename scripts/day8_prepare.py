"""Freeze complete dev baseline protocol and train-only bounded smoke inputs."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from code_repair.agent_protocol import PROTOCOL_VERSION, initial_messages
from code_repair.public_data import load_public_task


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--parquet-only', action='store_true')
    args = parser.parse_args()
    output = ROOT / 'runs/day8'
    output.mkdir(exist_ok=True)
    if args.parquet_only:
        import pandas as pd
        for name in ('train_smoke', 'dev'):
            rows = [json.loads(line) for line in (output / (name + '.jsonl')).read_text().splitlines()]
            pd.DataFrame(rows).to_parquet(output / (name + '.parquet'), index=False)
        print('Day8 parquet ready')
        return
    previous = json.loads((ROOT / 'reports/day7_sft_acceptance.json').read_text())
    if not previous['complete']:
        raise ValueError('Day7 final acceptance required')
    frozen = json.loads((ROOT / 'data/mbpp_repair/v0.1/manifest.json').read_text())
    for name, digest in frozen['pipeline_files'].items():
        if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest:
            raise ValueError('Frozen data pipeline changed: ' + name)
    public = ROOT / 'runs/day7/public_data'
    manifest = json.loads((public / 'manifest.json').read_text())
    selection = json.loads((ROOT / 'runs/day7/selection.json').read_text())
    train_ids = {r['task_id'] for r in selection['tasks'] if r['split'] == 'train'}
    dev = [r for r in manifest['tasks'] if r['split'] == 'dev']
    train = [r for r in manifest['tasks'] if r['task_id'] in train_ids and r['split'] == 'train']
    if len(dev) != 32 or len(train) != 4:
        raise ValueError('Expected complete frozen dev and four previously diagnosed train tasks')
    if {r['source_id'] for r in dev} & {r['source_id'] for r in train}:
        raise ValueError('Train/dev source overlap')
    hashes = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in
        ('code_repair/agent_protocol.py', 'code_repair/agent_session.py',
         'code_repair/contracts.py', 'code_repair/environment.py')}
    protocol = {'schema_version': 1, 'protocol_version': PROTOCOL_VERSION,
        'split': 'dev', 'purpose': 'complete development baseline, not final test',
        'seeds': [17, 29, 43], 'temperature': 0.6, 'top_p': 0.95,
        'max_steps': 6, 'max_prompt_length': 4096, 'max_response_length': 512,
        'episode_timeout': 240, 'test_timeout': 10, 'infra_retries': 2,
        'generation_backend': 'Transformers SDPA BF16; sequential single-episode generation',
        'metric': 'all valid single episodes; not best-of-three/pass@3',
        'source_manifest_sha256': manifest['source_manifest_sha256'],
        'core_files_sha256': hashes,
        'tasks': [{k:r[k] for k in ('task_id','source_id','split')} for r in dev]}
    protocol_path = output / 'evaluation_protocol.json'
    content = json.dumps(protocol, ensure_ascii=False, indent=2) + '\n'
    if protocol_path.exists() and protocol_path.read_text() != content:
        raise ValueError('Existing evaluation protocol differs; require a new version')
    protocol_path.write_text(content)
    for name, selected in (('train_smoke', train), ('dev', dev)):
        rows = []
        for index, row in enumerate(selected):
            task = load_public_task(public, row['task_id'])
            rows.append({'data_source': 'zzh_code_repair/v0.1', 'agent_name':'zzh_code_repair_day8',
                'prompt': initial_messages(task), 'env_kwargs':json.dumps({'task_id':task.task_id}),
                'reward_model':{'style':'rule','ground_truth':''},
                'extra_info':{**{k:row[k] for k in ('task_id','source_id','split')},'index':index}})
        (output / (name+'.jsonl')).write_text(''.join(json.dumps(r,ensure_ascii=False)+'\n' for r in rows))
    report = {'complete':True,'day8_complete':False,'dev_tasks':len(dev),
        'dev_sources':len({r['source_id'] for r in dev}),'attempts_per_model':96,
        'baseline_models':['Base','SFT-only'],'total_baseline_attempts':192,
        'smoke_train_tasks':[{k:r[k] for k in ('task_id','source_id','split')} for r in train],
        'smoke_only_repeats_four_train_tasks':True,
        'evaluation_protocol_sha256':hashlib.sha256(protocol_path.read_bytes()).hexdigest(),
        'test_executed':False,'private_materials_in_inputs':False}
    (ROOT / 'reports/day8_preparation.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__ == '__main__':
    main()
