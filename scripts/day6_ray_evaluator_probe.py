"""Check evaluator reachability from an actual local Ray worker; no candidate execution."""

import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    import ray
    ray.init(num_cpus=1, include_dashboard=False, runtime_env={'env_vars': {'PYTHONPATH': str(ROOT)}})
    try:
        @ray.remote(num_cpus=1)
        def health():
            from code_repair.evaluation import RemoteEvaluator
            token = (ROOT / 'runs/day6/evaluator_token').read_text().strip()
            return RemoteEvaluator('http://127.0.0.1:18765', token, 'repair-001').health()
        result = ray.get(health.remote(), timeout=45)
        report = {'complete': result.get('status') == 'ok', 'actual_ray_worker': True, 'health': result}
        (ROOT / 'reports/day6_ray_evaluator_health.json').write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps(report))
    finally:
        ray.shutdown()


if __name__ == '__main__':
    main()
