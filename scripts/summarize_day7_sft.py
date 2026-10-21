"""Audit bounded SFT and paired diagnostics without replacing original-model evidence."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    def read(name):
        return json.loads((ROOT / 'reports' / name).read_text())
    base = read('day7_model_diagnostics.json')
    original_acceptance = read('day7_acceptance.json')
    teacher = read('day7_sft_data.json')
    warmup = read('day7_sft_warmup.json')
    sft = read('day7_sft_diagnostics.json')
    protocol = read('day7_protocol_comparison.json')
    backup = read('day7_sft_backup.json')
    selection_path = ROOT / 'runs/day7/selection.json'
    selection = json.loads(selection_path.read_text())
    preparation = read('day7_data_preparation.json')
    expected = {(r['task_id'], seed) for r in selection['tasks'] for seed in selection['seeds']}
    actual = {(r['task_id'], r['seed']) for r in sft['episodes']}
    raw = (ROOT / 'runs/day7/sft_warmup/train.jsonl').read_bytes()
    rows = [json.loads(line) for line in raw.splitlines()]
    excluded = {r['source_id'] for r in selection['tasks']}
    errors, tools, hashes, trace_checks = Counter(), Counter(), {}, []
    for row in sft['episodes']:
        path = ROOT / 'runs/day7/diagnostic_sft' / (row['task_id'] + '-' + str(row['seed']) + '.json')
        trace = json.loads(path.read_text())
        trace_checks.append(trace['summary'] == row and len(trace['steps']) == row['steps'])
        hashes[str(path.relative_to(ROOT))] = hashlib.sha256(path.read_bytes()).hexdigest()
        for step in trace['steps']:
            action, result = step['action'], step['tool_response']
            if action and 'name' in action:
                tools['requested/' + action['name']] += 1
                if result and result['ok']:
                    tools['successful/' + action['name']] += 1
            if result and not result['ok']:
                errors[result['error']['code']] += 1
    import math
    checks = {
        'original_diagnostic_execution_passed': original_acceptance['diagnostic_execution_complete'],
        'same_frozen_diagnostic_selection': hashlib.sha256(selection_path.read_bytes()).hexdigest() == preparation['selection_sha256'],
        'train_only_source_disjoint_supervision': all(r['split'] == 'train' and r['source_id'] not in excluded for r in rows),
        'supervision_hash_matches_training': hashlib.sha256(raw).hexdigest() == teacher['dataset_sha256'] == warmup['teacher_data_sha256'],
        'all_teachers_docker_validated': teacher['complete'] and teacher['all_teacher_trajectories_docker_reward_one'],
        'exactly_80_finite_nonzero_updates': len(warmup['updates']) == 80 and all(math.isfinite(r['loss']) and math.isfinite(r['grad_norm']) and r['grad_norm'] > 0 for r in warmup['updates']),
        'changed_weights_and_gpu_reload': warmup['complete'] and bool(warmup['changed_q_projection_tensors']) and bool(warmup['checkpoint_gpu_reload_generated_text'].strip()),
        'paired_32_autonomous_valid_attempts': sft['complete'] and sft['model_kind'] == 'SFT-only' and not sft['guided'] and actual == expected and len(sft['episodes']) == 32 and all(r['valid_episode'] for r in sft['episodes']),
        'all_post_sft_traces_consistent': len(trace_checks) == 32 and all(trace_checks),
        'eight_post_sft_groups': len(sft['groups']) == 8 and all(len(g['rewards']) == 4 for g in sft['groups']),
    }
    signal = sft['train']['mixed_reward_groups'] > 0
    report = {'recorded_at': datetime.now(timezone.utc).isoformat(), 'checks': checks,
        'diagnostic_and_sft_execution_complete': all(checks.values()),
        'complete': all(checks.values()) and signal and protocol['complete'],
        'ready_for_grpo_smoke': all(checks.values()) and signal and protocol['complete'],
        'protocol_and_initial_prompt_token_equality_verified': protocol['complete'],
        'adapter_backup_verified': backup['complete'],
        'train_group_reward_variation_present': signal,
        'sft_training_performed': True, 'code_repair_grpo_performed': False,
        'base': {k: base[k] for k in ('train', 'dev')},
        'sft_only': {k: sft[k] for k in ('train', 'dev')},
        'sft_tool_counts': dict(tools), 'sft_error_counts': dict(errors),
        'trace_sha256': hashes,
        'next_step_decision': ('Full dev Base/SFT-only baselines, then bounded custom GRPO smoke.' if signal else 'Do not start GRPO with zero-variance groups; inspect remaining autonomous errors and training-task difficulty.'),
        'limitations': ['Eight-source diagnostic sample only; no full dev or final test result.',
            'Supervision includes train repair labels as well as tool formatting; gains cannot be attributed to GRPO.',
            'Transformers diagnostics and scripted real trainer tensor probe do not prove vLLM multi-turn optimization.',
            'Merged model weights remain on remote data disk; exact LoRA adapter is backed up locally.']}
    (ROOT / 'reports/day7_sft_acceptance.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps({k: report[k] for k in ('checks','complete','ready_for_grpo_smoke','base','sft_only','sft_tool_counts','sft_error_counts','next_step_decision')},indent=2))


if __name__ == '__main__':
    main()
