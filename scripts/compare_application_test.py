"""Audit and compare paired application test results without changing old reports."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
from prepare_application_test import DEFAULT_APP, PROTOCOL, digest, verify, write_json, validate_identity
from code_repair.agent_protocol import parse_action
from code_repair.contracts import ContractError, validate_tool_call


def validate_report(report, recipe, stage, *, require_complete=True):
    expected = {(row['task_id'], seed) for row in recipe['tasks'] for seed in recipe['seeds']}
    sources = {row['task_id']: row['source_id'] for row in recipe['tasks']}
    inputs = report['inputs']
    if (inputs['protocol_sha256'] != digest(PROTOCOL) or inputs['scope'] != 'test'
            or inputs['stage'] != stage or inputs['model_sha256'] != recipe['models'][stage]['sha256']
            or inputs['model_path'] != recipe['models'][stage]['remote_path']
            or not report['final_test'] or report['scripted_fixture'] or report['training_performed']
            or report['expected_episodes'] != len(expected) or report['fresh_blind_test']):
        raise ValueError('Changed application test identity')
    episodes = report['episodes']
    table = {(e['task_id'], e['seed']): e for e in episodes}
    if len(table) != len(episodes) or not set(table).issubset(expected):
        raise ValueError('Duplicate or unexpected episode')
    if (require_complete or report['complete']) and (not report['complete'] or set(table) != expected):
        raise ValueError('Incomplete application test coverage')
    for e in episodes:
        if (e['source_id'] != sources[e['task_id']] or e['split'] != 'test' or not e['final_test']
                or e['profile'] != recipe['profile'] or e['backend'] != recipe['backend']
                or e['model'] != 'zzh-repair-' + stage or not e['terminal']['valid_episode']
                or e['reward'] not in (0, 1)):
            raise ValueError('Invalid episode, source or model identity')
        if (not 1 <= e['decisions'] <= recipe['max_steps']
                or len(e['trace']) != e['decisions']
                or len(e['prompt_tokens']) != e['decisions']
                or len(e['response_tokens']) != e['decisions']
                or any(not 0 < n <= recipe['max_prompt_length'] for n in e['prompt_tokens'])
                or any(not 0 < n <= recipe['max_response_length'] for n in e['response_tokens'])):
            raise ValueError('Decision or token budget changed')
        acceptance = e['terminal']['acceptance']
        passed = (acceptance is not None and acceptance['status'] == 'completed'
            and acceptance['failed'] == 0 and acceptance['tests'] > 0
            and e['terminal']['termination_reason'] != 'episode_timeout')
        if bool(e['reward']) != passed:
            raise ValueError('Reward does not match private terminal acceptance')
        for trace in e['trace']:
            try:
                action, parsed = parse_action(trace['model_text']), True
            except ValueError:
                action, parsed = None, False
            valid = parsed
            if parsed and 'name' in action:
                try:
                    validate_tool_call(action['name'], action['arguments'])
                except ContractError:
                    valid = False
            if action != trace['action'] or parsed != trace['parsed'] or valid != trace['contract_valid']:
                raise ValueError('Raw action or contract accounting mismatch')
    if report['complete'] and report.get('successes') != sum(e['reward'] == 1 for e in episodes):
        raise ValueError('Saved success count differs from episodes')
    return table


def summarize(recipe, reports):
    tables = {stage: validate_report(reports[stage], recipe, stage) for stage in ('sft', 'step70')}
    for field in ('inference_url', 'evaluator_url', 'initial_prompts_sha256'):
        if reports['sft']['inputs'][field] != reports['step70']['inputs'][field]:
            raise ValueError('Paired application environment/tokenizer differs')
    keys = set(tables['sft'])
    counts = {s: sum(e['reward'] == 1 for e in table.values()) for s, table in tables.items()}
    metrics = {s: {'successes': counts[s], 'episodes': len(keys),
        'invalid_attempts': len(reports[s]['invalid_attempts']),
        'invalid_model_actions': sum(not t['contract_valid'] for e in table.values() for t in e['trace']),
        'decisions': sum(e['decisions'] for e in table.values()),
        'prompt_tokens': sum(sum(e['prompt_tokens']) for e in table.values()),
        'response_tokens': sum(sum(e['response_tokens']) for e in table.values()),
        'episode_seconds': sum(e['elapsed_seconds'] for e in table.values()),
        'termination_reasons': dict(Counter(e['terminal']['termination_reason'] for e in table.values()))}
        for s, table in tables.items()}
    improved = sum(tables['sft'][k]['reward'] == 0 and tables['step70'][k]['reward'] == 1 for k in keys)
    regressed = sum(tables['sft'][k]['reward'] == 1 and tables['step70'][k]['reward'] == 0 for k in keys)
    return {'complete': True, 'split': 'test', 'profile': recipe['profile'], 'backend': recipe['backend'],
        'protocol_sha256': digest(PROTOCOL), 'task_count': len(recipe['tasks']),
        'included_sources': recipe['included_sources'], 'excluded_sources': recipe['excluded_sources'],
        'episodes_per_model': len(keys), 'sft_successes': counts['sft'], 'step70_successes': counts['step70'],
        'sft_success_rate': counts['sft'] / len(keys), 'step70_success_rate': counts['step70'] / len(keys),
        'delta_percentage_points': 100 * (counts['step70'] - counts['sft']) / len(keys),
        'paired_improved': improved, 'paired_regressed': regressed,
        'paired_both_success': sum(tables['sft'][k]['reward'] == tables['step70'][k]['reward'] == 1 for k in keys),
        'paired_both_failure': sum(tables['sft'][k]['reward'] == tables['step70'][k]['reward'] == 0 for k in keys),
        'by_seed': {str(seed): {s: sum(e['reward'] == 1 for (task, sd), e in table.items() if sd == seed)
            for s, table in tables.items()} for seed in recipe['seeds']},
        'metrics': metrics, 'fresh_blind_test': False, 'test_results_previously_observed': True,
        'statistical_significance_evaluated': False, 'training_performed': False,
        'formal_225_updates_complete': False, 'caveat': recipe['caveat']}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--zzhclaw-repo', type=Path, default=DEFAULT_APP)
    args = parser.parse_args()
    recipe = verify(args.zzhclaw_repo.resolve())
    paths = {s: ROOT / 'reports' / f'application_test_{s}.json' for s in ('sft', 'step70')}
    reports = {s: json.loads(p.read_text()) for s, p in paths.items()}
    result = summarize(recipe, reports)
    identities = {s: json.loads((ROOT / 'runs/application_test' / f'model-{s}.json').read_text()) for s in reports}
    for stage, identity in identities.items():
        if validate_identity(identity, recipe, stage) != reports[stage]['inputs']['initial_prompts_sha256']:
            raise ValueError('Model receipt differs from the evaluated tokenizer identity')
    if identities['sft']['initial_test_prompts'] != identities['step70']['initial_test_prompts']:
        raise ValueError('Paired offline tokenizer fingerprints differ')
    if identities['sft']['generation_config'] != identities['step70']['generation_config']:
        raise ValueError('Paired model generation defaults differ')
    result['source_reports_sha256'] = {s: digest(p) for s, p in paths.items()}
    result['checked_at'] = datetime.now(timezone.utc).isoformat()
    write_json(ROOT / 'reports/application_test_comparison.json', result)
    write_json(ROOT / 'reports/application_test_acceptance.json', {
        'complete': True, 'protocol_sha256': digest(PROTOCOL),
        'comparison_sha256': digest(ROOT / 'reports/application_test_comparison.json'),
        'valid_episodes': 2 * recipe['episodes_per_model'], 'training_performed': False,
        'fresh_blind_test': False, 'checks': ['frozen_source_data_models_and_code',
            'complete_unique_paired_coverage', 'valid_infrastructure', 'budgets',
            'raw_actions_and_terminal_rewards', 'paired_metrics_and_seeds',
            'matching_offline_tokenizer_fingerprints', 'original_reports_unchanged']})
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
