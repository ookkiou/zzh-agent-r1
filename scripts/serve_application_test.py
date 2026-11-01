"""Verify frozen test-model inputs on AutoDL, optionally serve the verified model."""
import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / 'scripts'))
from prepare_application_test import PROTOCOL, PUBLIC, digest, validate_resources, write_json


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', choices=('sft', 'step70'), required=True)
    parser.add_argument('--protocol-sha256', required=True)
    parser.add_argument('--serve', action='store_true')
    args = parser.parse_args()
    if sys.platform != 'linux':
        parser.error('Run this helper on the AutoDL Linux GPU instance')
    if digest(PROTOCOL) != args.protocol_sha256:
        raise ValueError('Application test protocol transfer mismatch')
    recipe = json.loads(PROTOCOL.read_text())
    validate_resources(recipe)
    from transformers import AutoTokenizer
    from code_repair.agent_protocol import initial_messages
    from code_repair.contracts import TOOL_SCHEMAS
    from code_repair.final_test import load_final_public_task
    model = recipe['models'][args.stage]
    path = Path(model['remote_path'])
    if digest(path / 'model.safetensors') != model['sha256']:
        raise ValueError('Model does not match frozen candidate')
    if importlib.metadata.version('vllm') != '0.11.0':
        raise ValueError('Expected the original vLLM 0.11.0 environment')
    tokenizer = AutoTokenizer.from_pretrained(path, local_files_only=True)
    prompts = {}
    for row in recipe['tasks']:
        task = load_final_public_task(PUBLIC, row['task_id'], recipe['public_manifest_sha256'])
        ids = tokenizer.apply_chat_template(initial_messages(task), tools=TOOL_SCHEMAS,
            add_generation_prompt=True, tokenize=True)
        if not 0 < len(ids) <= recipe['max_prompt_length']:
            raise ValueError('Initial test prompt exceeds fixed budget')
        prompts[row['task_id']] = {'tokens': len(ids),
            'sha256': hashlib.sha256(json.dumps(ids, separators=(',', ':')).encode()).hexdigest()}
    alias = 'zzh-repair-' + args.stage
    command = [sys.executable, '-m', 'vllm.entrypoints.openai.api_server', '--model', str(path),
        '--served-model-name', alias, '--host', '127.0.0.1', '--port', '8000',
        '--dtype', 'bfloat16', '--max-model-len', '4608', '--max-num-seqs', '1',
        '--gpu-memory-utilization', '0.6', '--generation-config', 'vllm', '--enforce-eager']
    evidence = {'stage': args.stage, 'model_alias': alias, 'model_path': str(path),
        'model_sha256': model['sha256'], 'protocol_sha256': digest(PROTOCOL),
        'helper_sha256': digest(__file__), 'vllm_version': '0.11.0',
        'checked_at': datetime.now(timezone.utc).isoformat(), 'initial_test_prompts': prompts,
        'generation_config': json.loads((path / 'generation_config.json').read_text()),
        'core_files_sha256': recipe['core_files_sha256'], 'command': command,
        'server_ready': False, 'application_test_executed': False, 'training_performed': False}
    destination = ROOT / 'runs/application_test' / f'model-{args.stage}.json'
    write_json(destination, evidence)
    print('MODEL AND TEST PROMPTS VERIFIED; API readiness still needs checking:', destination, flush=True)
    if not args.serve:
        return
    gpu = subprocess.run(['nvidia-smi', '--query-compute-apps=pid', '--format=csv,noheader'],
        capture_output=True, text=True, timeout=10, check=True)
    if gpu.stdout.strip():
        raise RuntimeError('GPU occupied; inspect the owner before changing its process')
    os.environ['HF_HUB_OFFLINE'] = '1'
    os.environ['TRANSFORMERS_OFFLINE'] = '1'
    os.execv(sys.executable, command)


if __name__ == '__main__':
    main()
