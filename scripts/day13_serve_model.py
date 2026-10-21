"""User-operated AutoDL preflight/serve. No downloads, training or process termination."""
import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

MODELS = {
    'step70': ('/root/zzh-day9-eval/merged-step70',
        '40915da114c198d947b2b99482fdb3b96ba8bade9cb0b7fb33c53e79e1bb986d'),
    'sft': (str(ROOT/'runs/day7/sft_warmup/merged'),
        'f507ccbddb9881ae7bdd841cd2ba8fdf02e54661d04e83fad7e97d2f545be346')}


def digest(path):
    result = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(4*1024*1024), b''):
            result.update(chunk)
    return result.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', choices=MODELS, default='step70')
    parser.add_argument('--serve', action='store_true', help='Explicitly start the foreground inference server')
    args = parser.parse_args()
    if sys.platform != 'linux':
        parser.error('Run this on the AutoDL instance; the Mac does not need model weights')
    from transformers import AutoTokenizer
    from code_repair.agent_protocol import initial_messages
    from code_repair.contracts import TOOL_SCHEMAS
    from code_repair.public_data import load_public_task

    path, expected = MODELS[args.stage]
    if digest(Path(path)/'model.safetensors') != expected:
        raise ValueError('Frozen model weight hash mismatch')
    if importlib.metadata.version('vllm') != '0.11.0':
        raise ValueError('Expected the validated vLLM 0.11.0 environment')
    protocol = json.loads((ROOT/'runs/day8/evaluation_protocol.json').read_text())
    if digest(ROOT/'runs/day8/evaluation_protocol.json') != '078b36f56a85e1ef800da548ba042e7296fe6e79cb3b10dfb3c2d492f3338635':
        raise ValueError('Original dev protocol changed')
    for name, sha in protocol['core_files_sha256'].items():
        if digest(ROOT/name) != sha:
            raise ValueError('Shared repair runtime changed: '+name)
    tokenizer = AutoTokenizer.from_pretrained(path, local_files_only=True)
    prompts = {}
    public = ROOT/'runs/day9/public_data'
    if digest(public/'manifest.json') != '59eb1edb9c7f7ce19e0afa9c441a868d251ba7c704938e620a6584a2fd18c196':
        raise ValueError('Public train/dev export changed')
    for row in protocol['tasks']:
        tokens = tokenizer.apply_chat_template(initial_messages(load_public_task(public,row['task_id'])),
            tools=TOOL_SCHEMAS, add_generation_prompt=True, tokenize=True)
        prompts[row['task_id']] = {'tokens':len(tokens),
            'sha256':hashlib.sha256(json.dumps(tokens,separators=(',',':')).encode()).hexdigest()}
    alias = 'zzh-repair-'+args.stage
    command = [sys.executable, '-m', 'vllm.entrypoints.openai.api_server', '--model', path,
        '--served-model-name', alias, '--host', '127.0.0.1', '--port', '8000',
        '--dtype', 'bfloat16', '--max-model-len', '4608', '--max-num-seqs', '1',
        '--gpu-memory-utilization', '0.6', '--generation-config', 'vllm', '--enforce-eager']
    evidence = {'stage':args.stage, 'model_alias':alias, 'model_path':path, 'model_sha256':expected,
        'vllm_version':'0.11.0', 'checked_at':datetime.now(timezone.utc).isoformat(),
        'helper_sha256':digest(__file__), 'initial_dev_prompts':prompts,
        'generation_config':json.loads((Path(path)/'generation_config.json').read_text()),
        'core_files_sha256':protocol['core_files_sha256'], 'command':command,
        'server_ready':False, 'test_executed':False, 'training_performed':False}
    destination = Path('/root/zzh-day13-model-'+args.stage+'.json')
    destination.write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+'\n')
    print('MODEL FILES VERIFIED; this is not an API readiness check:',destination,flush=True)
    if not args.serve:
        return
    gpu = subprocess.run(['nvidia-smi','--query-compute-apps=pid','--format=csv,noheader'],
        capture_output=True,text=True,timeout=10,check=True)
    if gpu.stdout.strip():
        raise RuntimeError('GPU has an active process; inspect it instead of starting a second server')
    os.environ['HF_HUB_OFFLINE'] = '1'
    os.environ['TRANSFORMERS_OFFLINE'] = '1'
    os.execv(sys.executable, command)


if __name__ == '__main__':
    main()
