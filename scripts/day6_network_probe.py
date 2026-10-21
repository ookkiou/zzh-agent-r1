"""Measure a bounded public wheel transfer and preserve completed project wheels."""

import json
from pathlib import Path
import shutil
import time
import urllib.request
import zipfile

ROOT = Path(__file__).resolve().parents[1]
RESOURCE = '/pypi/packages/47/33/d19e0763c34392ec956534536fa837c060495bfff31ed83452135ea7608d/vllm-0.11.0-cp38-abi3-manylinux1_x86_64.whl'


def main():
    output = ROOT / 'wheels'
    output.mkdir(exist_ok=True)
    preserved = []
    for path in (ROOT / '.tmp').rglob('*.whl'):
        if zipfile.is_zipfile(path):
            target = output / path.name
            if not target.exists():
                shutil.copy2(path, target)
            preserved.append(path.name)
    rows = []
    for url in ('https://mirrors.aliyun.com' + RESOURCE, 'http://mirrors.aliyun.com' + RESOURCE):
        started = time.monotonic()
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers={'Range': 'bytes=0-1048575'}), timeout=15) as response:
                data = response.read(1048576)
            rows.append({'scheme': url.split(':')[0], 'bytes': len(data), 'seconds': time.monotonic() - started})
        except OSError as error:
            rows.append({'scheme': url.split(':')[0], 'error': type(error).__name__})
    report = {'preserved_wheels': preserved, 'measurements': rows}
    (ROOT / 'reports/day6_network_probe.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
