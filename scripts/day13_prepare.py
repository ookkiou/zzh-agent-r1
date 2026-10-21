"""Freeze the application migration recipe and verify local preparation (no GPU)."""
import argparse
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
APP_FILES = ['zzhclaw/agent/repair.py','zzhclaw/agent/repair_cli.py',
    'zzhclaw/agent/core.py','zzhclaw/coding/session/manager.py','zzhclaw/__main__.py']
LOCAL_FILES = ['scripts/day13_serve_model.py','scripts/run_zzhclaw_repair.py',
               'scripts/compare_zzhclaw_repair.py']
PROTOCOL = ROOT/'training/integration/evaluation_protocol.json'


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build(app):
    old_path = ROOT/'runs/day8/evaluation_protocol.json'
    if digest(old_path) != '078b36f56a85e1ef800da548ba042e7296fe6e79cb3b10dfb3c2d492f3338635':
        raise ValueError('Original dev protocol changed')
    old = json.loads(old_path.read_text())
    if digest(ROOT/'runs/day9/public_data/manifest.json') != '59eb1edb9c7f7ce19e0afa9c441a868d251ba7c704938e620a6584a2fd18c196':
        raise ValueError('Public export changed')
    for name, sha in old['core_files_sha256'].items():
        if digest(ROOT/name) != sha:
            raise ValueError('Shared repair runtime changed: '+name)
    if digest(ROOT/'reports/day11_candidate_freeze.json') != 'ce5af7ebbcdb850d5e5e9951224acf365a27336ec6cd8e81bfc09702d84d3822':
        raise ValueError('Step70 candidate freeze changed')
    manifest = json.loads((ROOT/'runs/day9/public_data/manifest.json').read_text())
    for name, sha in manifest['files'].items():
        if digest(ROOT/'runs/day9/public_data'/name) != sha:
            raise ValueError('Public asset changed: '+name)
    smoke, sources = [], set()
    for row in old['tasks']:
        if row['source_id'] not in sources and len(smoke)<2:
            smoke.append(row['task_id'])
            sources.add(row['source_id'])
    return {'schema_version':1,'profile':'code-repair-v1','candidate_step':70,
        'split':'dev','final_test':False,'training_performed':False,
        'purpose':'ZzhClaw application migration, separate from the frozen Transformers evaluation',
        'backend':'vllm-0.11-token-completions','dtype':'bfloat16',
        'max_steps':6,'max_prompt_length':4096,'max_response_length':512,
        'episode_timeout':240,'test_timeout':10,'temperature':0.6,'top_p':0.95,
        'top_k':20,'repetition_penalty':1.1,'stop_token_ids':[151645,151643],
        'seed_rule':'episode_seed + zero_based_decision_index',
        'seeds':old['seeds'],'tasks':old['tasks'],'smoke_tasks':smoke,
        'public_manifest_sha256':digest(ROOT/'runs/day9/public_data/manifest.json'),
        'dataset_manifest_sha256':manifest['source_manifest_sha256'],
        'original_dev_protocol_sha256':digest(old_path),
        'candidate_freeze_sha256':digest(ROOT/'reports/day11_candidate_freeze.json'),
        'model_sha256':json.loads((ROOT/'reports/final_test_eval_inputs.json').read_text())['model_sha256'],
        'core_files_sha256':old['core_files_sha256'],
        'app_files_sha256':{name:digest(app/name) for name in APP_FILES},
        'local_files_sha256':{name:digest(ROOT/name) for name in LOCAL_FILES},
        'migration_caveat':'Backend and random stream differ from Transformers; both app models use this same recipe',
        'metric':'96 valid single episodes per model; not pass@3; repeated seeds are correlated'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--zzhclaw-repo',type=Path,default=Path('/Users/zzh/Documents/GitHub/zzhclaw'))
    parser.add_argument('--freeze',action='store_true',help='Create the protocol once; never overwrite')
    args = parser.parse_args()
    recipe = build(args.zzhclaw_repo.resolve())
    if args.freeze and not PROTOCOL.exists():
        PROTOCOL.parent.mkdir(parents=True,exist_ok=True)
        with PROTOCOL.open('x') as stream:
            stream.write(json.dumps(recipe,ensure_ascii=False,indent=2)+'\n')
    if not PROTOCOL.exists() or json.loads(PROTOCOL.read_text()) != recipe:
        raise ValueError('Migration protocol missing/changed; do not silently refreeze an existing experiment')
    local = json.loads((ROOT/'reports/day13_local_profile_acceptance.json').read_text())
    if not local['complete'] or local['profile_sha256']!=recipe['app_files_sha256']['zzhclaw/agent/repair.py']:
        raise ValueError('Current profile lacks local Docker acceptance')
    smoke_path = ROOT/'reports/day13_step70_smoke.json'
    real_api = False
    if smoke_path.exists():
        smoke = json.loads(smoke_path.read_text())
        expected = {(task,recipe['seeds'][0]) for task in recipe['smoke_tasks']}
        observed = {(row['task_id'],row['seed']) for row in smoke['episodes']}
        real_api = bool(smoke['complete'] and smoke['inputs']['protocol_sha256']==digest(PROTOCOL)
            and smoke['inputs']['stage']=='step70' and smoke['inputs']['scope']=='smoke'
            and smoke['inputs']['model_sha256']==recipe['model_sha256']['step70']
            and len(smoke['episodes'])==len(expected) and observed==expected
            and not smoke['scripted_fixture'] and not smoke['final_test']
            and all(row['terminal']['valid_episode'] and 1<=row['decisions']<=6
                and len(row['prompt_tokens'])==row['decisions']
                and len(row['response_tokens'])==row['decisions']
                and all(0<n<=4096 for n in row['prompt_tokens'])
                and all(0<n<=512 for n in row['response_tokens']) for row in smoke['episodes']))
        if not real_api:
            raise ValueError('Existing real-model smoke does not match the current migration protocol')
        acceptance = {'complete':True,'protocol_sha256':digest(PROTOCOL),
            'source_report_sha256':digest(smoke_path),'valid_episodes':len(smoke['episodes']),
            'successes':sum(row['reward']==1 for row in smoke['episodes']),
            'invalid_attempts':len(smoke['invalid_attempts']),
            'all_observed_actions_contract_valid':all(t['contract_valid'] for row in smoke['episodes'] for t in row['trace']),
            'initial_token_fingerprint_checked_by_frozen_runner':True,
            'model_inference_performed':True,'training_performed':False,'final_test':False,
            'scope':'API integration smoke, not an ability comparison',
            'finished_at':smoke['finished_at']}
        (ROOT/'reports/day13_real_api_acceptance.json').write_text(json.dumps(acceptance,indent=2)+'\n')
    paired_complete = False
    audit_path = ROOT/'reports/day14_acceptance.json'
    if audit_path.exists():
        audit = json.loads(audit_path.read_text())
        paired_complete = bool(audit['complete'] and audit['protocol_sha256']==digest(PROTOCOL)
            and audit['comparison_sha256']==digest(ROOT/'reports/day14_application_comparison.json')
            and all(audit['metrics'][stage]['source_report_sha256']==digest(ROOT/'reports'/f'day13_{stage}_dev.json')
                for stage in ('sft','step70')))
        if not paired_complete:
            raise ValueError('Existing application acceptance is stale; re-run check_day14.py')
    report = {'local_preparation_complete':True,'protocol_sha256':digest(PROTOCOL),
        'zzhclaw_repo':str(args.zzhclaw_repo.resolve()),'unit_and_regression_tests':51,
        'real_http_and_docker_scripted_check_complete':True,
        'real_model_api_check_complete':real_api,'paired_application_dev_complete':paired_complete,
        'day13_14_complete':bool(real_api and paired_complete),
        'acceptance_scope':'restricted CLI repair profile and paired application dev migration',
        'model_weights_download_required':False,
        'test_reexecuted':False,'training_performed':False}
    (ROOT/'reports/day13_preparation.json').write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(report,ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
