"""Full paired Base/SFT-only dev evaluation under a frozen sampling protocol."""
import asyncio
from collections import Counter
from datetime import datetime, timezone
import gc
import hashlib
import json
import os
from pathlib import Path
import signal
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from code_repair.agent_session import GeneratedTokens, InfrastructureUnavailable, RepairSession, run_trajectory
from code_repair.evaluation import RemoteEvaluator
from code_repair.public_data import load_public_task


async def main():
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    if sys.platform != 'linux' or not torch.cuda.is_available():
        raise SystemExit('Linux GPU required')
    torch.set_num_threads(4)
    protocol_path=ROOT/'runs/day8/evaluation_protocol.json'
    protocol=json.loads(protocol_path.read_text())
    for name,digest in protocol['core_files_sha256'].items():
        if hashlib.sha256((ROOT/name).read_bytes()).hexdigest()!=digest:
            raise ValueError('Frozen evaluation core changed: '+name)
    token=Path(os.environ['CODE_REPAIR_TOKEN_FILE']).read_text().strip()
    url=os.environ['CODE_REPAIR_EVALUATOR_URL']
    public=ROOT/'runs/day7/public_data'
    health=RemoteEvaluator(url,token,protocol['tasks'][0]['task_id']).health()
    if health.get('backend')!='docker' or not health.get('container_isolation_configured') or protocol['source_manifest_sha256'] not in health['dataset_manifest_sha256']:
        raise ValueError('Verified Docker evaluator required')
    revision=json.loads((ROOT/'TRAINING_SOURCE_LOCK.json').read_text())['model']['revision']
    stages=[('base',ROOT/'models'/('qwen-coder-1.5b-'+revision)),
            ('sft',ROOT/'runs/day7/sft_warmup/merged')]
    started=time.monotonic()
    for stage,model_path in stages:
        directory=ROOT/'runs/day8/baseline'/stage
        directory.mkdir(parents=True,exist_ok=True)
        report_path=ROOT/'reports'/('day8_baseline_'+stage+'.json')
        fingerprint=hashlib.sha256(protocol_path.read_bytes()).hexdigest()
        report={'complete':False,'model_kind':'Base' if stage=='base' else 'SFT-only',
            'model_path':str(model_path),'base_revision':revision,'protocol_sha256':fingerprint,
            'training_performed':False,'guided':False,'final_test':False,
            'started_at':datetime.now(timezone.utc).isoformat(),
            'expected_attempts':96,'episodes':[],'invalid_attempts':[]}
        if report_path.exists():
            saved=json.loads(report_path.read_text())
            if saved['protocol_sha256']!=fingerprint or saved['model_path']!=str(model_path):
                raise ValueError('Cannot resume a different model/protocol')
            report=saved
            if report['complete']:
                print('Already complete',stage,flush=True)
                continue
        def save():
            content=json.dumps(report,ensure_ascii=False,indent=2)+'\n'
            if token in content:
                raise ValueError('Credential in report')
            temporary=report_path.with_suffix('.json.tmp')
            temporary.write_text(content)
            temporary.replace(report_path)
        tokenizer=AutoTokenizer.from_pretrained(model_path,local_files_only=True)
        model=AutoModelForCausalLM.from_pretrained(model_path,local_files_only=True,
            torch_dtype=torch.bfloat16,attn_implementation='sdpa').to('cuda').eval()
        save()
        async def encode(messages,tools):
            return tokenizer.apply_chat_template(messages,tools=tools,add_generation_prompt=True,tokenize=True)
        async def generate(prompt_ids):
            inputs=torch.tensor([prompt_ids],device='cuda')
            with torch.inference_mode():
                result=model.generate(input_ids=inputs,attention_mask=torch.ones_like(inputs),
                    max_new_tokens=protocol['max_response_length'],do_sample=True,
                    temperature=protocol['temperature'],top_p=protocol['top_p'],
                    pad_token_id=tokenizer.eos_token_id)
            return GeneratedTokens(result[0,len(prompt_ids):].tolist())
        done={(r['task_id'],r['seed']) for r in report['episodes']}
        for row in protocol['tasks']:
            task=load_public_task(public,row['task_id'])
            if row['split']!='dev':
                raise ValueError('Only dev tasks may be evaluated')
            for seed in protocol['seeds']:
                if (task.task_id,seed) in done:
                    continue
                for retry in range(protocol['infra_retries']+1):
                    torch.manual_seed(seed)
                    torch.cuda.manual_seed_all(seed)
                    session=RepairSession(task,RemoteEvaluator(url,token,task.task_id),
                        max_steps=protocol['max_steps'],episode_timeout=protocol['episode_timeout'],
                        test_timeout=protocol['test_timeout'])
                    start=time.monotonic()
                    try:
                        steps,info,timings=await run_trajectory(session,encode,generate,
                            lambda ids:tokenizer.decode(ids,skip_special_tokens=False),
                            max_prompt_length=protocol['max_prompt_length'],max_response_length=protocol['max_response_length'])
                    except InfrastructureUnavailable as error:
                        report['invalid_attempts'].append({**row,'seed':seed,'retry':retry,'error':str(error)})
                        save()
                        if retry==protocol['infra_retries']:
                            raise
                        continue
                    break
                tool_counts=Counter(t['action']['name'] for t in session.trace if t['action'] and 'name' in t['action'])
                errors=Counter(t['tool_response']['error']['code'] for t in session.trace if t['tool_response'] and not t['tool_response']['ok'])
                item={**row,'seed':seed,'retry':retry,'reward':sum(s.reward for s in steps),
                    'valid_episode':info['valid_episode'],'termination_reason':info['termination_reason'],
                    'steps':len(steps),'parsed_actions':sum(t['parsed'] for t in session.trace),
                    'contract_valid_actions':sum(t['contract_valid'] for t in session.trace),
                    'generated_tokens':sum(len(s.response_ids) for s in steps),
                    'elapsed_seconds':time.monotonic()-start,'timings':timings,
                    'tool_counts':dict(tool_counts),'error_counts':dict(errors)}
                trace={'summary':item,'terminal_info':info,'steps':session.trace}
                content=json.dumps(trace,ensure_ascii=False,indent=2)+'\n'
                if token in content:
                    raise ValueError('Credential in trace')
                (directory/(task.task_id+'-'+str(seed)+'.json')).write_text(content)
                report['episodes'].append(item)
                save()
                print(json.dumps({'model':stage,'completed':len(report['episodes']),**item}),flush=True)
        episodes=report['episodes']
        decisions=sum(r['steps'] for r in episodes)
        report.update({'complete':len(episodes)==96,'valid_coverage':len(episodes)/96,
            'task_count':len({r['task_id'] for r in episodes}),
            'source_count':len({r['source_id'] for r in episodes}),
            'successes':sum(r['reward']==1 for r in episodes),
            'success_rate':sum(r['reward']==1 for r in episodes)/len(episodes),
            'parsed_action_rate':sum(r['parsed_actions'] for r in episodes)/decisions,
            'contract_valid_action_rate':sum(r['contract_valid_actions'] for r in episodes)/decisions,
            'generated_tokens':sum(r['generated_tokens'] for r in episodes),
            'finished_at':datetime.now(timezone.utc).isoformat()})
        save()
        print('Completed',stage,report['success_rate'],flush=True)
        del model,tokenizer
        gc.collect()
        torch.cuda.empty_cache()
    print('Both complete dev baselines finished',time.monotonic()-started,flush=True)


if __name__=='__main__':
    os.environ.update({'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','TOKENIZERS_PARALLELISM':'false'})
    signal.alarm(5400)
    asyncio.run(main())
