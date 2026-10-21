"""Build v0.2 train expansion while preserving every v0.1 task and test freeze.

Only explicitly reviewed references and controlled AST fixture mutations execute
locally. No model candidates, dev expansion or test-source execution occurs.
"""
import argparse
import ast
from collections import Counter,defaultdict
import json
from pathlib import Path
import sys
import warnings

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from code_repair.contracts import ContractError,validate_candidate_source
from code_repair.dataset import near_duplicate,normalize_record,render_public_tests,sha256,source_features
from code_repair.dataset_v2 import expanded_mutations
from code_repair.execution import TrustedLocalBackend,strict_equal
from scripts.build_mbpp import OUTPUT as PARENT,PIPELINE_FILES as OLD_PIPELINE,json_text,reviewed_cases
from scripts.fetch_mbpp import DESTINATION,verify_snapshot
from scripts.mbpp_specs import SPECS as OLD_SPECS
from scripts.mbpp_specs_v2 import SPECS as NEW_SPECS,REVIEW_EXCLUSIONS
from scripts.verify_mbpp import validate_single_mutation

OUTPUT=ROOT/'data/mbpp_repair/v0.2'
VERSION='mbpp-repair@0.2.0'
TARGET_TRAIN=300
MAX_PER_SOURCE=8
MIN_TRAIN_SOURCES=60
PIPELINE_FILES=(*OLD_PIPELINE,'code_repair/dataset_v2.py','scripts/mbpp_specs_v2.py','scripts/build_mbpp_v2.py')


def execute_cases(backend,source,entrypoint,public,private):
    cases=[*public,*private]
    outcome=backend.execute(source,entrypoint,[row['args'] for row in cases],timeout=0.6)
    if outcome.status!='completed':return None,outcome.status
    results=[]
    for case,row in zip(cases,outcome.rows):
        results.append(row['kind']=='return' and strict_equal(row['value'],case['expected']))
    split=len(public)
    report={'public_passed':sum(results[:split]),'public_tests':split,
        'private_passed':sum(results[split:]),'private_tests':len(private),
        'behavior_sha256':sha256(json.dumps(outcome.rows,sort_keys=True,allow_nan=False))}
    return report,'completed'


def build_resources():
    warnings.filterwarnings('ignore',category=SyntaxWarning)
    lock=verify_snapshot()
    parent=json.loads((PARENT/'manifest.json').read_text())
    for name,digest in parent['pipeline_files'].items():
        if sha256((ROOT/name).read_bytes())!=digest:raise ValueError('Frozen v0.1 pipeline changed: '+name)
    for name,digest in parent['files'].items():
        if sha256((PARENT/name).read_bytes())!=digest:raise ValueError('Frozen v0.1 data changed: '+name)
    raw={r['task_id']:r for r in map(json.loads,(DESTINATION/'mbpp.jsonl').read_text().splitlines())}
    frozen=json.loads((PARENT/'test_sources.lock.json').read_text())
    occupied=[]
    for i in OLD_SPECS:
        record=normalize_record(raw[i]);occupied.append((record['source_id'],source_features(record['reference'])))
    for row in frozen['sources']:
        record=normalize_record(raw[row['upstream_task_id']])
        occupied.append((record['source_id'],source_features(record['reference'])))
    prototype=ROOT/'data/prototype'
    for row in json.loads((prototype/'manifest.json').read_text())['tasks']:
        occupied.append(('prototype:'+row['task_id'],source_features((prototype/row['path']/'reference/solution.py').read_text())))
    resources={}
    tasks=list(parent['tasks'])
    inherited_by_source=defaultdict(list)
    for row in tasks:
        inherited_by_source[row['source_id']].append(row)
        for name in ('task.json','starter/solution.py','reference/solution.py','public_tests.py','private_tests.json'):
            relative=row['path']+'/'+name;resources[relative]=(PARENT/relative).read_text()
    backend=TrustedLocalBackend()
    pools={};source_reports=[];duplicate_reports=[]
    specs={i:s for i,s in OLD_SPECS.items() if i>=601}|NEW_SPECS
    for i,spec in sorted(specs.items()):
        record=normalize_record(raw[i])
        if record['split']!='train':raise ValueError('Only train may be expanded')
        source_id=record['source_id']
        if source_id not in parent['sources']['train']:
            features=source_features(record['reference'])
            duplicate=next(((other,near_duplicate(features,value)) for other,value in occupied
                if other!=source_id and near_duplicate(features,value)),None)
            if duplicate:
                duplicate_reports.append({'source_id':source_id,'matched_source_id':duplicate[0],'reason':duplicate[1]})
                continue
            occupied.append((source_id,features))
        public,private=reviewed_cases(record,spec)
        reference,status=execute_cases(backend,record['reference'],record['entrypoint'],public,private)
        if (status!='completed' or reference['public_passed']!=len(public) or reference['private_passed']!=len(private)):
            raise ValueError('Reviewed reference failed independent contract: '+source_id+' '+str(reference))
        existing=inherited_by_source[source_id]
        code_hashes=set();behaviors=set()
        for row in existing:
            starter=resources[row['path']+'/starter/solution.py']
            outcome,status=execute_cases(backend,starter,record['entrypoint'],public,private)
            if status!='completed':raise ValueError('Inherited fixture execution failed')
            code_hashes.add(sha256(starter));behaviors.add(outcome['behavior_sha256'])
        grouped=defaultdict(list)
        for item in expanded_mutations(record['reference']):grouped[item['bug_type']].append(item)
        candidates=[]
        for index in range(max(map(len,grouped.values()),default=0)):
            candidates.extend(grouped[k][index] for k in sorted(grouped) if index<len(grouped[k]))
        accepted=[];rejected=[]
        for item in candidates:
            if len(existing)+len(accepted)>=MAX_PER_SOURCE:break
            digest=sha256(item['source'])
            if digest in code_hashes:continue
            try:
                validate_candidate_source(item['source'],record['reference'],record['entrypoint'])
                validate_single_mutation(record['reference'],item['source'],item['mutation'])
            except (ContractError,ValueError,SyntaxError) as error:
                rejected.append({'mutation':item['mutation'],'reason':'invalid_source','detail':str(error)})
                continue
            outcome,status=execute_cases(backend,item['source'],record['entrypoint'],public,private)
            if status!='completed':
                rejected.append({'mutation':item['mutation'],'reason':status});continue
            if outcome['public_passed']==len(public) or outcome['private_passed']==len(private):
                rejected.append({'mutation':item['mutation'],'reason':'not_both_public_and_private_failure'});continue
            if outcome['behavior_sha256'] in behaviors:
                rejected.append({'mutation':item['mutation'],'reason':'same_observed_typed_outputs_and_exceptions'});continue
            behaviors.add(outcome['behavior_sha256']);code_hashes.add(digest)
            accepted.append({**item,'verification':outcome})
        pools[source_id]=[{'record':record,'spec':spec,'public':public,'private':private,'variant':v} for v in accepted]
        source_reports.append({'source_id':source_id,'domain':spec['domain'],'review_note':spec['review_note'],
            'review_status':'agent_reviewed_not_human_signed_off','inherited_tasks':len(existing),
            'eligible_additional_variants':len(accepted),'reference':reference,'rejected_candidates':rejected})
        print(source_id,'inherited',len(existing),'new candidates',len(accepted),flush=True)
    required=TARGET_TRAIN-sum(r['split']=='train' for r in tasks)
    chosen=[]
    for index in range(MAX_PER_SOURCE):
        for source_id in sorted(pools):
            if index<len(pools[source_id]) and len(chosen)<required:chosen.append(pools[source_id][index])
    inventory={'target_train_tasks':TARGET_TRAIN,'eligible_additional_variants':sum(map(len,pools.values())),
        'selected_additional_variants':len(chosen),'selected_sources':len({r['record']['source_id'] for r in chosen}),
        'sources':source_reports,'duplicates_excluded':duplicate_reports}
    (ROOT/'reports/day9_build_inventory.json').write_text(json_text(inventory))
    if len(chosen)!=required:raise ValueError('Insufficient genuinely distinct validated train mutations; do not pad dataset')
    next_index=defaultdict(int)
    for selected in chosen:
        record,spec,variant,public,private=(selected[k] for k in ('record','spec','variant','public','private'))
        source_id=record['source_id'];next_index[source_id]+=1
        task_id=f'{source_id}-x{next_index[source_id]:02d}'
        relative='train/'+task_id
        metadata={'task_id':task_id,'source_id':source_id,'split':'train','entrypoint':record['entrypoint'],
            'instruction':record['instruction']+'\n\n精确输入域与验收约定：'+spec['domain']+f"\n修复 solution.py 中的 {record['entrypoint']} 函数，保留签名。",
            'bug_type':variant['bug_type'],'mutation':variant['mutation'],
            'source':{'repository':lock['repository'],'commit':lock['commit'],'task_id':record['upstream_task_id'],
                'raw_code_sha256':record['raw_code_sha256'],'reference_sha256':record['reference_sha256']},
            'domain':spec['domain'],'review_status':'agent_reviewed_not_human_signed_off',
            'public_cases':len(public),'private_cases':len(private)}
        assets={'task.json':json_text(metadata),'starter/solution.py':variant['source'],
            'reference/solution.py':record['reference'],'public_tests.py':render_public_tests(record['entrypoint'],public),
            'private_tests.json':json_text(private)}
        resources.update({relative+'/'+name:content for name,content in assets.items()})
        tasks.append({'task_id':task_id,'source_id':source_id,'split':'train','bug_type':variant['bug_type'],'path':relative})
    tasks.sort(key=lambda row:(row['split'],row['task_id']))
    sources={split:sorted({r['source_id'] for r in tasks if r['split']==split}) for split in ('train','dev')}
    if len(sources['train'])<MIN_TRAIN_SOURCES:raise ValueError('Insufficient train source diversity')
    selection={'version':VERSION,'parent_version':parent['version'],'model_results_used_for_selection':False,
        'target_train':TARGET_TRAIN,'max_variants_per_source':MAX_PER_SOURCE,
        'selection':'preserve v0.1, then round-robin additional mutations across reviewed train sources',
        'behavior_dedup':'actual typed outputs and exception types over fixed public+private inputs; not semantic equivalence',
        'new_review_exclusions':REVIEW_EXCLUSIONS,'source_reports':source_reports,
        'duplicates_excluded':duplicate_reports,'human_review_complete':False}
    resources['selection_report.json']=json_text(selection)
    resources['test_sources.lock.json']=(PARENT/'test_sources.lock.json').read_text()
    manifest={'schema_version':1,'version':VERSION,'parent_version':parent['version'],
        'parent_manifest_sha256':sha256((PARENT/'manifest.json').read_bytes()),
        'source_lock_sha256':parent['source_lock_sha256'],
        'pipeline_files':{name:sha256((ROOT/name).read_bytes()) for name in PIPELINE_FILES},
        'split_policy':parent['split_policy'],'tasks':tasks,'sources':sources,
        'task_counts':dict(Counter(r['split'] for r in tasks)),
        'source_counts':{split:len(value) for split,value in sources.items()},
        'bug_counts':dict(Counter(r['bug_type'] for r in tasks)),
        'frozen_test_sources':50,'dev_unchanged':True,'test_freeze_unchanged':True,
        'files':{name:sha256(text) for name,text in sorted(resources.items())}}
    resources['manifest.json']=json_text(manifest)
    return resources


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--check',action='store_true');args=parser.parse_args()
    resources=build_resources()
    existing={str(p.relative_to(OUTPUT)) for p in OUTPUT.rglob('*') if p.is_file()}
    for name,content in resources.items():
        p=OUTPUT/name
        if p.exists() and p.read_text()!=content:raise ValueError('Existing v0.2 differs: '+name)
        if args.check and not p.exists():raise ValueError('Missing v0.2 resource: '+name)
    if existing-set(resources):raise ValueError('Unexpected v0.2 assets')
    if not args.check:
        for name,content in resources.items():
            p=OUTPUT/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(content)
    manifest=json.loads(resources['manifest.json'])
    print('Checked' if args.check else 'Built',manifest['task_counts'],manifest['source_counts'])


if __name__=='__main__':
    main()
