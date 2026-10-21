"""Read-only GPU-host diagnostics. Does not install packages, download weights or train."""

import argparse
from datetime import datetime, timezone
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
PACKAGES = ('torch', 'vllm', 'verl', 'ray', 'transformers', 'hydra-core', 'omegaconf',
            'datasets', 'pandas', 'pyarrow', 'flash-attn', 'tensordict')
MODULES = ('torch', 'vllm', 'verl', 'ray', 'transformers', 'hydra', 'omegaconf',
           'datasets', 'pandas', 'pyarrow', 'agent_r1.trainer.main_agent_ppo',
           'agent_r1.agent_flow.agent_flow', 'agent_r1.env.base', 'recipes.gsm8k')


def command(args, *, cwd=None, timeout=15):
    try:
        result = subprocess.run(args, cwd=cwd, stdin=subprocess.DEVNULL, capture_output=True,
                                text=True, timeout=timeout)
        return {'ok': result.returncode == 0, 'returncode': result.returncode,
                'stdout': result.stdout[-20000:], 'stderr': result.stderr[-4000:]}
    except (OSError, subprocess.TimeoutExpired) as error:
        return {'ok': False, 'error': type(error).__name__}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--upstream-dir', type=Path, default=ROOT / 'runs/day6/Agent-R1')
    parser.add_argument('--output', type=Path, default=ROOT / 'reports/day6_preflight.json')
    parser.add_argument('--probe-training-stack', action='store_true',
                        help='Import installed training modules in bounded subprocesses on a Linux GPU host')
    args = parser.parse_args()
    source_lock = json.loads((ROOT / 'TRAINING_SOURCE_LOCK.json').read_text())
    upstream = args.upstream_dir.resolve()
    versions = {}
    for name in PACKAGES:
        try:
            versions[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            versions[name] = None
    source_checks = {name: (upstream / name).is_file() and
                     hashlib.sha256((upstream / name).read_bytes()).hexdigest() == digest
                     for name, digest in source_lock['agent_r1']['reviewed_files_sha256'].items()}
    nvidia = command(['nvidia-smi', '--query-gpu=name,memory.total,driver_version', '--format=csv,noheader'])
    memory = None
    if Path('/proc/meminfo').is_file():
        memory = next((line.strip() for line in Path('/proc/meminfo').read_text().splitlines()
                       if line.startswith('MemTotal:')), None)
    disk = shutil.disk_usage(ROOT)
    verl_root = ROOT / 'runs/day6/verl'
    version_file = verl_root / 'verl/version/version'
    verl_source = {'verified': False}
    if version_file.is_file() and versions['verl']:
        metadata = importlib.metadata.distribution('verl')
        direct_url = json.loads(metadata.read_text('direct_url.json') or '{}')
        expected = source_lock['verl']
        verl_source = {'package_version': versions['verl'], 'direct_url': direct_url,
            'source_version': version_file.read_text().strip(),
            'version_file_sha256': hashlib.sha256(version_file.read_bytes()).hexdigest()}
        verl_source['verified'] = (
            versions['verl'] == expected.get('normalized_package_version')
            and verl_source['source_version'] == expected.get('source_package_version')
            and verl_source['version_file_sha256'] == expected.get('version_file_sha256')
            and direct_url.get('url') == verl_root.as_uri()
            and direct_url.get('dir_info', {}).get('editable') is True)
    imports = {}
    cuda = {'ok': False, 'not_run': True}
    if args.probe_training_stack and platform.system() == 'Linux' and nvidia['ok'] and all(source_checks.values()):
        for module in MODULES:
            # The module name is a fixed allowlist, never a model-generated command.
            result = command([sys.executable, '-c', 'import importlib; importlib.import_module(' + repr(module) + ')'],
                             cwd=upstream, timeout=45)
            imports[module] = result
            print(f'import {module}: {"PASS" if result["ok"] else "FAIL"}', flush=True)
        cuda = command([sys.executable, '-c',
            'import json,torch; available=torch.cuda.is_available(); '
            'print(json.dumps({"available":available,"torch_cuda":torch.version.cuda,'
            '"device_count":torch.cuda.device_count()})); '
            'x=torch.ones(8,device="cuda"); assert float(x.sum())==8; torch.cuda.synchronize()'], timeout=45)
    checks = {
        'linux_host': platform.system() == 'Linux',
        'python_312_selected': sys.version_info[:2] == (3, 12),
        'nvidia_driver_accessible': nvidia['ok'],
        'pinned_agent_r1_reviewed_files': all(source_checks.values()),
        'pinned_verl_source_install': verl_source['verified'],
        'core_package_versions_present': all(versions[name] for name in PACKAGES if name != 'flash-attn'),
        'core_imports_passed': bool(imports) and all(item['ok'] for item in imports.values()),
        'cuda_tensor_operation': cuda['ok'],
    }
    report = {'schema_version': 1, 'stage': 'day6-preflight',
              'recorded_at': datetime.now(timezone.utc).isoformat(),
              'host': {'system': platform.system(), 'machine': platform.machine(),
                       'python': platform.python_version(), 'cpu_count': os.cpu_count(),
                       'host_meminfo': memory, 'project_disk_free_bytes': disk.free},
              'packages': versions, 'verl_source_install': verl_source,
              'nvidia_smi': nvidia, 'source_checks': source_checks,
              'imports': imports, 'cuda_probe': cuda, 'checks': checks,
              'preflight_complete': all(checks.values()), 'day6_complete': False,
              'not_covered': ['dependency source revision validation on installed host',
                              'model inference and three-tool protocol roundtrip',
                              'remote executor tunnel and isolation verification',
                              'official training updates and checkpoint evidence'],
              'installs_performed': False, 'weights_downloaded': False, 'training_performed': False}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print(f'Preflight: {sum(checks.values())}/{len(checks)}; complete={report["preflight_complete"]}')
    print('This is a diagnostic report, not day-6 training acceptance.')
    return 0 if report['preflight_complete'] else 1


if __name__ == '__main__':
    raise SystemExit(main())
