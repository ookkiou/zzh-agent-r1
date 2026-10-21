"""Small control helper for this project's own installation/download jobs."""

import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
JOBS = {'install': ('day6_install_runner.py', '.venv/bin/python'),
        'model_download': ('day6_model_download.py', '.venv/bin/python'),
        'flash_attn': ('day6_install_flashattn.py', '.venv/bin/python'),
        'single_config': ('day6_smoke.py', '.venv/bin/python'),
        'single_smoke': ('day6_smoke.py', '.venv/bin/python'),
        'model_protocol': ('day6_model_probe.py', '.venv/bin/python'),
        'stack_validation': ('day6_stack_validate.py', '.venv/bin/python'),
        'single_checkpoint': ('day6_checkpoint_verify.py', '.venv/bin/python'),
        'tool_config': ('day6_smoke.py', '.venv/bin/python'),
        'tool_smoke': ('day6_smoke.py', '.venv/bin/python'),
        'tool_checkpoint': ('day6_checkpoint_verify.py', '.venv/bin/python'),
        'ray_evaluator': ('day6_ray_evaluator_probe.py', '.venv/bin/python'),
        'export_environment': ('day6_export_environment.py', '.venv/bin/python'),
        'evaluator_failure': ('day6_evaluator_failure_probe.py', '.venv/bin/python'),
        'hermes_adapter': ('day6_hermes_adapter_probe.py', '.venv/bin/python'),
        'export_results': ('day6_export_results.py', '.venv/bin/python')}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('status', 'start', 'cancel', 'cleanup-orphans', 'evaluator-health'))
    parser.add_argument('--job', choices=JOBS, default='install')
    parser.add_argument('--group', type=int)
    parser.add_argument('--compact', action='store_true')
    args = parser.parse_args()
    reports = ROOT / 'reports'
    reports.mkdir(exist_ok=True)
    if args.action == 'evaluator-health':
        sys.path.insert(0, str(ROOT))
        from code_repair.evaluation import RemoteEvaluator
        token = (ROOT / 'runs/day6/evaluator_token').read_text().strip()
        result = RemoteEvaluator('http://127.0.0.1:18765', token, 'repair-001').health()
        (reports / 'day6_tunnel_health.json').write_text(json.dumps(result, indent=2) + '\n')
        print(json.dumps(result))
        return
    if args.action == 'cleanup-orphans':
        if args.group is None or args.group <= 1 or Path('/proc', str(args.group)).exists():
            raise SystemExit('Cleanup requires an exited dedicated job leader')
        members = []
        for process in Path('/proc').iterdir():
            if not process.name.isdecimal():
                continue
            try:
                fields = (process / 'stat').read_text().rpartition(')')[2].split()
                if int(fields[2]) == args.group:
                    if str(ROOT).encode() not in (process / 'cmdline').read_bytes():
                        raise SystemExit('Unrecognized group member; refusing cleanup')
                    members.append(int(process.name))
            except (OSError, ValueError, IndexError):
                continue
        if members:
            os.killpg(args.group, signal.SIGTERM)
        print('Project orphan group cleanup', args.group, 'members', members)
        return
    if args.action == 'status':
        if args.compact:
            names = ['day6_install_status.json', 'day6_stack_validation_status.json',
                'day6_model_protocol.json', 'day6_ray_evaluator_health.json',
                'day6_single_smoke_status.json', 'day6_single_checkpoint_verification.json',
                'day6_tool_config_status.json', 'day6_tool_smoke_status.json',
                'day6_tool_checkpoint_verification.json', 'day6_environment.lock.json']
            for name in names:
                if (reports / name).exists():
                    value = json.loads((reports / name).read_text())
                    summary = {key: value[key] for key in ('complete', 'current_step', 'failed_step',
                        'error', 'returncode', 'terminal_reward') if key in value}
                    if name == 'day6_model_protocol.json':
                        summary['tools'] = [s['expected_tool'] for s in value['steps']]
                    print(name + ': ' + json.dumps(summary))
            for job in ('tool_smoke', 'model_protocol', 'tool_checkpoint'):
                path = reports / ('day6_' + job + '.log')
                if path.exists():
                    print(path.name + ': ' + '\n'.join(path.read_text(errors='replace').splitlines()[-4:])[-2500:])
            return
        for job in JOBS:
            status = reports / ('day6_' + job + '_status.json')
            log = reports / ('day6_' + job + '.log')
            if status.exists():
                print(status.name + ':\n' + status.read_text())
            if log.exists():
                print(log.name + ':\n' + '\n'.join(log.read_text(errors='replace').splitlines()[-12:]))
        downloads = [(str(path.relative_to(ROOT)), path.stat().st_size)
                     for directory in (ROOT / '.tmp', ROOT / 'models') if directory.exists()
                     for path in directory.rglob('*') if path.is_file() and path.stat().st_size > 1024 * 1024]
        print('Download files: ' + json.dumps(sorted(downloads, key=lambda row: row[1], reverse=True)[:8]))
        return
    pid_path = reports / ('day6_' + args.job + '_pid.json')
    if pid_path.exists():
        pid = json.loads(pid_path.read_text())['pid']
        proc = Path('/proc') / str(pid) / 'cmdline'
        if proc.exists() and JOBS[args.job][0].encode() in proc.read_bytes():
            if args.action == 'cancel':
                if os.getpgid(pid) != pid:
                    raise SystemExit('Unexpected process group; refusing cleanup')
                os.killpg(pid, signal.SIGTERM)
                print('Cancelled project job', args.job, pid)
                return
            raise SystemExit('Job is already running')
    if args.action == 'cancel':
        raise SystemExit('No matching running project job')
    script, executable = JOBS[args.job]
    with (reports / ('day6_' + args.job + '.log')).open('ab') as output:
        command = [str(ROOT / executable), str(ROOT / 'scripts' / script)]
        if args.job in ('single_smoke', 'tool_smoke'):
            command.append('--execute')
        if args.job.startswith('tool_'):
            command.extend(['--stage', 'tool'])
        process = subprocess.Popen(command, cwd=ROOT,
                                   stdin=subprocess.DEVNULL, stdout=output, stderr=subprocess.STDOUT,
                                   start_new_session=True)
    pid_path.write_text(json.dumps({'pid': process.pid}) + '\n')
    print(args.job, 'started', process.pid)


if __name__ == '__main__':
    main()
