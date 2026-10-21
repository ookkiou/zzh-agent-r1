"""Download public model files, verifying every byte against official pinned metadata."""

import hashlib
import json
from pathlib import Path
import time
import urllib.request

ROOT = Path(__file__).resolve().parents[1]
STATUS = ROOT / 'reports/day6_model_download_status.json'


def file_hash(path, item):
    algorithm = hashlib.sha256() if item['lfs'] else hashlib.sha1()
    if not item['lfs']:
        algorithm.update(f'blob {item["size"]}\0'.encode())
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            algorithm.update(chunk)
    return algorithm.hexdigest()


def main():
    lock = json.loads((ROOT / 'reports/day6_model_files.lock.json').read_text())
    model = ROOT / 'models' / ('qwen-coder-1.5b-' + lock['revision'])
    model.mkdir(parents=True, exist_ok=True)
    status = {'revision': lock['revision'], 'path': str(model), 'files': [], 'complete': False}
    for item in lock['files']:
        if item['name'] == '.gitattributes':
            continue
        if Path(item['name']).name != item['name'] or not item['size']:
            raise ValueError('Unsupported model file metadata')
        target = model / item['name']
        expected = item['lfs']['sha256'] if item['lfs'] else item['git_blob_id']
        status['current_file'] = item['name']
        STATUS.write_text(json.dumps(status, indent=2) + '\n')
        if target.exists() and target.stat().st_size == item['size'] and file_hash(target, item) == expected:
            status['files'].append({'name': item['name'], 'verified': True})
            continue
        urls = [f'https://hf-mirror.com/{lock["repository"]}/resolve/{lock["revision"]}/{item["name"]}',
                f'https://modelscope.cn/api/v1/models/{lock["repository"]}/repo?Revision=master&FilePath={item["name"]}']
        succeeded = False
        partial = target.with_suffix(target.suffix + '.partial')
        for url in urls:
            try:
                offset = partial.stat().st_size if partial.exists() else 0
                headers = {'User-Agent': 'agent-r1-day6/1.0'}
                if offset:
                    headers['Range'] = f'bytes={offset}-'
                request = urllib.request.Request(url, headers=headers)
                started, reported = time.monotonic(), offset
                with urllib.request.urlopen(request, timeout=30) as response:
                    append = offset > 0 and response.status == 206
                    total = offset if append else 0
                    with partial.open('ab' if append else 'wb') as stream:
                        while chunk := response.read(4 * 1024 * 1024):
                            total += len(chunk)
                            if total > item['size'] or time.monotonic() - started > 1800:
                                raise ValueError('Download exceeded bounds')
                            stream.write(chunk)
                            if total - reported >= 64 * 1024 * 1024:
                                print(f'{item["name"]}: {total}/{item["size"]} bytes', flush=True)
                                reported = total
                if partial.stat().st_size != item['size'] or file_hash(partial, item) != expected:
                    partial.unlink(missing_ok=True)
                    raise ValueError('File checksum mismatch')
                partial.replace(target)
                print(item['name'] + ': verified', flush=True)
                succeeded = True
                break
            except (OSError, ValueError) as error:
                print(item['name'] + ': ' + type(error).__name__ + ': ' + str(error), flush=True)
        if not succeeded:
            status['failed_file'] = item['name']
            STATUS.write_text(json.dumps(status, indent=2) + '\n')
            return 1
        status['files'].append({'name': item['name'], 'verified': True})
    status['complete'] = True
    STATUS.write_text(json.dumps(status, indent=2) + '\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
