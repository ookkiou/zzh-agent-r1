"""Bounded autonomous model diagnostics using the same episode runner as Agent-R1 flow."""

import asyncio
import argparse
import json
import os
from pathlib import Path
import signal
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from code_repair.agent_session import GeneratedTokens, InfrastructureUnavailable, RepairSession, run_trajectory
from code_repair.evaluation import RemoteEvaluator
from code_repair.public_data import load_public_task


async def diagnose(sft_only=False):
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    if sys.platform != 'linux' or not torch.cuda.is_available():
        raise SystemExit('Run diagnostics on the verified Linux GPU host')
    output = ROOT / ('runs/day7/diagnostic_sft' if sft_only else 'runs/day7/diagnostic')
    output.mkdir(parents=True, exist_ok=True)
    selection = json.loads((ROOT / 'runs/day7/selection.json').read_text())
    public = ROOT / 'runs/day7/public_data'
    manifest = json.loads((public / 'manifest.json').read_text())
    token = Path(os.environ['CODE_REPAIR_TOKEN_FILE']).read_text().strip()
    url = os.environ['CODE_REPAIR_EVALUATOR_URL']
    health = RemoteEvaluator(url, token, selection['tasks'][0]['task_id']).health()
    if (health.get('backend') != 'docker' or not health.get('container_isolation_configured')
            or manifest['source_manifest_sha256'] not in health['dataset_manifest_sha256']):
        raise ValueError('Expected isolated evaluator for the frozen formal dataset')
    lock = json.loads((ROOT / 'TRAINING_SOURCE_LOCK.json').read_text())
    model_path = ROOT / 'models' / ('qwen-coder-1.5b-' + lock['model']['revision'])
    if sft_only:
        warmup = json.loads((ROOT / 'reports/day7_sft_warmup.json').read_text())
        if not warmup['complete']:
            raise ValueError('Completed and reloaded SFT checkpoint required')
        model_path = ROOT / 'runs/day7/sft_warmup/merged'
    tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True)
    model = AutoModelForCausalLM.from_pretrained(model_path, local_files_only=True,
        torch_dtype=torch.bfloat16, attn_implementation='sdpa').to('cuda').eval()
    report = {'complete': False, 'day7_complete': False, 'training_performed': False, 'guided': False,
        'full_dev_baseline': False, 'model_revision': lock['model']['revision'],
        'model_kind': 'SFT-only' if sft_only else 'original',
        'checkpoint_path': str(model_path),
        'generation_backend': 'Transformers; actual Agent-R1 tensor path checked separately',
        'episodes': [], 'groups': []}
    path = ROOT / ('reports/day7_sft_diagnostics.json' if sft_only else 'reports/day7_model_diagnostics.json')
    def save():
        serialized = json.dumps(report, ensure_ascii=False, indent=2)
        if token in serialized:
            raise RuntimeError('Credential would leak into report')
        path.write_text(serialized + '\n')
    save()
    async def encode(messages, tools):
        return tokenizer.apply_chat_template(messages, tools=tools, add_generation_prompt=True, tokenize=True)
    async def generate(prompt_ids):
        inputs = torch.tensor([prompt_ids], device='cuda')
        with torch.inference_mode():
            generated = model.generate(input_ids=inputs, attention_mask=torch.ones_like(inputs),
                max_new_tokens=selection['max_response_length'], do_sample=True,
                temperature=selection['temperature'], top_p=selection['top_p'],
                pad_token_id=tokenizer.eos_token_id)
        return GeneratedTokens(generated[0, len(prompt_ids):].tolist())
    try:
        for row in selection['tasks']:
            rewards = []
            task = load_public_task(public, row['task_id'])
            for seed in selection['seeds']:
                torch.manual_seed(seed)
                torch.cuda.manual_seed_all(seed)
                session = RepairSession(task, RemoteEvaluator(url, token, task.task_id))
                try:
                    steps, info, timings = await run_trajectory(session, encode, generate,
                        lambda ids: tokenizer.decode(ids, skip_special_tokens=False),
                        max_prompt_length=selection['max_prompt_length'],
                        max_response_length=selection['max_response_length'])
                except InfrastructureUnavailable:
                    report['failure'] = 'infrastructure_error; incomplete run excluded from learning conclusions'
                    save()
                    raise
                reward = sum(step.reward for step in steps)
                rewards.append(reward)
                item = {**row, 'seed': seed, 'reward': reward, 'valid_episode': info['valid_episode'],
                    'termination_reason': info['termination_reason'], 'steps': len(steps),
                    'parsed_actions': sum(t['parsed'] for t in session.trace),
                    'contract_valid_actions': sum(t['contract_valid'] for t in session.trace),
                    'successful_tool_requests': sum(bool(t['tool_response'] and t['tool_response']['ok']) for t in session.trace),
                    'generated_tokens': sum(len(s.response_ids) for s in steps)}
                trace = {'summary': item, 'terminal_info': info, 'steps': session.trace, 'timings': timings}
                content = json.dumps(trace, ensure_ascii=False, indent=2)
                if token in content:
                    raise RuntimeError('Credential would leak into trace')
                (output / (task.task_id + '-' + str(seed) + '.json')).write_text(content + '\n')
                report['episodes'].append(item)
                save()
                print(json.dumps(item), flush=True)
            report['groups'].append({**row, 'rewards': rewards, 'mixed_rewards': len(set(rewards)) > 1})
            save()
        for split in ('train', 'dev'):
            episodes = [r for r in report['episodes'] if r['split'] == split]
            groups = [r for r in report['groups'] if r['split'] == split]
            decisions = sum(r['steps'] for r in episodes)
            report[split] = {'valid_episodes': len(episodes),
                'success_rate': sum(r['reward'] == 1 for r in episodes) / len(episodes),
                'parsed_action_rate': sum(r['parsed_actions'] for r in episodes) / decisions,
                'contract_valid_action_rate': sum(r['contract_valid_actions'] for r in episodes) / decisions,
                'mixed_reward_groups': sum(r['mixed_rewards'] for r in groups), 'groups': len(groups)}
        report['complete'] = True
        report['learning_signal_present_in_train'] = report['train']['mixed_reward_groups'] > 0
        save()
        print(json.dumps({'complete': True, 'train': report['train'], 'dev': report['dev']}))
    except BaseException:
        save()
        raise


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--sft-only', action='store_true')
    args = parser.parse_args()
    os.environ.update({'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1', 'TOKENIZERS_PARALLELISM': 'false'})
    signal.alarm(3600)
    asyncio.run(diagnose(args.sft_only))
