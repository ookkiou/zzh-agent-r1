"""Create a local allowlisted evidence bundle; never upload or include credentials/weights."""
import gzip
import io
import json
from pathlib import Path
import re
import tarfile

from build_day15_delivery import ROOT, OUT, SOURCES, CASES, digest

MANIFEST=OUT/'delivery_manifest.json'
ARCHIVE=OUT/'zzh-repair-evidence.tar.gz'
PREFIX='zzh-repair-evidence'
SCRIPTS=['scripts/build_day15_delivery.py','scripts/day15_demo.py',
         'scripts/check_day15.py','scripts/package_day15.py']


def selected_files():
    names=set(SOURCES+SCRIPTS)
    names.update(str(p.relative_to(ROOT)) for p in (ROOT/'docs').glob('*.md'))
    assets=['metrics.json','case_index.json','training_observations.csv','sft_updates.csv','evaluation_summary.csv']
    for stem in ('sft_training','training_diagnostics','evaluation_comparison'):
        assets.extend('figures/'+stem+suffix for suffix in ('.png','.pdf'))
    for slug,task,seed,title,old,new in CASES:
        assets.extend('cases/'+slug+suffix for suffix in ('.json','.md'))
        assets.extend('source_public/'+task+'/'+name for name in ('task.json','solution.py'))
    names.update('artifacts/day15/'+name for name in assets)
    return sorted(names)


def checked_bytes(relative, secrets):
    path=ROOT/relative
    if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(ROOT):
        raise ValueError('Not a regular allowlisted local file: '+relative)
    if any(part in ('.env','ssh','evaluator_token','private_tests.json','reference') for part in Path(relative).parts):
        raise ValueError('Forbidden credential/oracle path')
    if path.suffix in ('.pt','.safetensors'):
        raise ValueError('Weights cannot enter the evidence bundle')
    data=path.read_bytes()
    if any(secret and secret in data for secret in secrets):
        raise ValueError('Credential value found; refusing to package '+relative)
    if re.search(rb'-----BEGIN (?:OPENSSH |RSA |EC )?PRIVATE KEY-----',data):
        raise ValueError('Private key found')
    return data


def main():
    names=selected_files()
    token_path=ROOT/'runs/day6/evaluator_token'
    secrets=[token_path.read_bytes().strip()] if token_path.exists() else []
    payload={name:checked_bytes(name,secrets) for name in names}
    manifest={'schema_version':1,'scope':'offline evidence recalculation and recorded dev replay',
        'contains_full_training_source':False,'contains_model_weights':False,
        'contains_private_test_inputs':False,'uploaded':False,
        'files':{name:digest(ROOT/name) for name in names}}
    content=(json.dumps(manifest,ensure_ascii=False,indent=2)+'\n').encode()
    MANIFEST.write_bytes(content)
    payload[str(MANIFEST.relative_to(ROOT))]=content
    with ARCHIVE.open('wb') as raw:
        with gzip.GzipFile(fileobj=raw,mode='wb',filename='',mtime=0) as compressed:
            with tarfile.open(fileobj=compressed,mode='w') as archive:
                for name,data in sorted(payload.items()):
                    info=tarfile.TarInfo(PREFIX+'/'+name)
                    info.size=len(data);info.mode=0o644;info.mtime=0;info.uid=info.gid=0
                    archive.addfile(info,io.BytesIO(data))
    checksum=digest(ARCHIVE)
    ARCHIVE.with_suffix(ARCHIVE.suffix+'.sha256').write_text(checksum+'  '+ARCHIVE.name+'\n')
    report={'complete':True,'archive':str(ARCHIVE.relative_to(ROOT)),'bytes':ARCHIVE.stat().st_size,
        'sha256':checksum,'files':len(payload),'allowlisted':True,'credential_value_scan_passed':True,
        'uploaded':False,'model_weights_included':False,'private_test_inputs_included':False}
    (ROOT/'reports/day15_package.json').write_text(json.dumps(report,indent=2)+'\n') if (ROOT/'reports').exists() else None
    print(json.dumps(report,indent=2))


if __name__=='__main__':
    main()
