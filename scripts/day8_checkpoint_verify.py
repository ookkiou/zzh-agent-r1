"""Verify five real repair GRPO updates, incremental weight changes and GPU checkpoint reload."""
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys
ROOT=Path(__file__).resolve().parents[1]


def main():
    report_path=ROOT/'reports/day8_checkpoint_verification.json'
    report={'complete':False,'code_repair_grpo':True,'ability_improvement_evaluated':False}
    def save():
        report_path.write_text(json.dumps(report,indent=2)+'\n')
    save()
    status=json.loads((ROOT/'reports/day8_smoke_status.json').read_text())
    if status.get('returncode')!=0:
        raise SystemExit('Successful custom training process required')
    log=re.sub(r'\x1b\[[0-9;]*m','',(ROOT/'reports/day8_smoke.log').read_text(errors='replace'))
    metrics={}
    for line in log.splitlines():
        step=re.search(r'training/global_step:(\d+)',line)
        if step:
            metrics[int(step.group(1))]={key:float(value) for key,value in re.findall(
                r'(actor/(?:grad_norm|pg_loss|kl_loss)|critic/score/mean|timing_s/(?:step|gen|update_actor)):([^\s]+)',line)}
    if set(metrics)!={1,2,3,4,5} or any(not math.isfinite(v) for row in metrics.values() for v in row.values()):
        raise SystemExit('Exactly five finite optimizer metric rows required')
    if not all(row.get('actor/grad_norm',0)>0 for row in metrics.values()):
        raise SystemExit('Nonzero finite actor gradients required for all smoke steps')
    audits=[json.loads(line) for line in (ROOT/'runs/day8/smoke/training_batch_audit.jsonl').read_text().splitlines()]
    if [r['global_step'] for r in audits]!=[1,2,3,4,5]:
        raise SystemExit('Five actual pre-optimizer batch audits required')
    allowed={json.loads(line)['extra_info']['task_id'] for line in (ROOT/'runs/day8/train_smoke.jsonl').read_text().splitlines()}
    if any(r['trajectory_count']!=16 or r['group_count']!=4 or not r['actual_trajectory_grpo_advantages_verified']
           or {t['task_id'] for t in r['trajectories']}!=allowed for r in audits):
        raise SystemExit('Incomplete/misaligned train-only repair rollout groups')
    if sum(r['mixed_reward_groups'] for r in audits)==0:
        raise SystemExit('No actual training groups had relative learning signal')
    real_trajectories=[t for r in audits for t in r['trajectories']]
    if not any(t['steps']>1 for t in real_trajectories):
        raise SystemExit('No real multi-step trajectories participated in optimizer updates')
    for item in real_trajectories:
        trace=json.loads((ROOT/'runs/day8/smoke_traces'/(item['trace_id']+'.json')).read_text())
        if trace['guided'] or trace['model_generation']!='real vLLM, not scripted' or trace['reward']!=item['reward'] or len(trace['token_steps'])!=item['steps']:
            raise SystemExit('Actual model trace does not match trainer batch audit')
    report['updates']=metrics
    report['training_audit']={'updates':len(audits),'real_episodes':len(real_trajectories),
        'mixed_reward_groups':sum(r['mixed_reward_groups'] for r in audits),
        'real_multi_step_episodes':sum(t['steps']>1 for t in real_trajectories),
        'terminal_reward_once':True,'actual_grpo_advantages_verified':True,'train_only':True}
    actor=ROOT/'runs/day8/smoke/global_step_5/actor'
    destination=ROOT/'runs/day8/smoke/merged-step5'
    env=os.environ.copy();env.update({'HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','OMP_NUM_THREADS':'4'})
    result=subprocess.run([sys.executable,'-m','verl.model_merger','merge','--backend','fsdp',
        '--local_dir',str(actor),'--target_dir',str(destination),'--use_cpu_initialization'],cwd=ROOT,env=env,timeout=600)
    if result.returncode:
        raise SystemExit(result.returncode)
    report['merged_path']=str(destination)
    save()
    import torch
    from safetensors import safe_open
    from transformers import AutoModelForCausalLM, AutoTokenizer
    torch.set_num_threads(4)
    lock = json.loads((ROOT / 'TRAINING_SOURCE_LOCK.json').read_text())
    original_path = ROOT / 'runs/day7/sft_warmup/merged'
    trained = {}
    changed_tensors = changed_elements = checked_elements = 0
    for file in sorted(destination.glob('*.safetensors')):
        with safe_open(file, framework='pt', device='cpu') as weights:
            for name in weights.keys():
                trained[name] = file
    if not trained:
        raise SystemExit('Merged safetensors missing')
    with safe_open(original_path / 'model.safetensors', framework='pt', device='cpu') as original:
        extra = set(trained) - set(original.keys())
        if extra == {'lm_head.weight'}:
            old_config = json.loads((original_path / 'config.json').read_text())
            new_config = json.loads((destination / 'config.json').read_text())
            if not old_config.get('tie_word_embeddings') or not new_config.get('tie_word_embeddings'):
                raise SystemExit('Unexpected extra output head without tied embeddings')
            with safe_open(trained['lm_head.weight'], framework='pt', device='cpu') as weights:
                head = weights.get_tensor('lm_head.weight')
            with safe_open(trained['model.embed_tokens.weight'], framework='pt', device='cpu') as weights:
                embedding = weights.get_tensor('model.embed_tokens.weight')
            if not torch.equal(head, embedding):
                raise SystemExit('Saved tied output head differs from embedding')
            report['tied_weight_alias_verified'] = 'lm_head.weight == model.embed_tokens.weight'
            del trained['lm_head.weight']
            del head, embedding
        if set(original.keys()) != set(trained):
            raise SystemExit('Original and checkpoint tensor names differ')
        for name in original.keys():
            with safe_open(trained[name], framework='pt', device='cpu') as weights:
                left, right = original.get_tensor(name), weights.get_tensor(name)
            if left.shape != right.shape or not bool(torch.isfinite(right).all()):
                raise SystemExit('Invalid checkpoint tensor ' + name)
            changed = int(torch.count_nonzero(left != right))
            changed_elements += changed
            changed_tensors += bool(changed)
            checked_elements += right.numel()
    report['weight_comparison'] = {'checked_tensors': len(trained), 'changed_tensors': changed_tensors,
        'checked_elements': checked_elements, 'changed_elements': changed_elements,
        'all_checkpoint_weights_finite': True, 'compared_to': 'SFT-only merged checkpoint', 'base_revision': lock['model']['revision']}
    save()
    if changed_elements == 0:
        raise SystemExit('Checkpoint has no observable weight changes')
    tokenizer = AutoTokenizer.from_pretrained(destination, local_files_only=True)
    model = AutoModelForCausalLM.from_pretrained(destination, local_files_only=True,
                torch_dtype=torch.bfloat16, attn_implementation='sdpa').to('cuda').eval()
    inputs = tokenizer.apply_chat_template([{'role': 'user', 'content': 'Output the integer 7.'}],
                add_generation_prompt=True, return_tensors='pt', return_dict=True).to('cuda')
    with torch.inference_mode():
        output = model.generate(**inputs, max_new_tokens=16, do_sample=False,
                                pad_token_id=tokenizer.eos_token_id)
    text = tokenizer.decode(output[0, inputs['input_ids'].shape[1]:], skip_special_tokens=True)
    report['checkpoint_reload'] = {'gpu': torch.cuda.get_device_name(0), 'generated_text': text,
                                   'nonempty': bool(text.strip())}
    report['complete'] = bool(text.strip())
    save()
    print(json.dumps(report, indent=2))
    return 0 if report['complete'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
