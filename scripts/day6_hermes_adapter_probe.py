"""Replay genuine model requests through strict JSON normalization and official Hermes parser."""

import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'runs/day6/Agent-R1'))
sys.path.insert(0, str(ROOT / 'scripts'))


def main():
    from agent_r1.env.tool_format import HermesFormatWrapper
    from code_repair.environment import RepairEnvironment
    from code_repair.evaluation import RemoteEvaluator
    from code_repair.tasks import load_task
    from day6_model_probe import parse_model_tool_call
    raw = ROOT / 'reports/day6_model_protocol.json'
    model_report = json.loads(raw.read_text())
    if not model_report['complete']:
        raise SystemExit('Completed genuine model protocol trace required')
    task = load_task(ROOT / 'data/day6-public-task', include_private=False)
    token = (ROOT / 'runs/day6/evaluator_token').read_text().strip()
    evaluator = RemoteEvaluator('http://127.0.0.1:18765', token, task.task_id)
    report = {'complete': False, 'is_replay': True, 'new_model_generation': False,
              'native_hermes_generation_verified': False,
              'source_model_trace_sha256': hashlib.sha256(raw.read_bytes()).hexdigest(), 'steps': []}
    with RepairEnvironment(task, evaluator=evaluator, max_steps=6, test_timeout=15) as environment:
        for row in model_report['steps']:
            action, wire_format = parse_model_tool_call(row['generated_text'])
            canonical = '<tool_call>' + json.dumps(action, allow_nan=False) + '</tool_call>'
            _, calls = HermesFormatWrapper().parse_response(canonical)
            if len(calls) != 1 or calls[0].name != action['name'] or calls[0].arguments != action['arguments']:
                raise SystemExit('Hermes normalization changed request semantics')
            result = environment.step({'name': calls[0].name, 'arguments': calls[0].arguments})
            report['steps'].append({'tool': calls[0].name, 'native_wire_format': wire_format,
                                    'official_hermes_parser_roundtrip': True,
                                    'tool_response_ok': result.tool_response['ok']})
        result = environment.step({'final': 'Protocol adapter replay complete.'})
        report['terminal_reward'] = result.reward
        report['terminal_info'] = result.info
        report['complete'] = result.info['valid_episode'] and all(s['tool_response_ok'] for s in report['steps'])
    (ROOT / 'reports/day6_hermes_adapter.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
