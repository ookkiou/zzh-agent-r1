"""Real AgentEnv/HTTP/Docker verification using known train/dev fixtures, never model ability."""

import asyncio
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'runs/day6/Agent-R1')]


async def main():
    from agent_r1.env.base import Action
    from code_repair.agent_r1_env import CodeRepairAgentEnv
    from code_repair.evaluation import RemoteEvaluator
    selection = json.loads((ROOT / 'runs/day7/selection.json').read_text())
    public = ROOT / 'runs/day7/public_data'
    tokenfile = ROOT / 'runs/day6/evaluator_token'
    token = tokenfile.read_text().strip()
    url = 'http://127.0.0.1:8765'
    manifest = json.loads((public / 'manifest.json').read_text())
    health = RemoteEvaluator(url, token, selection['tasks'][0]['task_id']).health()
    if (health['backend'] != 'docker' or not health['container_isolation_configured']
            or manifest['source_manifest_sha256'] not in health['dataset_manifest_sha256']):
        raise ValueError('Expected Docker service for the frozen formal dataset')
    os.environ.update({'CODE_REPAIR_PUBLIC_DATA_DIR': str(public), 'CODE_REPAIR_TOKEN_FILE': str(tokenfile),
                       'CODE_REPAIR_EVALUATOR_URL': url})
    rows = []
    for task in selection['tasks']:
        for repaired in (False, True):
            env = CodeRepairAgentEnv(task['task_id'])
            try:
                env.reset()
                await env.step(Action(text='{"name":"read_file","arguments":{"path":"solution.py"}}'))
                if repaired:
                    record = next(r for r in manifest['tasks'] if r['task_id'] == task['task_id'])
                    # Known, already verified train/dev reference fixture; never shipped to GPU/model observations.
                    source = (ROOT / 'data/mbpp_repair/v0.1' / record['path'] / 'reference/solution.py').read_text()
                    _, _, _, info = await env.step(Action(text=json.dumps({'name': 'write_file',
                        'arguments': {'path': 'solution.py', 'content': source}})))
                await env.step(Action(text='{"name":"run_tests","arguments":{}}'))
                observed, reward, done, info = await env.step(Action(text='{"final":"done"}'))
                if not (done and info['valid_episode'] and reward == float(repaired)):
                    raise ValueError('Fixture adapter reward mismatch')
                if token in json.dumps(observed.messages) or 'private-' in json.dumps(observed.messages):
                    raise ValueError('Control/private material leaked to observations')
                if env.session.environment.workspace.exists():
                    raise ValueError('Episode workspace was not removed')
                rows.append({'task_id': task['task_id'], 'repaired_fixture': repaired,
                             'reward': reward, 'workspace_removed': True})
            finally:
                env.close()
    report = {'complete': True, 'uses_model': False, 'uses_reference_patches': True,
        'actual_agent_r1_env': True, 'backend': 'docker', 'episodes': rows,
        'task_count': len(selection['tasks']), 'episode_count': len(rows), 'day7_complete': False}
    (ROOT / 'reports/day7_docker_adapter.json').write_text(json.dumps(report, indent=2) + '\n')
    print('Actual AgentEnv + HTTP + Docker:', len(rows), 'fixture episodes passed; no model involved')


if __name__ == '__main__':
    asyncio.run(main())
