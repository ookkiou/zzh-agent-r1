"""Scripted HTTP -> ZzhClaw -> unchanged repair runner -> real Docker check.

Uses a known dev reference ONLY for integration diagnostics, never a model score.
No GPU, final test or remote inference service is accessed.
"""
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
import tempfile
import threading

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    from code_repair.evaluation import RemoteEvaluator
    from code_repair.public_data import load_public_task
    from zzhclaw.agent.repair import CodeRepairAgent, VllmRepairTransport
    from zzhclaw.coding.session import SessionManager
    task = load_public_task(ROOT/'runs/day9/public_data', 'mbpp-526-m01')
    reference = (ROOT/'data/mbpp_repair/v0.2/dev/mbpp-526-m01/reference/solution.py').read_text()
    token = (ROOT/'runs/day6/evaluator_token').read_text().strip()
    evaluator = RemoteEvaluator('http://127.0.0.1:8765',token,task.task_id)
    health = evaluator.health()
    if (health.get('backend')!='docker' or not health.get('container_isolation_configured')
            or '37b846babd6d9949e2247752042c3669d618d0f367212b65ba32e39717da9555'
                not in health.get('dataset_manifest_sha256',[])):
        raise ValueError('Expected isolated v0.2 Docker service')
    state = {'texts':[], 'text':'', 'requests':0}
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass
        def do_POST(self):
            data = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            state['requests'] += 1
            if self.path == '/tokenize':
                if len(data['tools']) != 3 or 'Authorization' in json.dumps(data):
                    raise ValueError('Invalid public prompt')
                result = {'tokens':[1,2], 'count':2, 'max_model_len':4608}
            elif self.path == '/v1/completions':
                state['text'] = state['texts'].pop(0)
                result = {'choices':[{'token_ids':[3], 'text':state['text'], 'finish_reason':'stop'}]}
            elif self.path == '/detokenize':
                result = {'prompt':state['text']}
            else:
                self.send_error(404)
                return
            body = json.dumps(result).encode()
            self.send_response(200)
            self.send_header('Content-Type','application/json')
            self.send_header('Content-Length',str(len(body)))
            self.end_headers()
            self.wfile.write(body)
    server = ThreadingHTTPServer(('127.0.0.1',0),Handler)
    worker = threading.Thread(target=server.serve_forever,daemon=True)
    worker.start()
    rows = []
    def action(name, **arguments):
        return json.dumps({'name':name,'arguments':arguments})
    try:
        with tempfile.TemporaryDirectory(prefix='zzh-repair-sessions-') as directory:
            for label, source, expected in [('unchanged',task.starter_source,0),('known_reference',reference,1)]:
                state['texts'] = [action('read_file',path='solution.py'),
                    action('write_file',path='solution.py',content=source),action('run_tests'),'{"final":"done"}']
                agent = CodeRepairAgent(task,evaluator,VllmRepairTransport(
                    'http://127.0.0.1:'+str(server.server_port),'scripted-http-fixture'),
                    task_split='dev',session_manager=SessionManager(directory))
                events = []
                agent.run(on_event=events.append)
                result = agent.last_result
                if result['reward']!=expected or not result['terminal']['valid_episode'] or result['decisions']!=4:
                    raise ValueError('Unexpected scripted Docker result')
                if token in json.dumps(result) or not any(e['event_type']=='tool_result' for e in events):
                    raise ValueError('Missing application events or credential in result')
                rows.append({'fixture':label,'reward':result['reward'],'decisions':result['decisions'],
                    'terminal':result['terminal'],'zzhclaw_session_persisted':bool(agent.list_sessions())})
    finally:
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)
    report = {'complete':True,'scripted_fixture':True,'model_inference_performed':False,
        'training_performed':False,'final_test_executed':False,'real_docker':True,
        'real_http_transport':True,'token_ids_are_scripted_fixture_ids':True,
        'episodes':rows,'http_requests':state['requests'],
        'profile_sha256':hashlib.sha256(Path(sys.modules['zzhclaw.agent.repair'].__file__).read_bytes()).hexdigest()}
    (ROOT/'reports/day13_local_profile_acceptance.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__ == '__main__':
    main()
