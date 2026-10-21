"""Summarize genuine diagnostic traces; a completed run is distinct from a learning-signal pass."""

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    path = ROOT / 'reports/day7_model_diagnostics.json'
    model = json.loads(path.read_text())
    selection_path = ROOT / 'runs/day7/selection.json'
    selection = json.loads(selection_path.read_text())
    preparation = json.loads((ROOT / 'reports/day7_data_preparation.json').read_text())
    local = json.loads((ROOT / 'reports/day7_local_acceptance.json').read_text())
    host = json.loads((ROOT / 'reports/day7_host_preflight.json').read_text())
    tensor = json.loads((ROOT / 'reports/day7_trainer_contract.json').read_text())
    counters, errors, reasons = Counter(), Counter(), Counter()
    trace_checks, trace_hashes = [], {}
    for row in model['episodes']:
        trace_path = ROOT / 'runs/day7/diagnostic' / (row['task_id'] + '-' + str(row['seed']) + '.json')
        trace = json.loads(trace_path.read_text())
        trace_hashes[str(trace_path.relative_to(ROOT))] = hashlib.sha256(trace_path.read_bytes()).hexdigest()
        trace_checks.append(trace['summary'] == row and len(trace['steps']) == row['steps'])
        reasons[row['termination_reason']] += 1
        for step in trace['steps']:
            if not step['parsed']:
                counters['unparseable_model_decisions'] += 1
            action = step['action']
            if action and 'name' in action:
                counters['requested/' + action['name']] += 1
            result = step['tool_response']
            if result and result['ok'] and action and 'name' in action:
                counters['successful/' + action['name']] += 1
            elif result and not result['ok']:
                errors[result['error']['code']] += 1
    expected = {(r['task_id'], seed) for r in selection['tasks'] for seed in selection['seeds']}
    actual = {(r['task_id'], r['seed']) for r in model['episodes']}
    checks = {
        'local_adapter_and_docker_acceptance': local['local_preparation_complete'],
        'linux_gpu_stack_checks': host['preflight_complete'],
        'actual_trainer_response_mask_contract': tensor['complete'] and tensor['actual_pinned_agent_r1_tensor_path'],
        'autonomous_original_model_not_training': model.get('guided') is False and model['training_performed'] is False,
        'fixed_selection_unchanged': hashlib.sha256(selection_path.read_bytes()).hexdigest() == preparation['selection_sha256'],
        'all_32_selected_attempts_complete': model['complete'] and actual == expected and len(model['episodes']) == 32,
        'all_traces_available_and_consistent': len(trace_checks) == 32 and all(trace_checks),
        'all_attempts_valid_infrastructure': len(model['episodes']) == 32 and all(r['valid_episode'] for r in model['episodes']),
        'eight_reward_groups_recorded': len(model['groups']) == 8 and all(len(g['rewards']) == 4 for g in model['groups']),
        'train_group_reward_variation_present': model.get('learning_signal_present_in_train') is True,
    }
    execution_complete = all(v for k, v in checks.items() if k != 'train_group_reward_variation_present')
    signal = checks['train_group_reward_variation_present']
    decision = ('Proceed to full dev baseline and bounded custom GRPO smoke after reviewing traces.' if signal
        else 'Do not start formal GRPO. Inspect protocol/tool failures; prepare supervised tool trajectories if exploration is insufficient. Keep SFT-only comparison.')
    report = {'recorded_at': datetime.now(timezone.utc).isoformat(), 'checks': checks,
        'diagnostic_execution_complete': execution_complete, 'complete': all(checks.values()),
        'ready_for_grpo_smoke': execution_complete and signal, 'training_performed': False,
        'full_dev_baseline': False, 'model_ability_improvement_proven': False,
        'train': model.get('train'), 'dev': model.get('dev'),
        'tool_counts': dict(counters), 'error_counts': dict(errors), 'termination_counts': dict(reasons),
        'next_step_decision': decision, 'trace_sha256': trace_hashes,
        'limitations': ['Eight-source diagnostics only, not complete dev/test evaluation.',
            'Model generation uses Transformers; real Agent-R1 tensor path tested separately with scripted actions.',
            'No code-repair optimizer updates or post-training improvement claimed.']}
    (ROOT / 'reports/day7_acceptance.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: report[k] for k in ('diagnostic_execution_complete', 'complete', 'train', 'dev',
        'tool_counts', 'error_counts', 'next_step_decision')}, indent=2))


if __name__ == '__main__':
    main()
