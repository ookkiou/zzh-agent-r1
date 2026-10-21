"""Package pinned training sources and diagnostics; no installation or model download."""

import gzip
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import tarfile

ROOT = Path(__file__).resolve().parents[1]
PREFIX = 'agent-r1-day6'


def digest(content):
    return hashlib.sha256(content).hexdigest()


def build():
    lock = json.loads((ROOT / 'TRAINING_SOURCE_LOCK.json').read_text())
    contents = {name: (ROOT / name).read_bytes() for name in (
        'TRAINING_SOURCE_LOCK.json', 'scripts/day6_preflight.py', 'docs/DAY6_RUNBOOK.md')}
    for component, archive_name, destination in (
        ('agent_r1', 'agent-r1-' + lock['agent_r1']['commit'] + '.tar.gz', 'runs/day6/Agent-R1'),
        ('verl', 'verl-v0.7.0.tar.gz', 'runs/day6/verl'),
    ):
        archive_bytes = (ROOT / 'runs/day6' / archive_name).read_bytes()
        if digest(archive_bytes) != lock[component]['archive_sha256']:
            raise ValueError(component + ' archive checksum mismatch')
        with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode='r:gz') as archive:
            if archive.pax_headers.get('comment') != lock[component]['commit']:
                raise ValueError(component + ' archive commit mismatch')
            entries = archive.getmembers()
            top = PurePosixPath(entries[0].name).parts[0]
            if sum(entry.size for entry in entries) > 100_000_000:
                raise ValueError('Expanded source exceeds 100MB')
            for entry in entries:
                path = PurePosixPath(entry.name)
                if path.is_absolute() or '..' in path.parts or path.parts[0] != top:
                    raise ValueError('Unsafe source path')
                if entry.isdir():
                    continue
                if not entry.isfile():
                    raise ValueError('Source links and special files are not permitted')
                relative = PurePosixPath(*path.parts[1:])
                key = destination + '/' + str(relative)
                if key in contents:
                    raise ValueError('Duplicate source member')
                contents[key] = archive.extractfile(entry).read()
    for name, expected in lock['agent_r1']['reviewed_files_sha256'].items():
        if digest(contents['runs/day6/Agent-R1/' + name]) != expected:
            raise ValueError('Reviewed source mismatch')
    contents['UPLOAD_README.md'] = (
        '# Day 6 diagnostic bundle\n\n'
        'No credentials, model weights or private repair tests are included.\n'
        'Extract under your selected data directory, then enter agent-r1-day6.\n\n'
        'Run `python3 scripts/day6_preflight.py --output reports/day6_server_preflight.json`.\n'
        'Missing dependencies and no-GPU mode are expected to fail readiness checks.\n'
        'This command does not install packages or train.\n\n'
        'Pinned sources: runs/day6/Agent-R1 and runs/day6/verl.\n'
        'Dependency installation and single-GPU launcher still require host validation.\n'
        'Training-stage completion must not be inferred from this bundle.\n'
    ).encode()
    manifest = {name: {'sha256': digest(value), 'bytes': len(value)} for name, value in sorted(contents.items())}
    contents['BUNDLE_MANIFEST.json'] = (json.dumps(manifest, indent=2) + '\n').encode()
    output = ROOT / 'runs/day6/day6-bootstrap.tar.gz'
    temporary = output.with_suffix('.tmp')
    with temporary.open('wb') as stream, gzip.GzipFile(filename='', fileobj=stream, mode='wb', mtime=0) as zipped:
        with tarfile.open(fileobj=zipped, mode='w') as archive:
            for name, content in sorted(contents.items()):
                item = tarfile.TarInfo(PREFIX + '/' + name)
                item.size, item.mode, item.mtime = len(content), 0o644, 0
                archive.addfile(item, io.BytesIO(content))
    # Verify every packaged byte before publishing the generated bundle.
    with tarfile.open(temporary) as archive:
        packaged = {entry.name.removeprefix(PREFIX + '/'): archive.extractfile(entry).read()
                    for entry in archive.getmembers()}
    if packaged != contents:
        raise ValueError('Bundle self-verification failed')
    temporary.replace(output)
    report = {'schema_version': 1, 'bundle': str(output.relative_to(ROOT)),
              'sha256': digest(output.read_bytes()), 'bytes': output.stat().st_size,
              'file_count': len(contents), 'source_archives_and_commit_verified': True,
              'all_packaged_bytes_verified': True, 'includes_model_weights': False,
              'includes_private_repair_tests': False, 'training_runtime_verified': False,
              'day6_complete': False}
    (ROOT / 'reports/day6_bootstrap.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    build()
