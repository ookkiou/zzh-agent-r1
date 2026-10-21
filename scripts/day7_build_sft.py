"""Build supervised tool trajectories from validated TRAIN references only, excluding diagnostics."""

import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from code_repair.agent_session import RepairSession
from code_repair.evaluation import RemoteEvaluator
from code_repair.public_data import load_public_task


def main():
    public = ROOT / 'runs/day7/public_data'
    manifest = json.loads((public / 'manifest.json').read_text())
    selection = json.loads((ROOT / 'runs/day7/selection.json').read_text())
    excluded = {row['source_id'] for row in selection['tasks']}
    rows = [row for row in manifest['tasks'] if row['split'] == 'train' and row['source_id'] not in excluded]
    token = (ROOT / 'runs/day6/evaluator_token').read_text().strip()
    url = 'http://127.0.0.1:8765'
    health = RemoteEvaluator(url, token, rows[0]['task_id']).health()
    if health['backend'] != 'docker' or manifest['source_manifest_sha256'] not in health['dataset_manifest_sha256']:
        raise ValueError('Expected formal Docker evaluator')
    examples = []
    for row in rows:
        task = load_public_task(public, row['task_id'])
        reference = ROOT / 'data/mbpp_repair/v0.1' / row['path'] / 'reference/solution.py'
        source = reference.read_text()
        actions = [{'name': 'read_file', 'arguments': {'path': 'solution.py'}},
            {'name': 'read_file', 'arguments': {'path': 'public_tests.py'}},
            {'name': 'write_file', 'arguments': {'path': 'solution.py', 'content': source}},
            {'name': 'run_tests', 'arguments': {}}, {'final': 'done'}]
        session = RepairSession(task, RemoteEvaluator(url, token, task.task_id))
        trajectory = []
        session.reset()
        try:
            for index, action in enumerate(actions):
                text = json.dumps(action, ensure_ascii=False)
                trajectory.append({'task_id': task.task_id, 'source_id': row['source_id'], 'split': 'train',
                    'step_index': index, 'messages': session.observation(), 'response': text})
                result = session.step(text)
                if result.tool_response is not None and not result.tool_response['ok']:
                    raise ValueError('Known TRAIN reference trajectory rejected')
            if not result.done or not result.info['valid_episode'] or result.reward != 1:
                raise ValueError('TRAIN reference did not pass terminal Docker acceptance')
            examples.extend(trajectory)
            print('Validated TRAIN teacher', task.task_id, flush=True)
        finally:
            session.close()
    content = ''.join(json.dumps(row, ensure_ascii=False) + '\n' for row in examples)
    if token in content:
        raise ValueError('Credential leak in supervision')
    directory = ROOT / 'runs/day7/sft_warmup'
    directory.mkdir(exist_ok=True)
    path = directory / 'train.jsonl'
    path.write_text(content)
    report = {'complete': True, 'uses_reference_patches_as_train_labels': True, 'split': 'train',
        'dev_or_test_labels_used': False, 'diagnostic_sources_excluded': sorted(excluded),
        'task_count': len(rows), 'source_count': len({r['source_id'] for r in rows}), 'rows': len(examples),
        'source_ids': sorted({r['source_id'] for r in rows}), 'dataset_sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
        'all_teacher_trajectories_docker_reward_one': True,
        'scope': 'tool-use and repair supervision, not pure format-only supervision; SFT-only comparison required'}
    (ROOT / 'reports/day7_sft_data.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
