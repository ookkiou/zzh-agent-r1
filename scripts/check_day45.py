"""Verify stored real-container evidence and rerun the complete regression suite."""

import hashlib
import json
import os
from pathlib import Path
import shutil
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    lock = json.loads((ROOT / 'SANDBOX_LOCK.json').read_text())
    if not shutil.which('docker') or os.environ.get('CODE_REPAIR_DOCKER_IMAGE') != lock['image']:
        raise SystemExit('Set PATH and CODE_REPAIR_DOCKER_IMAGE from SANDBOX_LOCK.json; Docker test must not skip')
    sandbox = json.loads((ROOT / 'reports/sandbox_verification.json').read_text())
    service = json.loads((ROOT / 'reports/service_verification.json').read_text())
    suite = unittest.defaultTestLoader.discover(str(ROOT / 'tests'))
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    manifests_current = all(
        hashlib.sha256((ROOT / item['dataset'] / 'manifest.json').read_bytes()).hexdigest() == item['manifest_sha256']
        for item in service['datasets'])
    rows = [task for dataset in service['datasets'] for task in dataset['tasks']]
    checks = {
        'real_docker_isolation': sandbox['complete'] and all(sandbox['checks'].values()),
        'digest_pinned_same_image': sandbox['image'] == service['image'] == lock['image'],
        'all_124_tasks_covered': len(rows) == service['total_tasks'] == 124,
        'correct_patches_reward_one': all(row['repaired']['valid'] and row['repaired']['reward'] == 1 for row in rows),
        'wrong_patches_reward_zero': all(row['original']['valid'] and row['original']['reward'] == 0 for row in rows),
        'no_duplicate_rewards': all(row[scenario]['repeated_terminal_reward'] == 0 for row in rows
                                    for scenario in ('original', 'repaired')),
        'workspaces_removed': all(row[scenario]['workspace_removed'] for row in rows for scenario in ('original', 'repaired')),
        'parallel_isolation': service['checks']['parallel_episodes_independent'],
        'private_material_server_side': service['checks']['private_material_kept_server_side'],
        'authenticated_service': service['checks']['unauthorized_rejected'],
        'service_acceptance_complete': service['complete'] and all(service['checks'].values()),
        'dataset_manifests_unchanged': manifests_current,
        'regression_suite_no_skips': result.wasSuccessful() and not result.skipped and result.testsRun >= 60,
        'model_free_acceptance': service['uses_model'] is False and service['uses_reference_patches'] is True,
    }
    evidence = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in
                ('SANDBOX_LOCK.json', 'reports/sandbox_verification.json', 'reports/service_verification.json')}
    report = {'schema_version': 1, 'stage': 'days4-5', 'checks': checks, 'evidence_sha256': evidence,
              'regression': {'tests': result.testsRun, 'failures': len(result.failures), 'errors': len(result.errors),
                             'skipped': len(result.skipped)},
              'complete': all(checks.values()), 'uses_gpu': False, 'uses_model': False}
    (ROOT / 'reports/day45_acceptance.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(f'Days 4-5 acceptance: {sum(checks.values())}/{len(checks)}; complete={report["complete"]}')
    return 0 if report['complete'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
