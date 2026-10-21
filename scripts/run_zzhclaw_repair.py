"""User-operated model API smoke/dev run via the actual ZzhClaw restricted Agent."""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from day13_prepare import PROTOCOL, build, digest


def write_report(path, report, token):
    text = json.dumps(report,ensure_ascii=False,indent=2)+'\n'
    if token in text:
        raise ValueError('Credential in report')
    path.parent.mkdir(parents=True,exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(text)
    temporary.replace(path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage',choices=('step70','sft'),default='step70')
    parser.add_argument('--scope',choices=('smoke','dev'),default='smoke')
    parser.add_argument('--zzhclaw-repo',type=Path,default=Path('/Users/zzh/Documents/GitHub/zzhclaw'))
    parser.add_argument('--inference-url',default='http://127.0.0.1:18000')
    parser.add_argument('--evaluator-url',default='http://127.0.0.1:8765')
    parser.add_argument('--execute',action='store_true',help='Without this, only verify inputs/API readiness')
    args = parser.parse_args()
    app = args.zzhclaw_repo.resolve()
    protocol = json.loads(PROTOCOL.read_text())
    if build(app)!=protocol:
        raise ValueError('Migration recipe/code changed; preserve the original experiment')
    sys.path.insert(0,str(app))
    from code_repair.agent_session import InfrastructureUnavailable
    from code_repair.evaluation import RemoteEvaluator
    from code_repair.public_data import load_public_task
    from zzhclaw.agent.repair import CodeRepairAgent, VllmRepairTransport
    from zzhclaw.coding.session import SessionManager
    if Path(sys.modules['zzhclaw.agent.repair'].__file__).resolve()!=app/'zzhclaw/agent/repair.py':
        raise ValueError('Unexpected ZzhClaw installation loaded')
    identity = json.loads((ROOT/'runs/day13'/('model-'+args.stage+'.json')).read_text())
    helper = protocol['local_files_sha256']['scripts/day13_serve_model.py']
    if (identity['stage']!=args.stage or identity['model_sha256']!=protocol['model_sha256'][args.stage]
            or identity['helper_sha256']!=helper or identity['vllm_version']!='0.11.0'
            or identity['core_files_sha256']!=protocol['core_files_sha256']):
        raise ValueError('Remote model identity/helper mismatch')
    defaults = identity['generation_config']
    if defaults.get('top_k')!=20 or defaults.get('repetition_penalty')!=1.1 or defaults.get('eos_token_id')!=[151645,151643]:
        raise ValueError('Model generation defaults changed')
    token = (ROOT/'runs/day6/evaluator_token').read_text().strip()
    rows = [row for row in protocol['tasks'] if args.scope=='dev' or row['task_id'] in protocol['smoke_tasks']]
    seeds = protocol['seeds'] if args.scope=='dev' else [protocol['seeds'][0]]
    expected = {(row['task_id'], seed) for row in rows for seed in seeds}
    alias = 'zzh-repair-'+args.stage
    transport = VllmRepairTransport(args.inference_url,alias)
    with transport.opener.open(args.inference_url.rstrip('/')+'/v1/models',timeout=10) as response:
        models = json.load(response)['data']
    if len(models)!=1 or models[0]['id']!=alias or models[0].get('root')!=identity['model_path']:
        raise ValueError('The active inference server does not serve the verified model')
    evaluator = RemoteEvaluator(args.evaluator_url,token,rows[0]['task_id'])
    health = evaluator.health()
    if (health.get('backend')!='docker' or not health.get('container_isolation_configured')
            or protocol['dataset_manifest_sha256'] not in health.get('dataset_manifest_sha256',[])):
        raise ValueError('Wrong/nonisolated evaluation service')
    inputs = {'protocol_sha256':digest(PROTOCOL),'stage':args.stage,'scope':args.scope,
        'model_sha256':identity['model_sha256'],'model_path':identity['model_path'],
        'inference_url':args.inference_url,'evaluator_url':args.evaluator_url}
    print('INPUTS AND API VERIFIED',json.dumps(inputs),flush=True)
    if not args.execute:
        return
    path = ROOT/'reports'/('day13_'+args.stage+'_'+args.scope+'.json')
    report = {'complete':False,'inputs':inputs,'expected_episodes':len(expected),'episodes':[],
        'invalid_attempts':[],'started_at':datetime.now(timezone.utc).isoformat(),
        'training_performed':False,'final_test':False,'scripted_fixture':False}
    if path.exists():
        report = json.loads(path.read_text())
        if report['inputs']!=inputs:
            raise ValueError('Cannot resume changed inputs')
    done = {(row['task_id'],row['seed']) for row in report['episodes']}
    if not done.issubset(expected) or len(done)!=len(report['episodes']):
        raise ValueError('Unexpected/duplicate saved episodes')
    write_report(path,report,token)
    # First prompt per episode must match offline HF tokenization on the GPU host.
    class VerifiedTransport(VllmRepairTransport):
        async def encode(self, messages, tools):
            ids = await super().encode(messages,tools)
            if self.decision==0:
                expected_prompt = identity['initial_dev_prompts'][self.task_id]
                sha = hashlib.sha256(json.dumps(ids,separators=(',',':')).encode()).hexdigest()
                if len(ids)!=expected_prompt['tokens'] or sha!=expected_prompt['sha256']:
                    raise ValueError('Serving chat template differs from the frozen repair prompt')
            return ids
    for row in rows:
        task = load_public_task(ROOT/'runs/day9/public_data',row['task_id'])
        evaluator = RemoteEvaluator(args.evaluator_url,token,task.task_id)
        for seed in seeds:
            if (task.task_id,seed) in done:
                continue
            current = VerifiedTransport(args.inference_url,alias,seed=seed)
            current.task_id = task.task_id
            agent = CodeRepairAgent(task,evaluator,current,task_split=row['split'],
                session_manager=SessionManager(str(ROOT/'runs/day13/sessions'/args.stage/args.scope)))
            try:
                agent.run()
                if not agent.last_result['terminal']['valid_episode']:
                    raise InfrastructureUnavailable('Invalid application episode')
            except Exception as error:
                report['invalid_attempts'].append({'task_id':task.task_id,'seed':seed,
                    'error_type':type(error).__name__,'observed_at':datetime.now(timezone.utc).isoformat()})
                write_report(path,report,token)
                raise
            report['episodes'].append(agent.last_result)
            write_report(path,report,token)
            print(f"{args.stage} {len(report['episodes'])}/{len(expected)} {task.task_id} seed={seed} reward={agent.last_result['reward']}",flush=True)
    report['complete'] = len(report['episodes'])==len(expected)
    report['successes'] = sum(row['reward']==1 for row in report['episodes'])
    report['finished_at'] = datetime.now(timezone.utc).isoformat()
    write_report(path,report,token)
    print('COMPLETE',path,flush=True)


if __name__ == '__main__':
    main()
