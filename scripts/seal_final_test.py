"""Seal test tasks and model identities after fixture-only Docker acceptance."""
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from code_repair.dataset import sha256
from scripts.build_final_test import POLICY, OUTPUT, text


def main():
    validation=json.loads((ROOT/'reports/final_test_docker_validation.json').read_text())
    manifest=json.loads((OUTPUT/'manifest.json').read_text())
    policy=json.loads(POLICY.read_text())
    candidate=json.loads((ROOT/'reports/day11_candidate_freeze.json').read_text())
    dataset_sha=sha256((OUTPUT/'manifest.json').read_bytes())
    if (not validation['complete'] or validation['dataset_manifest_sha256']!=dataset_sha
            or validation['docker_executions']!=len(manifest['tasks'])*4
            or not validation['authenticated_http'] or validation['models_involved']
            or validation['model_test_executed']):
        raise ValueError('Complete fixture-only authenticated Docker verification required')
    if manifest['candidate_freeze_sha256']!=sha256((ROOT/'reports/day11_candidate_freeze.json').read_bytes()) or manifest['construction_policy_sha256']!=sha256(POLICY.read_bytes()):
        raise ValueError('Candidate/policy changed after data construction')
    public=ROOT/'runs/final_test/public_data'
    public_sha=sha256((public/'manifest.json').read_bytes())
    if public_sha!=validation['public_manifest_sha256']:
        raise ValueError('Public export changed')
    public_manifest=json.loads((public/'manifest.json').read_text())
    for base,index in [(OUTPUT,manifest),(public,public_manifest)]:
        for name,expected in index['files'].items():
            if sha256((base/name).read_bytes())!=expected:
                raise ValueError('Frozen test asset changed: '+name)
    frozen_dev=json.loads((ROOT/'runs/day8/evaluation_protocol.json').read_text())
    generation={key:policy[key] for key in ('seeds','temperature','top_p','max_steps','max_prompt_length',
        'max_response_length','episode_timeout','test_timeout','infra_retries','generation_backend')}
    for key in generation:
        if generation[key]!=frozen_dev[key]:
            raise ValueError('Generation protocol differs from dev: '+key)
    protocol={'schema_version':1,'status':'sealed_before_first_model_test',
        'split':'test','purpose':'independent held-out report after dev-only checkpoint selection',
        'candidate_freeze_sha256':manifest['candidate_freeze_sha256'],
        'dataset_manifest_sha256':dataset_sha,'public_manifest_sha256':public_sha,
        'construction_policy_sha256':sha256(POLICY.read_bytes()),
        'cohort_sources':50,'included_sources':len(manifest['tasks']),
        'excluded_sources':50-len(manifest['tasks']),
        'tasks':[{k:r[k] for k in ('task_id','source_id','split')} for r in manifest['tasks']],
        **generation,'core_files_sha256':frozen_dev['core_files_sha256'],
        'test_loader_sha256':sha256((ROOT/'code_repair/final_test.py').read_bytes()),
        'models':{'sft':{'sha256':candidate['sft_baseline_sha256'],'remote_path':'/root/autodl-tmp/agent-r1-day6/runs/day7/sft_warmup/merged'},
            'step70':{'sha256':candidate['merged_model_sha256'],'remote_path':candidate['merged_model_path']}},
        'episodes_per_model':len(manifest['tasks'])*len(policy['seeds']),
        'metric':'mean single-episode strict private acceptance; not best-of-three/pass@3',
        'reporting_unit':'42 distinct original sources; repeated seeds are correlated',
        'report_all_failures':True,'model_failure_resampling':False,
        'use_test_for_further_tuning':False,'model_test_executed_at_seal':False,
        'original_225_update_target_complete':False}
    target=ROOT/'training/final_test/evaluation_protocol.json'
    content=text(protocol)
    if target.exists() and target.read_text()!=content:
        raise ValueError('Refusing to overwrite a different sealed protocol')
    target.write_text(content)
    print(text({'sealed':True,'tasks':len(manifest['tasks']),'episodes_per_model':protocol['episodes_per_model'],
        'models':2,'model_test_executed':False,'protocol_sha256':sha256(content)}))


if __name__=='__main__':
    main()
