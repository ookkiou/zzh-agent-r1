"""Verify real transport failure is invalid infrastructure, never a valid failure reward."""

import json
from pathlib import Path
import socket
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    from code_repair.environment import RepairEnvironment
    from code_repair.evaluation import RemoteEvaluator
    from code_repair.tasks import load_task
    # Reserve an unused loopback port with no listening server, giving a real connection refusal.
    with socket.socket() as reserved:
        reserved.bind(('127.0.0.1', 0))
        port = reserved.getsockname()[1]
        task = load_task(ROOT / 'data/day6-public-task', include_private=False)
        token = (ROOT / 'runs/day6/evaluator_token').read_text().strip()
        evaluator = RemoteEvaluator('http://127.0.0.1:' + str(port), token, task.task_id)
        with RepairEnvironment(task, evaluator=evaluator, max_steps=2, test_timeout=1) as environment:
            result = environment.step({'name': 'run_tests', 'arguments': {}})
            report = {'complete': (result.done and result.info['valid_episode'] is False
                and result.info['termination_reason'] == 'infrastructure_error'),
                'probe': 'real connection refusal at reserved non-listening loopback port',
                'active_tunnel_interrupted': False, 'terminal_reward': result.reward, 'terminal_info': result.info}
    (ROOT / 'reports/day6_evaluator_failure.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))
    return 0 if report['complete'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
