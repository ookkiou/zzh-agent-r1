"""Scripted test-entry HTTP/Docker fixtures; never count these as model results."""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
import tempfile
import threading

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
from prepare_application_test import DEFAULT_APP, PROTOCOL, PUBLIC, digest, verify, write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--zzhclaw-repo', type=Path, default=DEFAULT_APP)
    args = parser.parse_args()
    app = args.zzhclaw_repo.resolve()
    recipe = verify(app)
    sys.path.insert(0, str(app))
    from code_repair.evaluation import RemoteEvaluator
    from code_repair.final_test import load_final_public_task
    from zzhclaw.agent.repair import VllmRepairTransport
    from zzhclaw.agent.repair_test import ApplicationTestRepairAgent
    from zzhclaw.coding.session import SessionManager
    row = recipe['tasks'][0]  # Fixed diagnostic choice, not a model-based selection.
    task = load_final_public_task(PUBLIC, row['task_id'], recipe['public_manifest_sha256'])
    token = (ROOT / 'runs/day6/evaluator_token').read_text().strip()
    evaluator = RemoteEvaluator('http://127.0.0.1:8766', token, task.task_id)
    health = evaluator.health()
    if (health.get('backend') != 'docker' or not health.get('container_isolation_configured')
            or recipe['dataset_manifest_sha256'] not in health.get('dataset_manifest_sha256', [])):
        raise ValueError('Wrong/nonisolated test evaluator')
    reference = (ROOT / 'data/mbpp_repair/test-v0.1/test' / task.task_id / 'reference/solution.py').read_text()
    state = {'texts': [], 'text': '', 'requests': 0}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass

        def do_POST(self):
            data = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            state['requests'] += 1
            if self.path == '/tokenize':
                if len(data['tools']) != 3 or token in json.dumps(data):
                    raise ValueError('Unexpected scripted prompt')
                result = {'tokens': [1, 2], 'count': 2, 'max_model_len': 4608}
            elif self.path == '/v1/completions':
                state['text'] = state['texts'].pop(0)
                result = {'choices': [{'token_ids': [3], 'text': state['text'], 'finish_reason': 'stop'}]}
            elif self.path == '/detokenize':
                result = {'prompt': state['text']}
            else:
                self.send_error(404)
                return
            body = json.dumps(result).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(body)))
            self.end_headers()
            self.wfile.write(body)

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    results = []
    try:
        with tempfile.TemporaryDirectory(prefix='zzh-test-fixture-') as directory:
            for label, source, expected in [('unchanged', task.starter_source, 0), ('known_reference', reference, 1)]:
                state['texts'] = [json.dumps({'name': 'read_file', 'arguments': {'path': 'solution.py'}}),
                    json.dumps({'name': 'write_file', 'arguments': {'path': 'solution.py', 'content': source}}),
                    '{"name":"run_tests","arguments":{}}', '{"final":"done"}']
                agent = ApplicationTestRepairAgent(task, evaluator, VllmRepairTransport(
                    f'http://127.0.0.1:{server.server_port}', 'scripted-fixture-not-a-model'),
                    task_split='test', test_task_ids={r['task_id'] for r in recipe['tasks']},
                    session_manager=SessionManager(directory))
                events = []
                agent.run(on_event=events.append)
                result = agent.last_result
                if (result['reward'] != expected or not result['terminal']['valid_episode']
                        or result['decisions'] != 4 or not result['final_test'] or result['split'] != 'test'
                        or token in json.dumps(result)
                        or not any(e['event_type'] == 'tool_result' for e in events)):
                    raise ValueError('Scripted application test HTTP/Docker acceptance failed: ' + json.dumps({
                        'fixture': label, 'reward': result['reward'], 'expected': expected,
                        'decisions': result['decisions'], 'terminal': result['terminal'],
                        'actions_valid': [t['contract_valid'] for t in result['trace']],
                        'tool_errors': [t['tool_response'].get('error') for t in result['trace'] if t['tool_response']]}))
                results.append({'fixture': label, 'reward': result['reward'], 'decisions': result['decisions'],
                    'terminal': result['terminal'], 'application_session_persisted': bool(agent.list_sessions())})
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)
    result = {'complete': True, 'protocol_sha256': digest(PROTOCOL), 'scripted_fixture': True,
        'model_inference_performed': False, 'application_model_test_complete': False,
        'test_dataset_used': True, 'diagnostic_task': task.task_id, 'real_docker': True,
        'real_http_transport': True, 'token_ids_are_scripted_fixture_ids': True,
        'test_profile_sha256': digest(app / 'zzhclaw/agent/repair_test.py'),
        'http_requests': state['requests'], 'episodes': results, 'training_performed': False}
    write_json(ROOT / 'reports/application_test_local_acceptance.json', result)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
