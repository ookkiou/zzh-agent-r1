"""Full scripted Docker/HTTP acceptance. No model or final test-set evaluation."""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import secrets
import sys
import threading
import urllib.error

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from code_repair.environment import RepairEnvironment
from code_repair.evaluation import RemoteEvaluator
from code_repair.execution import DockerBackend
from code_repair.service import EvaluationServer, TaskRegistry
from code_repair.tasks import load_task
from verify_episodes import run_scenario


def main():
    image = json.loads((ROOT / 'SANDBOX_LOCK.json').read_text())['image']
    datasets = [ROOT / 'data/prototype', ROOT / 'data/mbpp_repair/v0.1']
    token = secrets.token_urlsafe(48)  # Process memory only, never in reports/traces.
    registry = TaskRegistry(datasets)
    backend = DockerBackend(image)
    checks, reports = {}, []
    with EvaluationServer(('127.0.0.1', 0), registry, backend, token) as server:
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        url = f'http://127.0.0.1:{server.server_port}'
        client = RemoteEvaluator(url, token, 'repair-001')
        try:
            health = client.health()
            checks['docker_service_healthy'] = (health['backend'] == 'docker' and health['image'] == image
                                               and health['task_count'] == 124)
            try:
                RemoteEvaluator(url, 'wrong-' + 'x' * 40, 'repair-001').health()
                checks['unauthorized_rejected'] = False
            except urllib.error.HTTPError as error:
                checks['unauthorized_rejected'] = error.code == 401

            for dataset in datasets:
                manifest_bytes = (dataset / 'manifest.json').read_bytes()
                manifest = json.loads(manifest_bytes)
                rows = []
                for item in manifest['tasks']:
                    directory = dataset / item['path']
                    trace_root = ROOT / 'runs/docker-service-episodes' / dataset.name
                    kwargs = {'service_url': url, 'token': token, 'trace_root': trace_root}
                    original = run_scenario(directory, None, repair=False, **kwargs)
                    repaired = run_scenario(directory, None, repair=True, **kwargs)
                    valid = original['valid'] and repaired['valid']
                    rows.append({'task_id': item['task_id'], 'original': original, 'repaired': repaired, 'valid': valid})
                    print(f'{len(rows)}/{len(manifest["tasks"])} {item["task_id"]}: {"PASS" if valid else "FAIL"}', flush=True)
                reports.append({'dataset': str(dataset.relative_to(ROOT)),
                                'manifest_sha256': hashlib.sha256(manifest_bytes).hexdigest(),
                                'tasks': rows, 'total_tasks': len(rows), 'total_episodes': 2 * len(rows),
                                'valid_tasks': sum(row['valid'] for row in rows)})

            directory = datasets[0] / 'train/repair-001'
            reference = (directory / 'reference/solution.py').read_text()
            def concurrent_episode(repair):
                task = load_task(directory, include_private=False)
                with RepairEnvironment(task, evaluator=RemoteEvaluator(url, token, task.task_id)) as env:
                    workspace = env.workspace
                    if repair:
                        env.step({'name': 'write_file', 'arguments': {'path': 'solution.py', 'content': reference}})
                    public = env.step({'name': 'run_tests', 'arguments': {}})
                    terminal = env.step({'final': 'scripted acceptance'})
                    serialized = json.dumps([env.observation(), env.trace])
                    private_result = RemoteEvaluator(url, token, task.task_id).check(task.starter_source, 'private')
                    result = {'expected_reward': float(repair), 'reward': terminal.reward,
                              'public_failed': public.tool_response['output']['failed'],
                              'valid_episode': terminal.info['valid_episode'],
                              'repeat_reward': env.step({'final': 'repeat'}).reward,
                              'public_only_client': not task.private_cases,
                              'no_private_material_in_trace': all(value not in serialized for value in
                                  (token, 'private-01', 'private_tests.json')),
                              'private_response_minimized': set(private_result) == {
                                  'status', 'tests', 'passed', 'failed', 'timed_out', 'elapsed_seconds'}}
                result['workspace_removed'] = not workspace.exists()
                return result
            with ThreadPoolExecutor(max_workers=4) as pool:
                concurrent = list(pool.map(concurrent_episode, (True, False, False, True)))
            checks['parallel_episodes_independent'] = all(
                row['reward'] == row['expected_reward'] and row['repeat_reward'] == 0
                and row['valid_episode'] and (row['public_failed'] == 0) == bool(row['expected_reward'])
                and row['workspace_removed'] for row in concurrent)
            checks['private_material_kept_server_side'] = all(
                row['public_only_client'] and row['no_private_material_in_trace'] and row['private_response_minimized']
                for row in concurrent)
            checks['all_scripted_episodes_passed'] = all(row['valid_tasks'] == row['total_tasks'] for row in reports)
        finally:
            server.shutdown()
            thread.join(timeout=5)
    report = {'schema_version': 1, 'verified_at': datetime.now(timezone.utc).isoformat(),
              'backend': 'remote-docker', 'image': image, 'uses_model': False, 'uses_reference_patches': True,
              'public_only_client': True, 'datasets': reports, 'parallel_episodes': concurrent,
              'checks': checks, 'total_tasks': sum(row['total_tasks'] for row in reports),
              'total_episodes': sum(row['total_episodes'] for row in reports) + len(concurrent),
              'complete': all(checks.values())}
    (ROOT / 'reports/service_verification.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(f'Service acceptance: complete={report["complete"]}; {report["total_episodes"]} episodes', flush=True)
    return 0 if report['complete'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
