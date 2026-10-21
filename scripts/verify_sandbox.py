"""Actual Docker isolation probes. Never run resource probes on the local backend."""

import argparse
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from code_repair.execution import DockerBackend


class RecordingDocker(DockerBackend):
    def __init__(self, image):
        super().__init__(image)
        self.names = []

    def command(self, name):
        self.names.append(name)
        return super().command(name)


ISOLATION = '''
import os, pathlib, socket
def probe(host_path):
    status = dict(line.split(':', 1) for line in pathlib.Path('/proc/self/status').read_text().splitlines() if ':' in line)
    root = next(line.split()[3].split(',') for line in pathlib.Path('/proc/mounts').read_text().splitlines() if line.split()[1] == '/')
    def blocked(path):
        try:
            pathlib.Path(path).write_text('blocked')
            return False
        except OSError:
            return True
    pathlib.Path('/tmp/writable').write_text('ok')
    sock = socket.socket()
    sock.settimeout(0.5)
    try:
        sock.connect(('1.1.1.1', 443))
        network_blocked = False
    except OSError:
        network_blocked = True
    finally:
        sock.close()
    return {'uid': os.getuid(), 'euid': os.geteuid(), 'cap_eff': status['CapEff'].strip(),
            'no_new_privs': status['NoNewPrivs'].strip(), 'root_ro': 'ro' in root,
            'root_write_blocked': blocked('/usr/local/probe'), 'network_blocked': network_blocked,
            'interfaces': dict((path.name, path.joinpath('flags').read_text().strip())
                               for path in pathlib.Path('/sys/class/net').iterdir() if path.is_dir()),
            'routes': pathlib.Path('/proc/net/route').read_text().splitlines()[1:],
            'host_path_absent': not os.path.exists(host_path),
            'host_env_absent': 'CODE_REPAIR_HOST_SENTINEL' not in os.environ,
            'tmp_writable': pathlib.Path('/tmp/writable').read_text() == 'ok',
            'tmp_bytes': os.statvfs('/tmp').f_blocks * os.statvfs('/tmp').f_frsize,
            'memory_max': pathlib.Path('/sys/fs/cgroup/memory.max').read_text().strip(),
            'pids_max': pathlib.Path('/sys/fs/cgroup/pids.max').read_text().strip(),
            'cpu_max': pathlib.Path('/sys/fs/cgroup/cpu.max').read_text().strip()}
'''

PID_LIMIT = '''
import os, signal, time
def probe():
    children = []
    limited = False
    try:
        for _ in range(40):
            try:
                pid = os.fork()
            except BlockingIOError:
                limited = True
                break
            if pid == 0:
                time.sleep(10)
                os._exit(0)
            children.append(pid)
        return {'limited': limited, 'children': len(children)}
    finally:
        for pid in children:
            os.kill(pid, signal.SIGKILL)
            os.waitpid(pid, 0)
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', help='Defaults to SANDBOX_LOCK.json image')
    parser.add_argument('--output', type=Path, default=ROOT / 'reports/sandbox_verification.json')
    args = parser.parse_args()
    image = args.image or json.loads((ROOT / 'SANDBOX_LOCK.json').read_text())['image']
    backend = RecordingDocker(image)
    checks, details = {}, {}

    def run(name, source, inputs=None, timeout=5):
        result = backend.execute(source, 'probe', inputs or [[]], timeout=timeout)
        details[name] = {'status': result.status, 'rows': result.rows, 'elapsed_seconds': result.elapsed_seconds,
                         'detail': result.detail}
        print(f'{name}: {result.status}', flush=True)
        return result

    with tempfile.TemporaryDirectory(prefix='sandbox-host-sentinel-') as directory:
        sentinel = Path(directory) / 'host-only.txt'
        sentinel.write_text('host-only')
        os.environ['CODE_REPAIR_HOST_SENTINEL'] = 'must-not-inherit'
        try:
            result = run('isolation', ISOLATION, [[str(sentinel)]])
        finally:
            os.environ.pop('CODE_REPAIR_HOST_SENTINEL', None)
        checks['probe_completed'] = result.status == 'completed' and result.rows[0]['kind'] == 'return'
        values = result.rows[0]['value'] if checks['probe_completed'] else {}
        checks.update({
            'non_root': values.get('uid') == values.get('euid') == 65534,
            'capabilities_dropped': values.get('cap_eff') == '0000000000000000',
            'no_new_privileges': values.get('no_new_privs') == '1',
            'read_only_root': values.get('root_ro') is True and values.get('root_write_blocked') is True,
            'no_network': ('lo' in values.get('interfaces', {}) and values.get('network_blocked') is True
                           and values.get('routes') == [] and all(
                               name == 'lo' or not int(flags, 16) & 1
                               for name, flags in values.get('interfaces', {}).items())),
            'no_host_mount_or_env': values.get('host_path_absent') is True and values.get('host_env_absent') is True,
            'bounded_writable_tmp': values.get('tmp_writable') is True and values.get('tmp_bytes') == 16777216,
            'memory_256m': values.get('memory_max') == '268435456',
            'pids_32': values.get('pids_max') == '32',
        })
        cpu = values.get('cpu_max', '').split()
        checks['cpu_one_core'] = len(cpu) == 2 and cpu[0] == cpu[1]

    result = run('tmp_isolation', "import pathlib\ndef probe(): return not pathlib.Path('/tmp/writable').exists()")
    checks['fresh_container_each_run'] = result.status == 'completed' and result.rows[0].get('value') is True
    result = run('timeout', 'def probe():\n    while True: pass\n', timeout=1)
    checks['infinite_loop_timeout'] = result.status == 'timeout'
    result = run('output_flood', "import os\ndef probe():\n    while True: os.write(1, b'x' * 4096)\n")
    checks['bounded_output'] = result.status == 'output_limit'
    result = run('pid_exhaustion', PID_LIMIT)
    checks['fork_limit_enforced'] = result.status == 'completed' and result.rows[0].get('value', {}).get('limited') is True
    result = run('memory_exhaustion', 'def probe(): return len(bytearray(384 * 1024 * 1024))')
    checks['memory_exhaustion_rejected'] = result.status == 'candidate_error'
    for name in backend.names:
        listed = subprocess.run(['docker', 'ps', '-a', '--filter', 'name=^/' + name + '$', '--format', '{{.Names}}'],
                                capture_output=True, text=True, timeout=10)
        checks['cleanup_' + name] = listed.returncode == 0 and not listed.stdout.strip()
    version = subprocess.run(['docker', 'version', '--format', '{{json .}}'], capture_output=True, text=True, timeout=10)
    report = {'schema_version': 1, 'verified_at': datetime.now(timezone.utc).isoformat(), 'backend': 'docker',
              'image': image, 'docker_version': json.loads(version.stdout) if version.returncode == 0 else None,
              'uses_model': False, 'checks': checks, 'probes': details, 'complete': all(checks.values())}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(f'Isolation checks: {sum(checks.values())}/{len(checks)}; complete={report["complete"]}', flush=True)
    return 0 if report['complete'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
