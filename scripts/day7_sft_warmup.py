"""Bounded LoRA supervised warmup with response-only labels; no GRPO updates."""

import gc
import hashlib
import json
import math
import os
from pathlib import Path
import random
import signal
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def main():
    import torch
    from peft import LoraConfig, get_peft_model
    from safetensors import safe_open
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from code_repair.contracts import TOOL_SCHEMAS
    if sys.platform != 'linux' or not torch.cuda.is_available():
        raise SystemExit('Verified Linux GPU required')
    os.environ.update({'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1'})
    torch.set_num_threads(4)
    random.seed(20261015)
    torch.manual_seed(20261015)
    directory = ROOT / 'runs/day7/sft_warmup'
    path = directory / 'train.jsonl'
    data = json.loads((ROOT / 'reports/day7_sft_data.json').read_text())
    if hashlib.sha256(path.read_bytes()).hexdigest() != data['dataset_sha256']:
        raise ValueError('SFT data checksum mismatch')
    lock = json.loads((ROOT / 'TRAINING_SOURCE_LOCK.json').read_text())
    original = ROOT / 'models' / ('qwen-coder-1.5b-' + lock['model']['revision'])
    tokenizer = AutoTokenizer.from_pretrained(original, local_files_only=True)
    raw = [json.loads(line) for line in path.read_text().splitlines()]
    excluded = set(data['diagnostic_sources_excluded'])
    examples, rejected_tasks = [], set()
    for row in raw:
        if row['split'] != 'train' or row['source_id'] in excluded:
            raise ValueError('Supervision split/source violation')
        prompt = tokenizer.apply_chat_template(row['messages'], tools=TOOL_SCHEMAS,
                    add_generation_prompt=True, tokenize=True)
        full = tokenizer.apply_chat_template(row['messages'] + [{'role': 'assistant', 'content': row['response']}],
                    tools=TOOL_SCHEMAS, add_generation_prompt=False, tokenize=True)
        if full[:len(prompt)] != prompt:
            raise ValueError('Supervised prompt/response token boundary mismatch')
        if len(prompt) > 4096 or len(full) - len(prompt) > 512:
            rejected_tasks.add(row['task_id'])
        examples.append((row['task_id'], full, [-100] * len(prompt) + full[len(prompt):]))
    examples = [row for row in examples if row[0] not in rejected_tasks]
    if len(examples) < 50:
        raise ValueError('Insufficient untruncated teacher trajectories')
    model = AutoModelForCausalLM.from_pretrained(original, local_files_only=True,
        torch_dtype=torch.bfloat16, attn_implementation='sdpa').to('cuda')
    model.config.use_cache = False
    model = get_peft_model(model, LoraConfig(task_type='CAUSAL_LM', r=16, lora_alpha=32,
        lora_dropout=0.05, target_modules='all-linear', bias='none'))
    model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={'use_reentrant': False})
    model.enable_input_require_grads()
    model.train()
    parameters = [p for p in model.parameters() if p.requires_grad]
    optimizer = torch.optim.AdamW(parameters, lr=1e-4, weight_decay=0)
    report_path = ROOT / 'reports/day7_sft_warmup.json'
    report = {'complete': False, 'algorithm': 'supervised LoRA, not GRPO', 'max_updates': 80,
        'gradient_accumulation': 4, 'learning_rate': 1e-4, 'lora_rank': 16,
        'base_revision': lock['model']['revision'], 'teacher_data_sha256': data['dataset_sha256'],
        'eligible_examples': len(examples), 'rejected_long_task_ids': sorted(rejected_tasks),
        'response_only_labels_verified': True, 'dev_or_test_labels_used': False,
        'diagnostic_sources_excluded': True, 'updates': []}
    def save():
        report_path.write_text(json.dumps(report, indent=2) + '\n')
    save()
    schedule = []
    while len(schedule) < 80 * 4:
        order = list(range(len(examples)))
        random.shuffle(order)
        schedule.extend(order)
    optimizer.zero_grad(set_to_none=True)
    for update in range(80):
        losses = []
        for index in schedule[update * 4:(update + 1) * 4]:
            _, ids, labels = examples[index]
            inputs = torch.tensor([ids], device='cuda')
            output = model(input_ids=inputs, attention_mask=torch.ones_like(inputs),
                           labels=torch.tensor([labels], device='cuda'))
            loss = output.loss
            if not torch.isfinite(loss):
                raise ValueError('Nonfinite supervised loss')
            losses.append(float(loss.detach()))
            (loss / 4).backward()
            del output, inputs, loss
        norm = float(torch.nn.utils.clip_grad_norm_(parameters, 1.0))
        if not math.isfinite(norm) or norm <= 0:
            raise ValueError('Invalid supervised gradient norm')
        optimizer.step()
        optimizer.zero_grad(set_to_none=True)
        row = {'update': update + 1, 'loss': sum(losses) / 4, 'grad_norm': norm}
        report['updates'].append(row)
        save()
        print(json.dumps(row), flush=True)
    adapter = directory / 'adapter'
    model.save_pretrained(adapter)
    model.eval()
    merged = model.merge_and_unload()
    merged.config.use_cache = True
    changed = []
    with safe_open(original / 'model.safetensors', framework='pt', device='cpu') as weights:
        for name in weights.keys():
            if name.endswith('self_attn.q_proj.weight'):
                actual = merged.get_parameter(name).detach().cpu()
                if not torch.equal(actual, weights.get_tensor(name)):
                    changed.append(name)
    if not changed:
        raise ValueError('No observable merged attention weight changes')
    target = directory / 'merged'
    merged.save_pretrained(target, safe_serialization=True)
    tokenizer.save_pretrained(target)
    del optimizer, parameters, model, merged
    gc.collect()
    torch.cuda.empty_cache()
    reloaded = AutoModelForCausalLM.from_pretrained(target, local_files_only=True,
        torch_dtype=torch.bfloat16, attn_implementation='sdpa').to('cuda').eval()
    ids = tokenizer.apply_chat_template([{'role': 'user', 'content': 'Output the integer 7.'}],
        tokenize=True, add_generation_prompt=True, return_tensors='pt').to('cuda')
    with torch.inference_mode():
        result = reloaded.generate(input_ids=ids, attention_mask=torch.ones_like(ids), max_new_tokens=16,
                                  do_sample=False, pad_token_id=tokenizer.eos_token_id)
    text = tokenizer.decode(result[0, ids.shape[1]:], skip_special_tokens=True)
    if not text.strip():
        raise ValueError('Reloaded supervised model generated no text')
    report.update({'complete': True, 'merged_path': str(target), 'adapter_path': str(adapter),
        'changed_q_projection_tensors': changed, 'checkpoint_gpu_reload_generated_text': text,
        'model_ability_improvement_evaluated': False})
    save()
    print(json.dumps({'complete': True, 'updates': 80, 'merged_path': str(target)}), flush=True)


if __name__ == '__main__':
    signal.alarm(1200)
    main()
