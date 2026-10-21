"""Local preparation acceptance only; never marks the whole Day-7 GPU stage complete."""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    suite = unittest.defaultTestLoader.discover(str(ROOT / 'tests'), pattern='test_agent_adapter.py')
    result = unittest.TextTestRunner(verbosity=1).run(suite)
    prepared = json.loads((ROOT / 'reports/day7_data_preparation.json').read_text())
    bundle = json.loads((ROOT / 'reports/day7_bundle.json').read_text())
    docker = json.loads((ROOT / 'reports/day7_docker_adapter.json').read_text())
    selection = json.loads((ROOT / 'runs/day7/selection.json').read_text())
    frozen = json.loads((ROOT / 'data/mbpp_repair/v0.1/manifest.json').read_text())
    checks = {'adapter_tests_pass_no_skips': result.wasSuccessful() and not result.skipped and result.testsRun >= 13,
        'public_104_tasks_exported': prepared['local_export_complete'] and prepared['exported_tasks'] == 104
            and not prepared['private_resources_exported'],
        'eight_distinct_diagnostic_sources': len(selection['tasks']) == 8
            and len({row['source_id'] for row in selection['tasks']}) == 8
            and all(sum(r['split'] == split for r in selection['tasks']) == 4 for split in ('train', 'dev')),
        'selection_frozen_before_model_results': hashlib.sha256((ROOT / 'runs/day7/selection.json').read_bytes()).hexdigest()
            == prepared['selection_sha256'],
        'real_agentenv_docker_fixture_roundtrip': docker['complete'] and docker['actual_agent_r1_env']
            and docker['episode_count'] == 16 and docker['uses_model'] is False,
        'bundle_bytes_verified': bundle['complete'] and hashlib.sha256((ROOT / bundle['archive']).read_bytes()).hexdigest()
            == bundle['sha256'] and not bundle['contains_credentials'] and not bundle['contains_private_or_reference_resources'],
        'frozen_pipeline_unchanged': all(hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == digest
            for name, digest in frozen['pipeline_files'].items()),
        'test_sources_not_executed_or_exported': prepared['repair_test_sources_executed'] is False,
    }
    report = {'recorded_at': datetime.now(timezone.utc).isoformat(), 'local_preparation_complete': all(checks.values()),
        'day7_complete': False, 'checks': checks,
        'tests': {'run': result.testsRun, 'failures': len(result.failures), 'errors': len(result.errors), 'skips': len(result.skipped)},
        'gpu_diagnostics_performed': False, 'learning_signal_verified': False,
        'remaining': ['actual pinned trainer tensor path on Linux', 'original model autonomous train/dev diagnostics',
                      'format/reward distribution and SFT decision from real outputs']}
    (ROOT / 'reports/day7_local_acceptance.json').write_text(json.dumps(report, indent=2) + '\n')
    print('Day 7 local preparation:', sum(checks.values()), '/', len(checks), report['local_preparation_complete'])
    return 0 if report['local_preparation_complete'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
