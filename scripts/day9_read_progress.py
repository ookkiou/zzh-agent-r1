"""Read live Day9 progress over SSH without changing the remote training job."""
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
REMOTE_PROBE = r'''
from datetime import datetime, timezone
import json, re, shutil, subprocess, sys
from pathlib import Path

root = Path('/root/autodl-tmp/agent-r1-day6')
expected = 'b9f93ec5dadf42c1199427e5ba425cc2a864daad30caae599aa27d22a6092f32'
records = sorted((root/'runs/day9/launch').glob('formal-execute-*.json'), key=lambda p:p.stat().st_mtime)
if not records:
    raise RuntimeError('No formal execution record')
record = json.loads(records[-1].read_text())
if record['run_fingerprint'] != expected:
    raise RuntimeError('Unexpected run identity')
attempt = record['attempt']
log = root/'reports'/('day9_formal_execute_'+attempt+'.log')
text = log.read_text(errors='replace') if log.exists() else ''
progress = re.findall(r'Training Progress:[^\r\n]*', text)
metrics = []
for line in text.splitlines():
    if 'training/global_step:' in line:
        fields = dict(re.findall(r'([\w/]+):(-?(?:\d+\.?\d*|\.\d+)(?:e[+-]?\d+)?)', line))
        metrics.append({k:float(fields[k]) for k in ('training/global_step','timing_s/step','actor/grad_norm','actor/kl_loss','critic/score/trajectory/mean') if k in fields})
steps = [int(re.search(r'training/global_step:(\d+)', line).group(1)) for line in text.splitlines() if re.search(r'training/global_step:(\d+)', line)]
for line in progress:
    match = re.search(r'(\d+)/225', line)
    if match: steps.append(int(match[1]))
pid_path = root/'reports/day9_formal_pid.json'
pid = json.loads(pid_path.read_text())['pid'] if pid_path.exists() else None
cmdpath = Path('/proc')/str(pid)/'cmdline'
cmdline = cmdpath.read_bytes() if cmdpath.exists() else b''
running = b'day9_train.py' in cmdline and b'formal' in cmdline
checkpoint = Path('/root/zzh-day9-checkpoints')
completed = []
pending = []
for directory in checkpoint.glob('global_step_*'):
    marker = directory/'zzh_completed_checkpoint.json'
    if not marker.exists():
        pending.append(directory.name)
        continue
    try:
        info = json.loads(marker.read_text())
        valid = (not directory.is_symlink() and not marker.is_symlink()
            and info['fingerprint'] == expected
            and directory.name == 'global_step_'+str(info['global_step'])
            and info.get('model_extra_and_dataloader_saved')
            and {'data.pt','actor/model_world_size_1_rank_0.pt','actor/extra_state_world_size_1_rank_0.pt'}.issubset(info['files']))
        for name, size in info['files'].items():
            path = directory/name
            valid = valid and path.resolve().is_relative_to(directory.resolve()) and not path.is_symlink() and path.is_file() and size > 0 and path.stat().st_size == size
        if valid: completed.append(info['global_step'])
        else: pending.append(directory.name)
    except (OSError, ValueError, KeyError):
        pending.append(directory.name)
gpu = subprocess.run(['nvidia-smi','--query-gpu=memory.used,memory.total,utilization.gpu','--format=csv,noheader'], capture_output=True, text=True, timeout=10)
sys.path.insert(0, str(root))
try:
    from code_repair.evaluation import RemoteEvaluator
    token = (root/'runs/day6/evaluator_token').read_text().strip()
    health = RemoteEvaluator('http://127.0.0.1:18765', token, 'mbpp-627-x01').health()
    evaluator = {'ok':health.get('status') == 'ok' and health.get('backend') == 'docker' and health.get('container_isolation_configured') is True and health.get('task_count') == 332 and '37b846babd6d9949e2247752042c3669d618d0f367212b65ba32e39717da9555' in health.get('dataset_manifest_sha256', []), 'task_count':health.get('task_count')}
except Exception as error:
    evaluator = {'ok':False, 'error_type':type(error).__name__}
print(json.dumps({'observed_at':datetime.now(timezone.utc).isoformat(),
    'attempt':attempt, 'run_fingerprint':expected, 'running':running, 'pid':pid,
    'reported_completed_step':max(steps) if steps else None, 'target_steps':225,
    'progress_line':progress[-1] if progress else None,
    'latest_metrics':metrics[-1] if metrics else None,
    'completed_checkpoint_steps':sorted(completed), 'pending_or_invalid_checkpoints':pending,
    'returncode':record.get('returncode'), 'log':str(log),
    'log_modified_at':datetime.fromtimestamp(log.stat().st_mtime, timezone.utc).isoformat() if log.exists() else None,
    'errors':[line[-400:] for line in text.splitlines() if any(term in line for term in ('Traceback (most recent call last)', 'OutOfMemoryError', 'CUDA error:', 'Repeated batches lack relative reward signal'))][-4:],
    'gpu_memory_used_total_and_utilization':gpu.stdout.strip(),
    'checkpoint_disk_free_gib':round(shutil.disk_usage(checkpoint).free/1024**3, 2),
    'evaluator':evaluator, 'checkpoint_check':'completion marker and file sizes; no weight hashing',
    'ability_improvement_verified':False}, ensure_ascii=False))
'''


def main():
    command = ['ssh', '-i', str(ROOT/'runs/ssh/autodl_day6_ed25519'),
        '-p', '37856', '-o', 'IdentitiesOnly=yes', '-o', 'BatchMode=yes',
        '-o', 'StrictHostKeyChecking=yes', '-o', 'ConnectTimeout=10',
        '-o', 'ServerAliveInterval=10', '-o', 'ServerAliveCountMax=2',
        'root@connect.westc.seetacloud.com',
        '/root/autodl-tmp/agent-r1-day6/.venv/bin/python -']
    result = subprocess.run(command, input=REMOTE_PROBE, text=True,
        capture_output=True, timeout=45)
    if result.returncode:
        print(json.dumps({'read_success':False, 'ssh_returncode':result.returncode,
            'error':result.stderr[-1200:]}, ensure_ascii=False))
        return 1
    report = json.loads(result.stdout)
    target = ROOT/'reports/day9_live_progress.json'
    if target.exists():
        previous = json.loads(target.read_text())
        report['previous_observation'] = {k:previous.get(k) for k in
            ('observed_at','attempt','reported_completed_step','running')}
    temporary = target.with_suffix('.tmp')
    temporary.write_text(json.dumps(report, ensure_ascii=False, indent=2)+'\n')
    temporary.replace(target)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    sys.exit(main())
