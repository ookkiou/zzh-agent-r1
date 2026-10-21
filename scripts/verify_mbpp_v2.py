"""Independently verify v0.2 resources, reviewed cases and preserved dev/test boundaries."""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from code_repair.contracts import validate_candidate_source
from code_repair.dataset import near_duplicate,normalize_record,render_public_tests,sha256,source_features,source_split
from code_repair.execution import TrustedLocalBackend,check_cases
from code_repair.tasks import load_task
from scripts.build_mbpp import OUTPUT as PARENT,reviewed_cases
from scripts.build_mbpp_v2 import OUTPUT,PIPELINE_FILES,VERSION,TARGET_TRAIN,MIN_TRAIN_SOURCES
from scripts.fetch_mbpp import DESTINATION,verify_snapshot
from scripts.mbpp_specs import SPECS as OLD_SPECS
from scripts.mbpp_specs_v2 import SPECS as NEW_SPECS
from scripts.verify_mbpp import safe_path,validate_single_mutation


def verify_dataset(dataset=OUTPUT,*,execute=True):
    dataset=Path(dataset).resolve()
    lock=verify_snapshot()
    parent=json.loads((PARENT/'manifest.json').read_text())
    manifest=json.loads((dataset/'manifest.json').read_text())
    if manifest['version']!=VERSION or manifest['parent_manifest_sha256']!=sha256((PARENT/'manifest.json').read_bytes()):
        raise ValueError('Dataset version or parent provenance changed')
    if manifest['source_lock_sha256']!=parent['source_lock_sha256'] or not manifest['dev_unchanged'] or not manifest['test_freeze_unchanged']:
        raise ValueError('Source provenance/dev/test preservation required')
    if set(manifest['pipeline_files'])!=set(PIPELINE_FILES):raise ValueError('Incomplete pipeline provenance')
    for f,d in manifest['pipeline_files'].items():
        if sha256((ROOT/f).read_bytes())!=d:raise ValueError('Pipeline changed after freeze: '+f)
    for f,d in parent['pipeline_files'].items():
        if sha256((ROOT/f).read_bytes())!=d:raise ValueError('Frozen v0.1 pipeline changed')
    for f,d in parent['files'].items():
        if sha256((PARENT/f).read_bytes())!=d:raise ValueError('Frozen v0.1 resource changed')
    expected=set(manifest['files'])|{'manifest.json'}
    if {str(p.relative_to(dataset)) for p in dataset.rglob('*') if p.is_file()}!=expected:
        raise ValueError('Missing or undeclared dataset asset')
    for f,d in manifest['files'].items():
        if sha256(safe_path(dataset,f).read_bytes())!=d:raise ValueError('Dataset resource changed: '+f)
    frozen_bytes=(PARENT/'test_sources.lock.json').read_bytes()
    if (dataset/'test_sources.lock.json').read_bytes()!=frozen_bytes:raise ValueError('Test freeze changed')
    frozen=json.loads(frozen_bytes)
    test_sources={r['source_id'] for r in frozen['sources']}
    if len(test_sources)!=50:raise ValueError('Expected fifty frozen test sources')
    for item in parent['tasks']:
        if item not in manifest['tasks']:raise ValueError('Inherited task metadata index changed')
        for name in ('task.json','starter/solution.py','reference/solution.py','public_tests.py','private_tests.json'):
            relative=item['path']+'/'+name
            if (dataset/relative).read_bytes()!=(PARENT/relative).read_bytes():raise ValueError('Inherited task bytes changed: '+relative)
    if [r for r in manifest['tasks'] if r['split']=='dev']!=[r for r in sorted(parent['tasks'],key=lambda x:(x['split'],x['task_id'])) if r['split']=='dev']:
        raise ValueError('Dev task selection changed')
    raw={r['task_id']:r for r in map(json.loads,(DESTINATION/'mbpp.jsonl').read_text().splitlines())}
    inherited={r['task_id']:r for r in parent['tasks']}
    specs=OLD_SPECS|NEW_SPECS
    backend=TrustedLocalBackend();rows=[];seen=set();source_records={}
    declared_assets={'selection_report.json','test_sources.lock.json'}
    for item in manifest['tasks']:
        match=re.fullmatch(r'mbpp-(\d{3})-([mx])(\d{2})',item['task_id'])
        if not match or item['task_id'] in seen:raise ValueError('Invalid/duplicate task ID')
        seen.add(item['task_id']);i=int(match[1]);record=normalize_record(raw[i])
        if record['split'] not in ('train','dev') or i not in specs:raise ValueError('Unreviewed/test source entered tasks')
        if item['task_id'] not in inherited and (record['split']!='train' or match[2]!='x'):
            raise ValueError('Only new train tasks with separate IDs allowed')
        task_dir=safe_path(dataset,item['path']);meta=json.loads((task_dir/'task.json').read_text())
        task=load_task(task_dir);reference=(task_dir/'reference/solution.py').read_text()
        if any(meta[k]!=item[k] for k in ('task_id','source_id','split','bug_type')) or meta['source_id']!=record['source_id'] or meta['split']!=source_split(i):
            raise ValueError('Metadata/index/source split mismatch')
        if reference!=record['reference'] or task.entrypoint!=record['entrypoint'] or item['path']!=meta['split']+'/'+task.task_id:
            raise ValueError('Reference, entrypoint or task path changed')
        expected_provenance={'repository':lock['repository'],'commit':lock['commit'],'task_id':i,
            'raw_code_sha256':record['raw_code_sha256'],'reference_sha256':record['reference_sha256']}
        if meta['source']!=expected_provenance:raise ValueError('Upstream provenance mismatch')
        public,private=reviewed_cases(record,specs[i])
        instruction=record['instruction']+'\n\n精确输入域与验收约定：'+specs[i]['domain']+f"\n修复 solution.py 中的 {record['entrypoint']} 函数，保留签名。"
        if (task.instruction!=instruction or meta['domain']!=specs[i]['domain'] or list(task.public_cases)!=public
                or list(task.private_cases)!=private or (task_dir/'public_tests.py').read_text()!=render_public_tests(task.entrypoint,public)):
            raise ValueError('Cases/instruction differ from independently reviewed contract')
        if meta['public_cases']!=len(public) or meta['private_cases']!=len(private) or meta['review_status']!='agent_reviewed_not_human_signed_off':
            raise ValueError('Case counts or review attribution changed')
        validate_candidate_source(task.starter_source,reference,task.entrypoint)
        validate_single_mutation(reference,task.starter_source,meta['mutation'])
        row={k:item[k] for k in ('task_id','source_id','split','bug_type')}
        if execute:
            row['reference']={mode:check_cases(backend,reference,task.entrypoint,cases) for mode,cases in [('public',public),('private',private)]}
            row['starter']={mode:check_cases(backend,task.starter_source,task.entrypoint,cases) for mode,cases in [('public',public),('private',private)]}
            row['valid']=all(row['reference'][mode]['status']=='completed' and row['reference'][mode]['failed']==0
                and row['starter'][mode]['status']=='completed' and row['starter'][mode]['failed']>0 for mode in ('public','private'))
        else:row['valid']=None
        rows.append(row);source_records[record['source_id']]=record
        declared_assets.update(item['path']+'/'+name for name in ('task.json','starter/solution.py','reference/solution.py','public_tests.py','private_tests.json'))
    if declared_assets!=set(manifest['files']):raise ValueError('Manifest asset set mismatch')
    counts=dict(Counter(r['split'] for r in rows))
    sources={s:sorted({r['source_id'] for r in rows if r['split']==s}) for s in ('train','dev')}
    if (counts!=manifest['task_counts'] or sources!=manifest['sources']
            or {s:len(v) for s,v in sources.items()}!=manifest['source_counts']
            or dict(Counter(r['bug_type'] for r in rows))!=manifest['bug_counts']):raise ValueError('Manifest counts changed')
    if counts!={'dev':32,'train':TARGET_TRAIN} or len(sources['train'])<MIN_TRAIN_SOURCES:
        raise ValueError('Expected 300 train, unchanged 32 dev and adequate source diversity')
    if set(sources['train'])&set(sources['dev']) or test_sources&(set(sources['train'])|set(sources['dev'])):
        raise ValueError('Split source overlap')
    features=[(s,source_features(r['reference'])) for s,r in sorted(source_records.items())]
    for r in frozen['sources']:
        record=normalize_record(raw[r['upstream_task_id']]);features.append((record['source_id'],source_features(record['reference'])))
    prototype=ROOT/'data/prototype'
    for r in json.loads((prototype/'manifest.json').read_text())['tasks']:
        features.append(('prototype:'+r['task_id'],source_features((prototype/r['path']/'reference/solution.py').read_text())))
    for index,(s,f) in enumerate(features):
        for other,g in features[index+1:]:
            if near_duplicate(f,g):raise ValueError('Near-duplicate source overlap: '+s+' / '+other)
    selected=json.loads((dataset/'selection_report.json').read_text())
    if selected['model_results_used_for_selection'] or selected['human_review_complete']:raise ValueError('Selection/review attribution mismatch')
    return {'complete':execute and all(r['valid'] for r in rows),'static_validation_complete':True,
        'dataset_version':VERSION,'manifest_sha256':sha256((dataset/'manifest.json').read_bytes()),
        'task_counts':counts,'source_counts':manifest['source_counts'],'bug_counts':manifest['bug_counts'],
        'parent_v01_unchanged':True,'all_104_parent_tasks_unchanged':True,'dev_unchanged':True,'test_freeze_unchanged':True,
        'test_sources_executed':False,'test_source_count':50,'human_review_complete':False,
        'execution_scope':'reviewed known fixtures and controlled AST variants, not model-generated candidates',
        'tasks':rows}


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--static-only',action='store_true');args=p.parse_args()
    report=verify_dataset(execute=not args.static_only)
    output=ROOT/'reports'/('day9_data_static.json' if args.static_only else 'day9_data_validation.json')
    output.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='tasks'},ensure_ascii=False,indent=2))
    if not (report['static_validation_complete'] if args.static_only else report['complete']):raise SystemExit(1)


if __name__=='__main__':
    main()
