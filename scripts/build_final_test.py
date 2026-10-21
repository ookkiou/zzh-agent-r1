"""Build a separate held-out repair set after candidate selection; no model involved."""
import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from code_repair.contracts import validate_candidate_source
from code_repair.dataset import mutations, normalize_record, sha256, source_features, near_duplicate, render_public_tests
from code_repair.execution import TrustedLocalBackend, check_cases
from scripts.build_mbpp import reviewed_cases
from scripts.fetch_mbpp import DESTINATION, verify_snapshot
from scripts.mbpp_test_specs import SPECS, EXCLUSIONS

OUTPUT = ROOT/'data/mbpp_repair/test-v0.1'
POLICY = ROOT/'training/final_test/construction_policy.json'
COHORT = ROOT/'data/mbpp_repair/v0.2/test_sources.lock.json'
PIPELINE = ('scripts/build_final_test.py','scripts/mbpp_test_specs.py',
    'code_repair/dataset.py','code_repair/contracts.py','code_repair/execution.py')


def text(value):
    return json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n'


def stable(result):
    return {k:v for k,v in result.items() if k!='elapsed_seconds'}


def build():
    upstream = verify_snapshot()
    policy = json.loads(POLICY.read_text())
    cohort = json.loads(COHORT.read_text())
    if sha256(COHORT.read_bytes())!=policy['test_source_lock_sha256'] or sha256((ROOT/'reports/day11_candidate_freeze.json').read_bytes())!=policy['candidate_freeze_sha256']:
        raise ValueError('Candidate or source cohort changed after policy freeze')
    if set(SPECS)|set(EXCLUSIONS)!={r['upstream_task_id'] for r in cohort['sources']} or set(SPECS)&set(EXCLUSIONS):
        raise ValueError('Every frozen source needs exactly one review disposition')
    parent_path=ROOT/'data/mbpp_repair/v0.2'
    parent=json.loads((parent_path/'manifest.json').read_text())
    for name,digest in parent['files'].items():
        if sha256((parent_path/name).read_bytes())!=digest:
            raise ValueError('Frozen development resource changed: '+name)
    occupied=[]
    for item in parent['tasks']:
        if item['source_id'] not in {name for name,_ in occupied}:
            occupied.append((item['source_id'],source_features((parent_path/item['path']/'reference/solution.py').read_text())))
    prototype=ROOT/'data/prototype'
    for item in json.loads((prototype/'manifest.json').read_text())['tasks']:
        occupied.append(('prototype:'+item['task_id'],source_features((prototype/item['path']/'reference/solution.py').read_text())))
    raw={r['task_id']:r for r in map(json.loads,(DESTINATION/'mbpp.jsonl').read_text().splitlines())}
    backend=TrustedLocalBackend()
    resources={}; tasks=[]; reviews=[]
    for frozen in sorted(cohort['sources'],key=lambda r:r['upstream_task_id']):
        i=frozen['upstream_task_id']
        if i in EXCLUSIONS:
            reviews.append({'source_id':frozen['source_id'],'included':False,
                'reason':EXCLUSIONS[i],'stage':'independent_contract_review'})
            continue
        record=normalize_record(raw[i])
        for key in ('source_id','raw_code_sha256','reference_sha256'):
            if record[key]!=frozen[key]:
                raise ValueError('Frozen raw/reference identity mismatch')
        if record['split']!='test':
            raise ValueError('Non-test source in held-out builder')
        features=source_features(record['reference'])
        for source,other in occupied:
            reason=near_duplicate(features,other)
            if reason:
                raise ValueError('Frozen source overlaps prior source: '+record['source_id']+' '+source+' '+reason)
        occupied.append((record['source_id'],features))
        public,private=reviewed_cases(record,SPECS[i])
        reference={mode:stable(check_cases(backend,record['reference'],record['entrypoint'],cases))
            for mode,cases in [('public',public),('private',private)]}
        if any(r['status']!='completed' or r['failed'] for r in reference.values()):
            reviews.append({'source_id':record['source_id'],'included':False,
                'reason':'reference_contradicts_contract','stage':'reference_validation','reference':reference})
            print('REFERENCE FAILED',record['source_id'],json.dumps(reference),flush=True)
            continue
        grouped=defaultdict(list)
        for item in mutations(record['reference']):
            grouped[item['bug_type']].append(item)
        ordered=[grouped[kind][depth] for depth in range(max(map(len,grouped.values()),default=0))
            for kind in sorted(grouped) if depth<len(grouped[kind])]
        chosen=None; rejected=[]
        for candidate in ordered:
            validate_candidate_source(candidate['source'],record['reference'],record['entrypoint'])
            outcomes={}
            for mode,cases in [('public',public),('private',private)]:
                outcomes[mode]=stable(check_cases(backend,candidate['source'],record['entrypoint'],cases,timeout=0.5))
                if outcomes[mode]['status']!='completed' or not outcomes[mode]['failed']:
                    break
            if len(outcomes)==2 and all(r['status']=='completed' and r['failed'] for r in outcomes.values()):
                chosen=candidate
                break
            rejected.append({'mutation':candidate['mutation'],'results':outcomes})
        if chosen is None:
            reviews.append({'source_id':record['source_id'],'included':False,
                'reason':'no_completed_public_and_private_failing_mutation',
                'stage':'mutation_validation','rejected_candidates':rejected})
            continue
        task_id=record['source_id']+'-t01'
        relative='test/'+task_id
        instruction=record['instruction']+'\n\n精确输入域与验收约定：'+SPECS[i]['domain']+f"\n修复 solution.py 中的 {record['entrypoint']} 函数，保留签名。"
        metadata={'task_id':task_id,'source_id':record['source_id'],'split':'test',
            'entrypoint':record['entrypoint'],'instruction':instruction,
            'domain':SPECS[i]['domain'],'bug_type':chosen['bug_type'],'mutation':chosen['mutation'],
            'source':{'commit':upstream['commit'],'task_id':i,'raw_code_sha256':record['raw_code_sha256'],
                'reference_sha256':record['reference_sha256']},
            'review_status':'agent_reviewed_not_human_signed_off',
            'public_cases':len(public),'private_cases':len(private)}
        assets={'task.json':text(metadata),'starter/solution.py':chosen['source'],
            'reference/solution.py':record['reference'],'public_tests.py':render_public_tests(record['entrypoint'],public),
            'private_tests.json':text(private)}
        resources.update({relative+'/'+name:content for name,content in assets.items()})
        tasks.append({'task_id':task_id,'source_id':record['source_id'],'split':'test',
            'bug_type':chosen['bug_type'],'path':relative})
        reviews.append({'source_id':record['source_id'],'included':True,'reference':reference,
            'chosen_mutation':chosen['mutation'],'rejected_candidates':rejected})
        print('BUILT',task_id,flush=True)
    resources['selection_report.json']=text({'sources':reviews,'models_consulted':False,
        'cohort_sources':50,'included_sources':len(tasks),'excluded_sources':50-len(tasks),
        'replacement_sources_used':False,'human_review_complete':False})
    resources['test_sources.lock.json']=COHORT.read_text()
    manifest={'schema_version':1,'version':'mbpp-repair-test@0.1.0','split':'test',
        'candidate_freeze_sha256':policy['candidate_freeze_sha256'],
        'construction_policy_sha256':sha256(POLICY.read_bytes()),
        'test_source_lock_sha256':sha256(COHORT.read_bytes()),
        'parent_manifest_sha256':sha256((parent_path/'manifest.json').read_bytes()),
        'pipeline_files':{name:sha256((ROOT/name).read_bytes()) for name in PIPELINE},
        'task_counts':{'test':len(tasks)},'source_counts':{'test':len(tasks)},
        'bug_counts':dict(Counter(r['bug_type'] for r in tasks)),
        'tasks':tasks,'files':{name:sha256(value) for name,value in sorted(resources.items())},
        'fixture_references_executed':True,'model_test_executed':False}
    resources['manifest.json']=text(manifest)
    return resources


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--draft',action='store_true',help='Validate authored fixtures; do not write a dataset')
    parser.add_argument('--check',action='store_true',help='Rebuild and compare the frozen dataset')
    args=parser.parse_args()
    resources=build()
    selection=json.loads(resources['selection_report.json'])
    if args.draft:
        (ROOT/'reports/final_test_build_draft.json').write_text(text(selection))
    else:
        current={str(p.relative_to(OUTPUT)) for p in OUTPUT.rglob('*') if p.is_file()}
        if current-set(resources):
            raise ValueError('Unexpected existing asset')
        for name,content in resources.items():
            p=OUTPUT/name
            if p.exists() and p.read_text()!=content:
                raise ValueError('Refusing to overwrite changed dataset: '+name)
            if args.check and not p.exists():
                raise ValueError('Missing frozen asset: '+name)
        if not args.check:
            for name,content in resources.items():
                p=OUTPUT/name;p.parent.mkdir(parents=True,exist_ok=True);p.write_text(content)
    print(json.dumps({'included':selection['included_sources'],'excluded':selection['excluded_sources'],
        'draft_only':args.draft,'model_test_executed':False}))


if __name__=='__main__':
    main()
