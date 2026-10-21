"""Paired SFT/step70 dev evaluation using the unchanged Day8 episode protocol."""
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
from code_repair.public_data import load_public_task

MODEL = Path('/root/zzh-day9-eval/merged-step70')
CHECKPOINT = Path('/root/zzh-day9-checkpoints/global_step_70')
PROTOCOL_SHA = '078b36f56a85e1ef800da548ba042e7296fe6e79cb3b10dfb3c2d492f3338635'


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


def validate_inputs(protocol, public):
    if digest(ROOT/'runs/day8/evaluation_protocol.json') != PROTOCOL_SHA:
        raise ValueError('Frozen protocol changed')
    identity = json.loads((ROOT/'runs/day9/input_identity.json').read_text())
    if digest(public/'manifest.json') != identity['public_manifest_sha256']:
        raise ValueError('Day9 manifest changed')
    manifest = json.loads((public/'manifest.json').read_text())
    old_public = ROOT/'runs/day7/public_data'
    old = json.loads((old_public/'manifest.json').read_text())
    if old['source_manifest_sha256'] != protocol['source_manifest_sha256'] or manifest['source_manifest_sha256'] != identity['dataset_manifest_sha256']:
        raise ValueError('Dataset version bridge mismatch')
    tables = [{r['task_id']:r for r in m['tasks']} for m in (old, manifest)]
    if len(protocol['tasks']) != 32 or len(protocol['seeds']) != 3 or {r['task_id'] for r in protocol['tasks']} != {r['task_id'] for r in manifest['tasks'] if r['split']=='dev'}:
        raise ValueError('Expected frozen dev32 and three seeds')
    for row in protocol['tasks']:
        if row['split'] != 'dev' or tables[1][row['task_id']]['source_id'] != row['source_id']:
            raise ValueError('Non-frozen dev task')
        for suffix in ('task.json', 'starter/solution.py', 'public_tests.py'):
            a, b = [table[row['task_id']]['path']+'/'+suffix for table in tables]
            if digest(old_public/a) != old['files'][a] or digest(public/b) != manifest['files'][b]:
                raise ValueError('Dev file differs from its manifest: '+b)
            if suffix == 'task.json':
                left, right = [json.loads(p.read_text()) for p in (old_public/a, public/b)]
                keys = {'task_id','source_id','split','entrypoint','instruction'}
                if set(right)!=keys or any(left.get(k)!=right[k] for k in keys):
                    raise ValueError('Model-visible task metadata differs')
            elif old['files'][a] != manifest['files'][b]:
                raise ValueError('Old/new dev starter/tests differ: '+b)
        if initial_messages(load_public_task(old_public,row['task_id'])) != initial_messages(load_public_task(public,row['task_id'])):
            raise ValueError('Old/new model messages differ')
    for name, expected in protocol['core_files_sha256'].items():
        if digest(ROOT/name) != expected:
            raise ValueError('Frozen evaluation core changed: '+name)
    fingerprint = hashlib.sha256(b'\n'.join([(ROOT/'runs/day9/input_identity.json').read_bytes(),
        (ROOT/'reports/day7_sft_checkpoint_manifest.json').read_bytes()])).hexdigest()
    marker = json.loads((CHECKPOINT/'zzh_completed_checkpoint.json').read_text())
    if marker['global_step'] != 70 or marker['fingerprint'] != fingerprint or not marker['model_extra_and_dataloader_saved']:
        raise ValueError('Checkpoint identity mismatch')
    for name, size in marker['files'].items():
        path = CHECKPOINT/name
        if not path.resolve().is_relative_to(CHECKPOINT.resolve()) or path.is_symlink() or path.stat().st_size != size:
            raise ValueError('Checkpoint file/size mismatch')
    sft = ROOT/'runs/day7/sft_warmup/merged'
    saved = json.loads((ROOT/'reports/day7_sft_checkpoint_manifest.json').read_text())
    for name, entry in saved['files'].items():
        if name.startswith('merged/') and digest(ROOT/'runs/day7/sft_warmup'/name) != entry['sha256']:
            raise ValueError('SFT reference changed: '+name)
    for name in ('added_tokens.json','chat_template.jinja','merges.txt','special_tokens_map.json','tokenizer.json','tokenizer_config.json','vocab.json'):
        if digest(sft/name) != digest(MODEL/name):
            raise ValueError('Tokenizer differs: '+name)
    configs = [json.loads((p/'generation_config.json').read_text()) for p in (sft, MODEL)]
    if [{k:v for k,v in c.items() if k!='transformers_version'} for c in configs][0] != {k:v for k,v in configs[1].items() if k!='transformers_version'}:
        raise ValueError('Generation defaults differ')
    return {'protocol_sha256':PROTOCOL_SHA, 'run_fingerprint':fingerprint,
        'dataset_manifest_sha256':identity['dataset_manifest_sha256'],
        'dev_starter_and_test_files_byte_identical':64,
        'dev_model_messages_equal':32, 'dev_model_visible_metadata_equal':32, 'checkpoint_step':70,
        'checkpoint_marker_sha256':digest(CHECKPOINT/'zzh_completed_checkpoint.json'),
        'sft_model_sha256':digest(sft/'model.safetensors'),
        'step70_model_sha256':digest(MODEL/'model.safetensors'),
        'script_sha256':digest(Path(__file__)), 'test_executed':False,
        'checkpoint_check':'marker and sizes; merged model hashed; source weight hash not checked'}


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
    protocol = json.loads((ROOT/'runs/day8/evaluation_protocol.json').read_text())
    public = ROOT/'runs/day9/public_data'
    evidence = validate_inputs(protocol, public)
    token = (ROOT/'runs/day6/evaluator_token').read_text().strip()
    url = 'http://127.0.0.1:18765'
    health = RemoteEvaluator(url, token, protocol['tasks'][0]['task_id']).health()
    if health.get('backend')!='docker' or not health.get('container_isolation_configured') or health.get('task_count')!=332 or evidence['dataset_manifest_sha256'] not in health['dataset_manifest_sha256']:
        raise ValueError('Expected authenticated Docker v0.2 evaluator')
    write_json(ROOT/'reports/day9_eval_step70_inputs.json', evidence, token)
    print('INPUTS VERIFIED', json.dumps(evidence), flush=True)
    if args.check_only:
        return
    expected = {(row['task_id'], seed) for row in protocol['tasks'] for seed in protocol['seeds']}
    reports = {}
    started = time.monotonic()
    for stage, model_path in [('sft',ROOT/'runs/day7/sft_warmup/merged'), ('step70',MODEL)]:
        directory = ROOT/'runs/day9/eval_step70'/stage
        directory.mkdir(parents=True, exist_ok=True)
        report_path = ROOT/'reports'/('day9_eval_step70_'+stage+'.json')
        report = {'complete':False, 'stage':stage, 'model_path':str(model_path), 'inputs':evidence,
            'training_performed':False, 'guided':False, 'final_test':False,
            'started_at':datetime.now(timezone.utc).isoformat(), 'expected_attempts':96,
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
            task = load_public_task(public,row['task_id'])
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
                print(json.dumps({'stage':stage,'completed':len(report['episodes']),'total':96,
                    'task_id':task.task_id,'seed':seed,'reward':item['reward']}),flush=True)
        episodes = report['episodes']
        if {(r['task_id'],r['seed']) for r in episodes}!=expected or len(episodes)!=96:
            raise ValueError('Incomplete dev evaluation')
        report.update({'complete':True,'task_count':32,'source_count':14,
            'successes':sum(r['reward']==1 for r in episodes),
            'success_rate':sum(r['reward']==1 for r in episodes)/96,
            'finished_at':datetime.now(timezone.utc).isoformat()})
        write_json(report_path,report,token)
        reports[stage] = report
        del model,tokenizer
        gc.collect()
        torch.cuda.empty_cache()
    paired = {stage:{(r['task_id'],r['seed']):r for r in report['episodes']} for stage,report in reports.items()}
    comparison = {'complete':True,'inputs':evidence,'task_count':32,'source_count':14,
        'seeds':protocol['seeds'],'sft_successes':reports['sft']['successes'],
        'step70_successes':reports['step70']['successes'],
        'sft_success_rate':reports['sft']['success_rate'],'step70_success_rate':reports['step70']['success_rate'],
        'delta_percentage_points':100*(reports['step70']['success_rate']-reports['sft']['success_rate']),
        'paired_improved_episodes':sum(paired['sft'][k]['reward']==0 and paired['step70'][k]['reward']==1 for k in expected),
        'paired_regressed_episodes':sum(paired['sft'][k]['reward']==1 and paired['step70'][k]['reward']==0 for k in expected),
        'metric':'96 single episodes per model, not pass@3','statistical_significance_evaluated':False,
        'test_executed':False,'formal_225_updates_complete':False,'elapsed_seconds':time.monotonic()-started}
    write_json(ROOT/'reports/day9_eval_step70_comparison.json',comparison,token)
    print('PAIRED DEV COMPARISON',json.dumps(comparison),flush=True)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-only',action='store_true')
    args = parser.parse_args()
    os.environ.update({'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','TOKENIZERS_PARALLELISM':'false'})
    signal.alarm(5400)
    asyncio.run(main(args))
