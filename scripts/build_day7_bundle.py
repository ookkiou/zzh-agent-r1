"""Build a checksum manifest and public-only Day-7 overlay for the existing Day-6 project."""

import gzip
import hashlib
import io
import json
from pathlib import Path
import tarfile

ROOT = Path(__file__).resolve().parents[1]


def main():
    files = list((ROOT / 'code_repair').glob('*.py')) + list((ROOT / 'scripts').glob('day7_*.py'))
    files += [ROOT / 'training/code_repair/base.yaml', ROOT / 'TRAINING_SOURCE_LOCK.json']
    files += [ROOT / 'scripts/day6_preflight.py']
    files += [ROOT / 'runs/day7' / name for name in ('selection.json', 'train.jsonl', 'dev.jsonl')]
    public = ROOT / 'runs/day7/public_data'
    manifest = json.loads((public / 'manifest.json').read_text())
    files += [public / 'manifest.json'] + [public / name for name in manifest['files']]
    payload = {}
    for path in sorted(set(files)):
        if path.is_symlink() or not path.is_file():
            raise ValueError('Bundle needs a regular prepared file: ' + str(path))
        name = str(path.relative_to(ROOT))
        if any(part in ('reference', 'ssh', '.venv') for part in Path(name).parts) or path.name == 'private_tests.json':
            raise ValueError('Disallowed bundle resource')
        payload[name] = path.read_bytes()
    bundle_manifest = {'files': {name: hashlib.sha256(data).hexdigest() for name, data in payload.items()},
        'needs_existing_day6_environment_and_weights': True, 'contains_credentials': False,
        'contains_private_cases_or_reference_sources': False}
    payload['runs/day7/overlay_manifest.json'] = (json.dumps(bundle_manifest, sort_keys=True, indent=2) + '\n').encode()
    archive = ROOT / 'runs/day7/day7-overlay.tar.gz'
    with archive.open('wb') as output:
        with gzip.GzipFile(fileobj=output, filename='', mode='wb', mtime=0) as compressed:
            with tarfile.open(fileobj=compressed, mode='w') as tar:
                for name, data in sorted(payload.items()):
                    info = tarfile.TarInfo(name)
                    info.size, info.mode, info.mtime = len(data), 0o644, 0
                    tar.addfile(info, io.BytesIO(data))
    with tarfile.open(archive) as tar:
        actual = {member.name: tar.extractfile(member).read() for member in tar.getmembers()}
    if actual != payload:
        raise ValueError('Overlay byte verification failed')
    report = {'complete': True, 'day7_complete': False, 'files': len(payload), 'bytes': archive.stat().st_size,
        'sha256': hashlib.sha256(archive.read_bytes()).hexdigest(), 'archive': str(archive.relative_to(ROOT)),
        'contains_credentials': False, 'contains_private_or_reference_resources': False,
        'gpu_runtime_verified': False}
    (ROOT / 'reports/day7_bundle.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
