"""Frozen independent final-test comparison; no parameter updates."""
import argparse
import asyncio
from collections import Counter
from datetime import datetime, timezone
import gc
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from code_repair.agent_session import GeneratedTokens, InfrastructureUnavailable, RepairSession, run_trajectory
from code_repair.agent_protocol import initial_messages
from code_repair.evaluation import RemoteEvaluator
from code_repair.final_test import load_final_public_task, verified_asset, PUBLIC_KEYS

PROTOCOL_SHA = '4b5fde7d02ac238d26fc4ed4cebcbb4d882ddfc0e85a530ab333cadc311742eb'


def validate_inputs(protocol, public):
    protocol_path = ROOT/'training/final_test/evaluation_protocol.json'
    if digest(protocol_path) != PROTOCOL_SHA or protocol['status'] != 'sealed_before_first_model_test':
        raise ValueError('Held-out protocol changed after sealing')
    if digest(ROOT/'reports/day11_candidate_freeze.json') != protocol['candidate_freeze_sha256']:
        raise ValueError('Candidate selection changed')
    for name, expected in protocol['core_files_sha256'].items():
        if digest(ROOT/name) != expected:
            raise ValueError('Frozen episode core changed: '+name)
    if digest(ROOT/'code_repair/final_test.py') != protocol['test_loader_sha256']:
        raise ValueError('Held-out public loader changed')
    if digest(public/'manifest.json') != protocol['public_manifest_sha256']:
        raise ValueError('Public manifest changed')
    manifest = json.loads((public/'manifest.json').read_text())
    if manifest['source_manifest_sha256'] != protocol['dataset_manifest_sha256']:
        raise ValueError('Public dataset does not match sealed test dataset')
    rows = [{k:r[k] for k in ('task_id','source_id','split')} for r in manifest['tasks']]
    if rows != protocol['tasks'] or len(rows) != 42 or len({r['source_id'] for r in rows}) != 42:
        raise ValueError('Expected exactly frozen 42 distinct test sources')
    expected = {r['path']+'/'+n for r in manifest['tasks'] for n in ('task.json','starter/solution.py','public_tests.py')}
    actual = {str(p.relative_to(public)) for p in public.rglob('*') if p.is_file()}
    if set(manifest['files']) != expected or actual != expected|{'manifest.json'}:
        raise ValueError('Public export has missing/private/unexpected files')
    for name in expected:
        verified_asset(public,name,manifest['files'])
    for row in rows:
        load_final_public_task(public,row['task_id'],protocol['public_manifest_sha256'])
    hashes = {}
    for stage, model in protocol['models'].items():
        directory = Path(model['remote_path'])
        hashes[stage] = digest(directory/'model.safetensors')
        if hashes[stage] != model['sha256']:
            raise ValueError('Model differs from pre-test selection: '+stage)
    sft, trained = [Path(protocol['models'][stage]['remote_path']) for stage in ('sft','step70')]
    for name in ('added_tokens.json','chat_template.jinja','merges.txt','special_tokens_map.json','tokenizer.json','tokenizer_config.json','vocab.json'):
        if digest(sft/name) != digest(trained/name):
            raise ValueError('Tokenizer differs between paired models: '+name)
    configs = [json.loads((p/'generation_config.json').read_text()) for p in (sft,trained)]
    if [{k:v for k,v in c.items() if k!='transformers_version'} for c in configs][0] != {k:v for k,v in configs[1].items() if k!='transformers_version'}:
        raise ValueError('Paired generation defaults differ')
    return {'protocol_sha256':PROTOCOL_SHA,'dataset_manifest_sha256':protocol['dataset_manifest_sha256'],
        'public_manifest_sha256':protocol['public_manifest_sha256'],
        'candidate_freeze_sha256':protocol['candidate_freeze_sha256'],
        'model_sha256':hashes,'script_sha256':digest(Path(__file__)),
        'test_loader_sha256':protocol['test_loader_sha256'],'tasks':42,'episodes_per_model':126}


def digest(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(4*1024*1024), b''):
            result.update(chunk)
    return result.hexdigest()


def write_json(path, data, token):
    content = json.dumps(data, ensure_ascii=False, indent=2) + '\n'
    if token in content:
        raise ValueError('Credential in report')
    temporary = path.with_suffix('.tmp')
    temporary.write_text(content)
    temporary.replace(path)


async def main(args):
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    if sys.platform != 'linux' or not torch.cuda.is_available():
        raise ValueError('Linux GPU instance required')
    torch.set_num_threads(4)
    gpu = subprocess.run(['nvidia-smi','--query-compute-apps=pid','--format=csv,noheader'],
        capture_output=True, text=True, timeout=10)
    if gpu.returncode or gpu.stdout.strip():
        raise ValueError('GPU unavailable/occupied; do not overlap evaluation and training')
    protocol = json.loads((ROOT/'training/final_test/evaluation_protocol.json').read_text())
    public = ROOT/'runs/final_test/public_data'
    expected_count = protocol['episodes_per_model']
    evidence = validate_inputs(protocol, public)
    token = (ROOT/'runs/day6/evaluator_token').read_text().strip()
    url = 'http://127.0.0.1:18766'
    health = RemoteEvaluator(url, token, protocol['tasks'][0]['task_id']).health()
    if health.get('backend')!='docker' or not health.get('container_isolation_configured') or health.get('task_count')!=len(protocol['tasks']) or evidence['dataset_manifest_sha256'] not in health['dataset_manifest_sha256']:
        raise ValueError('Expected authenticated held-out Docker evaluator')
    write_json(ROOT/'reports/final_test_eval_inputs.json', evidence, token)
    print('INPUTS VERIFIED', json.dumps(evidence), flush=True)
    if args.check_only:
        return
    expected = {(row['task_id'], seed) for row in protocol['tasks'] for seed in protocol['seeds']}
    reports = {}
    started = time.monotonic()
    for stage, model_path in [(s,Path(protocol['models'][s]['remote_path'])) for s in ('sft','step70')]:
        directory = ROOT/'runs/final_test/evaluation'/stage
        directory.mkdir(parents=True, exist_ok=True)
        report_path = ROOT/'reports'/('final_test_eval_'+stage+'.json')
        report = {'complete':False, 'stage':stage, 'model_path':str(model_path), 'inputs':evidence,
            'training_performed':False, 'guided':False, 'final_test':True,
            'started_at':datetime.now(timezone.utc).isoformat(), 'expected_attempts':expected_count,
            'episodes':[], 'invalid_attempts':[]}
        if report_path.exists():
            report = json.loads(report_path.read_text())
            if report['inputs']!=evidence or report['model_path']!=str(model_path):
                raise ValueError('Cannot resume changed model/protocol/script')
        done = {(r['task_id'],r['seed']) for r in report['episodes']}
        if not done.issubset(expected) or len(done)!=len(report['episodes']):
            raise ValueError('Unexpected/duplicate episode')
        if report['complete']:
            if done!=expected:
                raise ValueError('Incomplete saved coverage')
            reports[stage] = report
            continue
        tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True)
        model = AutoModelForCausalLM.from_pretrained(model_path, local_files_only=True,
            torch_dtype=torch.bfloat16, attn_implementation='sdpa').to('cuda').eval()
        async def encode(messages, tools):
            return tokenizer.apply_chat_template(messages,tools=tools,add_generation_prompt=True,tokenize=True)
        async def generate(prompt_ids):
            inputs = torch.tensor([prompt_ids],device='cuda')
            with torch.inference_mode():
                result = model.generate(input_ids=inputs, attention_mask=torch.ones_like(inputs),
                    max_new_tokens=protocol['max_response_length'], do_sample=True,
                    temperature=protocol['temperature'], top_p=protocol['top_p'],
                    pad_token_id=tokenizer.eos_token_id)
            return GeneratedTokens(result[0,len(prompt_ids):].tolist())
        write_json(report_path, report, token)
        for row in protocol['tasks']:
            task = load_final_public_task(public,row['task_id'],protocol['public_manifest_sha256'])
            for seed in protocol['seeds']:
                if (task.task_id,seed) in done:
                    continue
                for retry in range(protocol['infra_retries']+1):
                    torch.manual_seed(seed)
                    torch.cuda.manual_seed_all(seed)
                    session = RepairSession(task,RemoteEvaluator(url,token,task.task_id),
                        max_steps=protocol['max_steps'],episode_timeout=protocol['episode_timeout'],
                        test_timeout=protocol['test_timeout'])
                    start = time.monotonic()
                    try:
                        steps,info,timings = await run_trajectory(session,encode,generate,
                            lambda ids:tokenizer.decode(ids,skip_special_tokens=False),
                            max_prompt_length=protocol['max_prompt_length'],
                            max_response_length=protocol['max_response_length'])
                    except InfrastructureUnavailable as error:
                        report['invalid_attempts'].append({**row,'seed':seed,'retry':retry,'error':str(error)})
                        write_json(report_path,report,token)
                        if retry==protocol['infra_retries']:
                            raise
                        continue
                    break
                item = {**row,'seed':seed,'retry':retry,'reward':sum(s.reward for s in steps),
                    'valid_episode':info['valid_episode'],'termination_reason':info['termination_reason'],
                    'steps':len(steps),'parsed_actions':sum(t['parsed'] for t in session.trace),
                    'contract_valid_actions':sum(t['contract_valid'] for t in session.trace),
                    'generated_tokens':sum(len(s.response_ids) for s in steps),
                    'elapsed_seconds':time.monotonic()-start,'timings':timings,
                    'tool_counts':dict(Counter(t['action']['name'] for t in session.trace if t['action'] and 'name' in t['action'])),
                    'error_counts':dict(Counter(t['tool_response']['error']['code'] for t in session.trace if t['tool_response'] and not t['tool_response']['ok']))}
                if not item['valid_episode']:
                    raise ValueError('Invalid infrastructure episode')
                write_json(directory/(task.task_id+'-'+str(seed)+'.json'),
                    {'summary':item,'terminal_info':info,'steps':session.trace},token)
                report['episodes'].append(item)
                write_json(report_path,report,token)
                print(json.dumps({'stage':stage,'completed':len(report['episodes']),'total':expected_count,
                    'task_id':task.task_id,'seed':seed,'reward':item['reward']}),flush=True)
        episodes = report['episodes']
        if {(r['task_id'],r['seed']) for r in episodes}!=expected or len(episodes)!=expected_count:
            raise ValueError('Incomplete final-test evaluation')
        report.update({'complete':True,'task_count':len(protocol['tasks']),'source_count':len(protocol['tasks']),
            'successes':sum(r['reward']==1 for r in episodes),
            'success_rate':sum(r['reward']==1 for r in episodes)/expected_count,
            'finished_at':datetime.now(timezone.utc).isoformat()})
        write_json(report_path,report,token)
        reports[stage] = report
        del model,tokenizer
        gc.collect()
        torch.cuda.empty_cache()
    paired = {stage:{(r['task_id'],r['seed']):r for r in report['episodes']} for stage,report in reports.items()}
    comparison = {'complete':True,'inputs':evidence,'task_count':len(protocol['tasks']),'source_count':len(protocol['tasks']),
        'seeds':protocol['seeds'],'sft_successes':reports['sft']['successes'],
        'step70_successes':reports['step70']['successes'],
        'sft_success_rate':reports['sft']['success_rate'],'step70_success_rate':reports['step70']['success_rate'],
        'delta_percentage_points':100*(reports['step70']['success_rate']-reports['sft']['success_rate']),
        'paired_improved_episodes':sum(paired['sft'][k]['reward']==0 and paired['step70'][k]['reward']==1 for k in expected),
        'paired_regressed_episodes':sum(paired['sft'][k]['reward']==1 and paired['step70'][k]['reward']==0 for k in expected),
        'metric':str(expected_count)+' single episodes per model, not pass@3','statistical_significance_evaluated':False,
        'test_executed':True,'formal_225_updates_complete':False,'elapsed_seconds':time.monotonic()-started}
    comparison['by_seed'] = {str(seed):{stage:sum(r['reward']==1 for r in reports[stage]['episodes'] if r['seed']==seed) for stage in ('sft','step70')} for seed in protocol['seeds']}
    write_json(ROOT/'reports/final_test_eval_comparison.json',comparison,token)
    print('PAIRED FINAL TEST COMPARISON',json.dumps(comparison),flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-only',action='store_true')
    args = parser.parse_args()
    os.environ.update({'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','TOKENIZERS_PARALLELISM':'false'})
    signal.alarm(5400)
    asyncio.run(main(args))
