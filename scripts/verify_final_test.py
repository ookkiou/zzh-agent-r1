"""Independently verify held-out data, then run known fixtures through HTTP and Docker."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
import os
from pathlib import Path
import secrets
import sys
import threading

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from code_repair.contracts import validate_candidate_source
from code_repair.dataset import sha256, normalize_record, source_features, near_duplicate, render_public_tests
from code_repair.execution import DockerBackend
from code_repair.evaluation import RemoteEvaluator
from code_repair.final_test import FinalTestRegistry, load_final_public_task, PUBLIC_KEYS, verified_asset
from code_repair.service import EvaluationServer, TaskRegistry
from code_repair.tasks import load_task
from scripts.build_mbpp import reviewed_cases
from scripts.build_final_test import OUTPUT, POLICY, COHORT, PIPELINE, text
from scripts.fetch_mbpp import DESTINATION, verify_snapshot
from scripts.mbpp_test_specs import SPECS, EXCLUSIONS
from scripts.verify_mbpp import validate_single_mutation


def static_verify():
    verify_snapshot()
    manifest=json.loads((OUTPUT/'manifest.json').read_text())
    digest=sha256((OUTPUT/'manifest.json').read_bytes())
    policy=json.loads(POLICY.read_text())
    cohort=json.loads(COHORT.read_text())
    candidate=ROOT/'reports/day11_candidate_freeze.json'
    if manifest['construction_policy_sha256']!=sha256(POLICY.read_bytes()) or manifest['candidate_freeze_sha256']!=sha256(candidate.read_bytes()) or policy['candidate_freeze_sha256']!=sha256(candidate.read_bytes()):
        raise ValueError('Candidate/policy not frozen before test')
    if manifest['test_source_lock_sha256']!=sha256(COHORT.read_bytes()) or (OUTPUT/'test_sources.lock.json').read_bytes()!=COHORT.read_bytes():
        raise ValueError('Frozen test cohort changed')
    if set(manifest['pipeline_files'])!=set(PIPELINE):
        raise ValueError('Missing build provenance')
    for name,expected in manifest['pipeline_files'].items():
        if sha256((ROOT/name).read_bytes())!=expected:
            raise ValueError('Build pipeline changed after construction')
    declared=set(manifest['files'])|{'manifest.json'}
    if {str(p.relative_to(OUTPUT)) for p in OUTPUT.rglob('*') if p.is_file()}!=declared:
        raise ValueError('Missing/extra held-out asset')
    for name in manifest['files']:
        verified_asset(OUTPUT,name,manifest['files'])
    parent=ROOT/'data/mbpp_repair/v0.2'
    old=json.loads((parent/'manifest.json').read_text())
    if manifest['parent_manifest_sha256']!=sha256((parent/'manifest.json').read_bytes()):
        raise ValueError('Development manifest changed')
    for name,expected in old['files'].items():
        if sha256((parent/name).read_bytes())!=expected:
            raise ValueError('Development asset changed')
    sources={r['source_id'] for r in manifest['tasks']}
    if len(sources)!=len(manifest['tasks']) or sources & {r['source_id'] for r in old['tasks']}:
        raise ValueError('Duplicate source or overlap with development')
    allowed={r['source_id']:r for r in cohort['sources']}
    if not sources.issubset(allowed):
        raise ValueError('Source outside frozen test cohort')
    raw={r['task_id']:r for r in map(json.loads,(DESTINATION/'mbpp.jsonl').read_text().splitlines())}
    signatures={}
    for row in old['tasks']:
        signatures[row['source_id']]=source_features((parent/row['path']/'reference/solution.py').read_text())
    proto=ROOT/'data/prototype'
    for row in json.loads((proto/'manifest.json').read_text())['tasks']:
        signatures['prototype:'+row['task_id']]=source_features((proto/row['path']/'reference/solution.py').read_text())
    for row in manifest['tasks']:
        i=allowed[row['source_id']]['upstream_task_id']
        record=normalize_record(raw[i])
        if i not in SPECS or i in EXCLUSIONS or record['split']!='test' or row['task_id']!=record['source_id']+'-t01' or row['path']!='test/'+row['task_id']:
            raise ValueError('Unreviewed/invalid test source')
        directory=OUTPUT/row['path']
        metadata=json.loads((directory/'task.json').read_text())
        task=load_task(directory)
        reference=(directory/'reference/solution.py').read_text()
        if reference!=record['reference'] or metadata['source']['raw_code_sha256']!=record['raw_code_sha256']:
            raise ValueError('Reference/upstream provenance changed')
        for key in ('source_id','raw_code_sha256','reference_sha256'):
            if record[key]!=allowed[row['source_id']][key]:
                raise ValueError('Frozen source identity changed')
        if any(metadata[k]!=row[k] for k in ('task_id','source_id','split','bug_type')):
            raise ValueError('Test index/metadata mismatch')
        public,private=reviewed_cases(record,SPECS[i])
        if (directory/'public_tests.py').read_text()!=render_public_tests(record['entrypoint'],public) or list(task.private_cases)!=private:
            raise ValueError('Cases differ from independently authored expectations')
        if {json.dumps(c['args'],sort_keys=True) for c in public} & {json.dumps(c['args'],sort_keys=True) for c in private}:
            raise ValueError('Public/private input overlap')
        validate_candidate_source(task.starter_source,reference,task.entrypoint)
        validate_single_mutation(reference,task.starter_source,metadata['mutation'])
        features=source_features(reference)
        for source,other in signatures.items():
            if near_duplicate(features,other):
                raise ValueError('Near-duplicate held-out source: '+source)
        signatures[row['source_id']]=features
    selection=json.loads((OUTPUT/'selection_report.json').read_text())
    reviewed={r['source_id'] for r in selection['sources']}
    if reviewed!=set(allowed) or {r['source_id'] for r in selection['sources'] if r['included']}!=sources:
        raise ValueError('Incomplete cohort inclusion/exclusion accounting')
    if manifest['task_counts']!={'test':len(sources)} or manifest['source_counts']!={'test':len(sources)}:
        raise ValueError('Incorrect task/source counts')
    try:
        TaskRegistry([OUTPUT])
    except ValueError:
        pass
    else:
        raise ValueError('Default train/dev registry unexpectedly accepts test')
    return manifest,digest,selection


def export_public(manifest,digest):
    output=ROOT/'runs/final_test/public_data'
    resources={}
    for row in manifest['tasks']:
        directory=OUTPUT/row['path']
        metadata=json.loads((directory/'task.json').read_text())
        resources[row['path']+'/task.json']=text({k:metadata[k] for k in ('task_id','source_id','split','entrypoint','instruction')})
        for name in ('starter/solution.py','public_tests.py'):
            resources[row['path']+'/'+name]=(directory/name).read_text()
    public={'schema_version':1,'split':'test','source_manifest_sha256':digest,
        'candidate_freeze_sha256':manifest['candidate_freeze_sha256'],
        'tasks':[{k:v for k,v in r.items() if k!='bug_type'} for r in manifest['tasks']],
        'files':{name:sha256(content) for name,content in sorted(resources.items())}}
    resources['manifest.json']=text(public)
    if {str(p.relative_to(output)) for p in output.rglob('*') if p.is_file()}-set(resources):
        raise ValueError('Unexpected existing public export')
    for name,content in resources.items():
        p=output/name
        if p.exists() and p.read_text()!=content:
            raise ValueError('Refusing to overwrite different public test export')
        p.parent.mkdir(parents=True,exist_ok=True);p.write_text(content)
    public_sha=sha256((output/'manifest.json').read_bytes())
    for row in manifest['tasks']:
        load_final_public_task(output,row['task_id'],public_sha)
    return public_sha,len(resources)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--static-only',action='store_true')
    args=parser.parse_args()
    manifest,digest,selection=static_verify()
    report={'complete':False,'static_checks_passed':True,'dataset_manifest_sha256':digest,
        'candidate_freeze_sha256':manifest['candidate_freeze_sha256'],
        'construction_policy_sha256':manifest['construction_policy_sha256'],
        'cohort_sources':50,'included_sources':len(manifest['tasks']),
        'excluded_sources':selection['excluded_sources'],'train_dev_unchanged':True,
        'source_disjointness_verified':True,'single_location_mutations_verified':True,
        'private_public_cases_separate':True,'default_train_dev_loader_still_rejects_test':True,
        'models_involved':False,'model_test_executed':False,
        'fixture_test_references_executed':not args.static_only,
        'human_review_complete':False,'docker_executions':0}
    if args.static_only:
        (ROOT/'reports/final_test_static_validation.json').write_text(text(report))
        print(text(report));return
    os.environ['PATH']='/Applications/Docker.app/Contents/Resources/bin:'+os.environ.get('PATH',os.defpath)
    image=json.loads((ROOT/'SANDBOX_LOCK.json').read_text())['image']
    registry=FinalTestRegistry(OUTPUT,digest,[r['task_id'] for r in manifest['tasks']])
    token=secrets.token_urlsafe(48)
    rows=[]
    with EvaluationServer(('127.0.0.1',0),registry,DockerBackend(image),token,test_timeout=10,concurrency=4) as server:
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        url='http://127.0.0.1:'+str(server.server_port)
        def check(row):
            directory=OUTPUT/row['path'];task=load_task(directory)
            client=RemoteEvaluator(url,token,task.task_id)
            results={}
            for kind,source in [('reference',(directory/'reference/solution.py').read_text()),('starter',task.starter_source)]:
                for mode in ('public','private'):
                    results[kind+'/'+mode]=client.check(source,mode,timeout=10)
            valid=all(r['status']=='completed' and (r['failed']==0 if k.startswith('reference/') else r['failed']>0) for k,r in results.items())
            return {'task_id':task.task_id,'valid':valid,'results':results}
        try:
            health=RemoteEvaluator(url,token,manifest['tasks'][0]['task_id']).health()
            if health['backend']!='docker' or digest not in health['dataset_manifest_sha256']:
                raise ValueError('Docker test service identity mismatch')
            report['health']=health
            with ThreadPoolExecutor(max_workers=4) as pool:
                futures=[pool.submit(check,row) for row in manifest['tasks']]
                for future in as_completed(futures):
                    row=future.result();rows.append(row)
                    print('DOCKER',len(rows),'/',len(manifest['tasks']),row['task_id'],row['valid'],flush=True)
        finally:
            server.shutdown();thread.join(timeout=10)
    report.update({'tasks':sorted(rows,key=lambda r:r['task_id']),'docker_executions':len(rows)*4,
        'backend':'docker','image':image,'authenticated_http':True,
        'complete':len(rows)==len(manifest['tasks']) and all(r['valid'] for r in rows)})
    if report['complete']:
        public_sha,count=export_public(manifest,digest)
        report.update({'public_manifest_sha256':public_sha,'public_export_files':count,
            'reference_code_exported':False,'private_cases_exported':False,'mutation_metadata_exported':False})
    (ROOT/'reports/final_test_docker_validation.json').write_text(text(report))
    print(text({k:v for k,v in report.items() if k!='tasks'}))
    if not report['complete']:
        raise SystemExit(1)


if __name__=='__main__':
    main()
