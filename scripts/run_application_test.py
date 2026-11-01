"""Run the frozen application test through ZzhClaw and the real vLLM API."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
from prepare_application_test import DEFAULT_APP, PROTOCOL, PUBLIC, digest, verify, validate_identity


def save(path, report, token):
    content = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + '\n'
    if token in content:
        raise ValueError('Credential in application test report')
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(content)
    temporary.replace(path)


def prompt_digest(ids):
    return hashlib.sha256(json.dumps(ids, separators=(',', ':')).encode()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', choices=('sft', 'step70'), required=True)
    parser.add_argument('--zzhclaw-repo', type=Path, default=DEFAULT_APP)
    parser.add_argument('--inference-url', default='http://127.0.0.1:18000')
    parser.add_argument('--evaluator-url', default='http://127.0.0.1:8766')
    parser.add_argument('--execute', action='store_true', help='Otherwise check inputs and API only')
    args = parser.parse_args()
    app = args.zzhclaw_repo.resolve()
    recipe = verify(app)
    sys.path.insert(0, str(app))
    from code_repair.agent_session import InfrastructureUnavailable
    from code_repair.evaluation import RemoteEvaluator
    from code_repair.final_test import load_final_public_task
    from zzhclaw.agent.repair import VllmRepairTransport
    from zzhclaw.agent.repair_test import ApplicationTestRepairAgent
    from zzhclaw.coding.session import SessionManager
    if Path(sys.modules['zzhclaw.agent.repair_test'].__file__).resolve() != app / 'zzhclaw/agent/repair_test.py':
        raise ValueError('Unexpected application installation')
    identity = json.loads((ROOT / 'runs/application_test' / f'model-{args.stage}.json').read_text())
    prompts = identity['initial_test_prompts']
    task_ids = {row['task_id'] for row in recipe['tasks']}
    model = recipe['models'][args.stage]
    prompts_sha = validate_identity(identity, recipe, args.stage)
    local = json.loads((ROOT / 'reports/application_test_local_acceptance.json').read_text())
    if (not local['complete'] or not local['real_docker'] or not local['real_http_transport']
            or local['protocol_sha256'] != digest(PROTOCOL)
            or local['test_profile_sha256'] != recipe['app_files_sha256']['zzhclaw/agent/repair_test.py']):
        raise ValueError('The frozen application test entry lacks local HTTP/Docker acceptance')
    alias = 'zzh-repair-' + args.stage
    transport = VllmRepairTransport(args.inference_url, alias)
    with transport.opener.open(args.inference_url.rstrip('/') + '/v1/models', timeout=10) as response:
        models = json.load(response)['data']
    if len(models) != 1 or models[0]['id'] != alias or models[0].get('root') != model['remote_path']:
        raise ValueError('Active API is not serving the verified model')
    token = (ROOT / 'runs/day6/evaluator_token').read_text().strip()
    health = RemoteEvaluator(args.evaluator_url, token, recipe['tasks'][0]['task_id']).health()
    if (health.get('backend') != 'docker' or not health.get('container_isolation_configured')
            or health.get('task_count') != len(task_ids)
            or recipe['dataset_manifest_sha256'] not in health.get('dataset_manifest_sha256', [])):
        raise ValueError('Expected authenticated, isolated final-test evaluator')
    inputs = {'protocol_sha256': digest(PROTOCOL), 'stage': args.stage, 'scope': 'test',
        'model_sha256': model['sha256'], 'model_path': model['remote_path'],
        'inference_url': args.inference_url, 'evaluator_url': args.evaluator_url,
        'initial_prompts_sha256': prompts_sha}
    print('APPLICATION TEST INPUTS AND API VERIFIED', json.dumps(inputs), flush=True)
    if not args.execute:
        return
    from compare_application_test import validate_report
    path = ROOT / 'reports' / f'application_test_{args.stage}.json'
    report = {'complete': False, 'inputs': inputs, 'expected_episodes': recipe['episodes_per_model'],
        'episodes': [], 'invalid_attempts': [], 'started_at': datetime.now(timezone.utc).isoformat(),
        'training_performed': False, 'final_test': True, 'scripted_fixture': False,
        'fresh_blind_test': False}
    if path.exists():
        report = json.loads(path.read_text())
        if report['inputs'] != inputs:
            raise ValueError('Cannot resume changed inputs')
        validate_report(report, recipe, args.stage, require_complete=False)
    done = {(row['task_id'], row['seed']) for row in report['episodes']}
    save(path, report, token)

    class VerifiedTransport(VllmRepairTransport):
        async def encode(self, messages, tools):
            ids = await super().encode(messages, tools)
            if self.decision == 0:
                expected = prompts[self.task_id]
                if len(ids) != expected['tokens'] or prompt_digest(ids) != expected['sha256']:
                    raise ValueError('Serving tokenizer differs from frozen offline initial prompt')
            return ids

    for row in recipe['tasks']:
        task = load_final_public_task(PUBLIC, row['task_id'], recipe['public_manifest_sha256'])
        evaluator = RemoteEvaluator(args.evaluator_url, token, task.task_id)
        for seed in recipe['seeds']:
            if (task.task_id, seed) in done:
                continue
            current = VerifiedTransport(args.inference_url, alias, seed=seed)
            current.task_id = task.task_id
            agent = ApplicationTestRepairAgent(task, evaluator, current, task_split='test',
                test_task_ids=task_ids, session_manager=SessionManager(
                    str(ROOT / 'runs/application_test/sessions' / args.stage)))
            try:
                agent.run()
                if not agent.last_result['terminal']['valid_episode']:
                    raise InfrastructureUnavailable('Invalid application test episode')
            except Exception as error:
                report['invalid_attempts'].append({**row, 'seed': seed,
                    'error_type': type(error).__name__, 'observed_at': datetime.now(timezone.utc).isoformat()})
                save(path, report, token)
                raise
            report['episodes'].append({**agent.last_result, 'source_id': row['source_id']})
            done.add((task.task_id, seed))
            save(path, report, token)
            print(f"{args.stage} {len(done)}/{recipe['episodes_per_model']} {task.task_id} seed={seed} reward={agent.last_result['reward']}", flush=True)
    report.update(complete=True, finished_at=datetime.now(timezone.utc).isoformat(),
                  successes=sum(e['reward'] == 1 for e in report['episodes']))
    validate_report(report, recipe, args.stage)
    save(path, report, token)
    print('COMPLETE', path, flush=True)


if __name__ == '__main__':
    main()
