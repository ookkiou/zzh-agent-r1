"""Verify actual two-update metrics, changed weights and checkpoint GPU reload."""

import argparse
import json
import math
import os
from pathlib import Path
import re
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', choices=('single', 'tool'), default='single')
    args = parser.parse_args()
    report_path = ROOT / ('reports/day6_' + args.stage + '_checkpoint_verification.json')
    report = {'complete': False, 'stage': args.stage, 'ability_improvement_evaluated': False}
    def save():
        report_path.write_text(json.dumps(report, indent=2) + '\n')
    save()
    status = json.loads((ROOT / ('reports/day6_' + args.stage + '_smoke_status.json')).read_text())
    if status.get('returncode') != 0:
        raise SystemExit('Successful training process required')
    log = (ROOT / ('reports/day6_' + args.stage + '_smoke.log')).read_text(errors='replace')
    log = re.sub(r'\x1b\[[0-9;]*m', '', log)
    metrics = {}
    for line in log.splitlines():
        step = re.search(r'training/global_step:(\d+)', line)
        if step:
            values = {key: float(value) for key, value in re.findall(
                r'(actor/(?:grad_norm|pg_loss|kl_loss)|critic/score/mean):([^\s]+)', line)}
            metrics[int(step.group(1))] = values
    if set(metrics) != {1, 2} or any(not math.isfinite(v) for row in metrics.values() for v in row.values()):
        raise SystemExit('Two finite update metric rows required')
    if not all(row.get('actor/grad_norm', 0) > 0 for row in metrics.values()):
        raise SystemExit('Nonzero actor gradients required')
    report['updates'] = metrics
    actor = ROOT / 'runs/day6-smoke' / args.stage / 'global_step_2/actor'
    destination = ROOT / 'runs/day6-smoke' / args.stage / 'merged-step2'
    env = os.environ.copy()
    env.update({'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1', 'OMP_NUM_THREADS': '4'})
    result = subprocess.run([sys.executable, '-m', 'verl.model_merger', 'merge', '--backend', 'fsdp',
            '--local_dir', str(actor), '--target_dir', str(destination), '--use_cpu_initialization'],
            cwd=ROOT, env=env, timeout=600)
    if result.returncode:
        raise SystemExit(result.returncode)
    report['merged_path'] = str(destination)
    save()
    import torch
    from safetensors import safe_open
    from transformers import AutoModelForCausalLM, AutoTokenizer
    torch.set_num_threads(4)
    lock = json.loads((ROOT / 'TRAINING_SOURCE_LOCK.json').read_text())
    original_path = ROOT / 'models' / ('qwen-coder-1.5b-' + lock['model']['revision'])
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
        'all_checkpoint_weights_finite': True, 'original_revision': lock['model']['revision']}
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
