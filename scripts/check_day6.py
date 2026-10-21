"""Check stored Day-6 GPU evidence without evaluating frozen repair test sources."""

from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]


def main():
    names = ('day6_server_inventory.json', 'day6_preflight.json', 'day6_install_status.json',
        'day6_flash_attn_verification.json', 'day6_model_download_status.json',
        'day6_environment.lock.json', 'day6_model_protocol.json', 'day6_hermes_adapter.json',
        'day6_ray_evaluator_health.json', 'day6_evaluator_failure.json', 'day6_gsm8k_preparation.json',
        'day6_single_smoke_status.json', 'day6_single_checkpoint_verification.json',
        'day6_tool_smoke_status.json', 'day6_tool_checkpoint_verification.json')
    reports = {}
    missing = []
    for name in names:
        path = ROOT / 'reports' / name
        if path.exists():
            reports[name] = json.loads(path.read_text())
        else:
            missing.append(name)
    checks = {'all_required_reports_present': not missing}
    def get(name):
        return reports.get('day6_' + name + '.json', {})
    preflight, model = get('preflight'), get('model_protocol')
    lock = json.loads((ROOT / 'TRAINING_SOURCE_LOCK.json').read_text())
    download = get('model_download_status')
    environment = get('environment.lock')
    freeze = ROOT / 'training/day6/requirements.linux.lock.txt'
    checks.update({
        'linux_gpu_cuda_and_core_imports': preflight.get('preflight_complete') is True
            and all(preflight.get('checks', {}).values()),
        'dependency_install_and_pip_check': get('install_status').get('complete') is True
            and environment.get('pip_check') == 'No broken requirements found.',
        'actual_environment_lock_matches': freeze.exists()
            and hashlib.sha256(freeze.read_bytes()).hexdigest() == environment.get('freeze_sha256'),
        'flash_attention_bf16_gpu_checked': get('flash_attn_verification').get('complete') is True,
        'fixed_model_all_files_verified': download.get('complete') is True
            and download.get('revision') == lock['model']['revision']
            and len(download.get('files', [])) == 9
            and all(row['verified'] for row in download.get('files', [])),
        'genuine_guided_model_three_tool_roundtrip': model.get('complete') is True
            and [s['expected_tool'] for s in model.get('steps', [])] == ['read_file', 'write_file', 'run_tests']
            and all(s['tool_response']['ok'] for s in model.get('steps', []))
            and model.get('credential_absent_from_report') is True,
        'official_hermes_parser_after_explicit_normalization': get('hermes_adapter').get('complete') is True
            and get('hermes_adapter').get('source_model_trace_sha256')
                == (hashlib.sha256((ROOT / 'reports/day6_model_protocol.json').read_bytes()).hexdigest()
                    if model else None),
        'actual_ray_worker_evaluator_reachable': get('ray_evaluator_health').get('complete') is True,
        'unreachable_service_episode_invalid': get('evaluator_failure').get('complete') is True
            and get('evaluator_failure').get('terminal_info', {}).get('valid_episode') is False,
        'official_diagnostic_not_repair_test_data': get('gsm8k_preparation').get('repair_test_sources_used') is False,
    })
    for stage in ('single', 'tool'):
        result = get(stage + '_checkpoint_verification')
        updates = result.get('updates', {})
        checks[stage + '_two_finite_nonzero_updates'] = (
            get(stage + '_smoke_status').get('returncode') == 0 and set(updates) == {'1', '2'}
            and all(row.get('actor/grad_norm', 0) > 0 and all(math.isfinite(v) for v in row.values())
                    for row in updates.values()))
        checks[stage + '_weights_changed_and_checkpoint_reloaded'] = (
            result.get('complete') is True and result.get('weight_comparison', {}).get('changed_elements', 0) > 0
            and result.get('checkpoint_reload', {}).get('nonempty') is True)
    manifest = json.loads((ROOT / 'data/mbpp_repair/v0.1/manifest.json').read_text())
    checks['frozen_repair_pipeline_and_resources_unchanged'] = all(
        hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest
        for name, digest in manifest['pipeline_files'].items()) and all(
        hashlib.sha256((ROOT / 'data/mbpp_repair/v0.1' / name).read_bytes()).hexdigest() == digest
        for name, digest in manifest['files'].items())
    evidence = {'reports/' + name: hashlib.sha256((ROOT / 'reports' / name).read_bytes()).hexdigest()
                for name in names if name not in missing}
    limitations = [
        'Three-tool run is guided, tool order constrained and controller terminated; not an ability benchmark.',
        'The genuine model emits fenced JSON; official Hermes parser was checked after explicit normalization.',
        'Guided repair terminal reward is 0; no repair improvement demonstrated.',
        'Official tool-config training is not evidence that the model autonomously used a tool.',
        'Custom code-repair recipe, baseline, multi-turn training and effectiveness evaluation remain future work.',
        'Checkpoint saves model and extra state; optimizer-state resume is not covered.',
    ]
    tool_log = ROOT / 'reports/day6_tool_smoke.log'
    if tool_log.exists():
        maxima = [float(v) for v in re.findall(r'num_steps/max:([^\s]+)', tool_log.read_text(errors='replace'))]
        if maxima and max(maxima) == 1:
            limitations.append('All logged official tool-config trajectories had one generation step; no multi-turn tool interaction observed.')
    report = {'schema_version': 1, 'stage': 'day6', 'recorded_at': datetime.now(timezone.utc).isoformat(),
        'checks': checks, 'complete': all(checks.values()), 'missing_reports': missing,
        'evidence_sha256': evidence, 'model_ability_improvement_proven': False,
        'code_repair_training_performed': False, 'limitations': limitations}
    (ROOT / 'reports/day6_acceptance.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(f'Day 6 acceptance: {sum(checks.values())}/{len(checks)}; complete={report["complete"]}')
    for name, passed in checks.items():
        if not passed:
            print('PENDING/FAIL', name)
    return 0 if report['complete'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
