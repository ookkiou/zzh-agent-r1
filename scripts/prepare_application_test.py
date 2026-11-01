"""Freeze the existing test cohort for a separate ZzhClaw/vLLM migration report."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
from day13_prepare import APP_FILES, build as build_dev
from code_repair.final_test import load_final_public_task

PROTOCOL = ROOT / 'training/application_test/evaluation_protocol.json'
ORIGINAL_TEST = ROOT / 'training/final_test/evaluation_protocol.json'
DEV_PROTOCOL = ROOT / 'training/integration/evaluation_protocol.json'
PUBLIC = ROOT / 'runs/final_test/public_data'
DEFAULT_APP = Path('/Users/zzh/Documents/GitHub/zzhclaw')
TEST_PROFILE = 'zzhclaw/agent/repair_test.py'
LOCAL_FILES = ['scripts/prepare_application_test.py', 'scripts/run_application_test.py',
               'scripts/serve_application_test.py', 'scripts/compare_application_test.py']
ORIGINAL_TEST_SHA = '4b5fde7d02ac238d26fc4ed4cebcbb4d882ddfc0e85a530ab333cadc311742eb'


def digest(path):
    sha = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            sha.update(chunk)
    return sha.hexdigest()


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2, allow_nan=False) + '\n')
    temporary.replace(path)


def validate_resources(recipe):
    if digest(ORIGINAL_TEST) != ORIGINAL_TEST_SHA:
        raise ValueError('Original Transformers test protocol changed')
    old = json.loads(ORIGINAL_TEST.read_text())
    for field in ('tasks', 'seeds', 'dataset_manifest_sha256', 'public_manifest_sha256',
                  'candidate_freeze_sha256', 'core_files_sha256', 'models'):
        if recipe[field] != old[field]:
            raise ValueError('Application test differs from frozen test: ' + field)
    if digest(ROOT / 'reports/day11_candidate_freeze.json') != recipe['candidate_freeze_sha256']:
        raise ValueError('Original candidate freeze changed')
    if digest(PUBLIC / 'manifest.json') != recipe['public_manifest_sha256']:
        raise ValueError('Public test export changed')
    manifest = json.loads((PUBLIC / 'manifest.json').read_text())
    if manifest['source_manifest_sha256'] != recipe['dataset_manifest_sha256']:
        raise ValueError('Wrong test dataset export')
    rows = [{k: row[k] for k in ('task_id', 'source_id', 'split')} for row in manifest['tasks']]
    if rows != recipe['tasks'] or len(rows) != 42 or len({r['source_id'] for r in rows}) != 42:
        raise ValueError('Expected the existing 42 distinct test sources')
    expected_files = set(manifest['files']) | {'manifest.json'}
    actual_files = {str(p.relative_to(PUBLIC)) for p in PUBLIC.rglob('*') if p.is_file()}
    if actual_files != expected_files:
        raise ValueError('Unexpected/private file in public test export')
    for row in rows:
        load_final_public_task(PUBLIC, row['task_id'], recipe['public_manifest_sha256'])
    for name, sha in recipe['core_files_sha256'].items():
        if digest(ROOT / name) != sha:
            raise ValueError('Frozen runtime changed: ' + name)
    if digest(ROOT / 'code_repair/final_test.py') != old['test_loader_sha256']:
        raise ValueError('Frozen test loader changed')
    for name, sha in recipe['local_files_sha256'].items():
        if digest(ROOT / name) != sha:
            raise ValueError('Application test implementation changed: ' + name)
    for name, sha in recipe['prior_reports_sha256'].items():
        if digest(ROOT / name) != sha:
            raise ValueError('Prior experiment changed: ' + name)


def build(app):
    dev = json.loads(DEV_PROTOCOL.read_text())
    if build_dev(app) != dev:
        raise ValueError('Original application dev implementation changed')
    if digest(app / TEST_PROFILE) != digest(ROOT / 'integrations/zzhclaw/repair_test.py'):
        raise ValueError('Test entry point differs from the published integration source')
    old = json.loads(ORIGINAL_TEST.read_text())
    fields = ('dtype', 'max_steps', 'max_prompt_length', 'max_response_length',
              'episode_timeout', 'test_timeout', 'temperature', 'top_p', 'top_k',
              'repetition_penalty', 'stop_token_ids', 'seed_rule')
    recipe = {k: dev[k] for k in fields}
    for field in ('tasks', 'seeds', 'dataset_manifest_sha256', 'public_manifest_sha256',
                  'candidate_freeze_sha256', 'core_files_sha256', 'models'):
        recipe[field] = old[field]
    recipe.update(schema_version=1, profile='code-repair-v1', split='test',
        backend=dev['backend'], candidate_step=70, training_performed=False,
        purpose='Application-backend transfer on the existing held-out test cohort',
        test_results_previously_observed=True, fresh_blind_test=False,
        use_test_for_tuning=False, model_failure_resampling=False,
        original_test_protocol_sha256=digest(ORIGINAL_TEST),
        original_application_dev_protocol_sha256=digest(DEV_PROTOCOL),
        cohort_sources=50, included_sources=42, excluded_sources=8,
        episodes_per_model=126, model_order=['sft', 'step70'],
        app_files_sha256={name: digest(app / name) for name in APP_FILES + [TEST_PROFILE]},
        local_files_sha256={name: digest(ROOT / name) for name in LOCAL_FILES},
        prior_reports_sha256={name: digest(ROOT / name) for name in (
            'reports/final_test_eval_comparison.json', 'reports/day14_application_comparison.json')},
        metric='126 valid single episodes per model; not pass@3; repeated seeds are correlated',
        infra_policy='Persist invalid attempts and abort; resume unfinished task/seed without resampling valid failures',
        caveat='Same existing test cohort, new application/backend evaluation; not a new blind test or proof of general capability')
    validate_resources(recipe)
    return recipe


def verify(app):
    recipe = json.loads(PROTOCOL.read_text())
    if build(app) != recipe:
        raise ValueError('Frozen application test recipe changed; do not overwrite this experiment')
    return recipe


def validate_identity(identity, recipe, stage):
    model = recipe['models'][stage]
    prompts = identity['initial_test_prompts']
    if (identity['protocol_sha256'] != digest(PROTOCOL) or identity['stage'] != stage
            or identity['model_path'] != model['remote_path'] or identity['model_sha256'] != model['sha256']
            or identity['helper_sha256'] != recipe['local_files_sha256']['scripts/serve_application_test.py']
            or identity['vllm_version'] != '0.11.0'
            or set(prompts) != {row['task_id'] for row in recipe['tasks']}
            or identity['core_files_sha256'] != recipe['core_files_sha256']):
        raise ValueError('Remote model/helper/tokenizer identity mismatch')
    defaults = identity['generation_config']
    if (defaults.get('top_k') != recipe['top_k'] or defaults.get('repetition_penalty') != recipe['repetition_penalty']
            or defaults.get('eos_token_id') != recipe['stop_token_ids']):
        raise ValueError('Model generation defaults changed')
    return hashlib.sha256(json.dumps(prompts, sort_keys=True).encode()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--zzhclaw-repo', type=Path, default=DEFAULT_APP)
    parser.add_argument('--freeze', action='store_true')
    args = parser.parse_args()
    recipe = build(args.zzhclaw_repo.resolve())
    if args.freeze and not PROTOCOL.exists():
        PROTOCOL.parent.mkdir(parents=True, exist_ok=True)
        with PROTOCOL.open('x') as stream:
            stream.write(json.dumps(recipe, ensure_ascii=False, indent=2) + '\n')
    if not PROTOCOL.exists() or json.loads(PROTOCOL.read_text()) != recipe:
        raise ValueError('Application test protocol missing/changed')
    result = {'local_preparation_complete': True, 'protocol_sha256': digest(PROTOCOL),
        'tasks': 42, 'episodes_per_model': 126, 'total_episodes': 252,
        'test_results_previously_observed': True, 'fresh_blind_test': False,
        'application_test_complete': False, 'model_inference_performed': False,
        'training_performed': False}
    write_json(ROOT / 'reports/application_test_preparation.json', result)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
