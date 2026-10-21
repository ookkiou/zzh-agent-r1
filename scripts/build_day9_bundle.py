"""Build a deterministic public-only overlay for the existing pinned Day6 instance."""
import gzip
import hashlib
import io
import json
from pathlib import Path
import tarfile

ROOT=Path(__file__).resolve().parents[1]


def main():
    files=list((ROOT/'code_repair').glob('*.py'))
    files += [ROOT/'scripts'/name for name in ('day9_prepare.py','day9_train.py','day9_preflight.py',
        'day9_storage.py','day9_verify_reload.py','day9_control.py','day9_pipeline.py','day9_snapshot.py','day9_collect_evidence.py')]
    files += [ROOT/'training/code_repair/day9.yaml',ROOT/'training/day9/run_plan.json',ROOT/'TRAINING_SOURCE_LOCK.json']
    files += [ROOT/'runs/day9'/name for name in ('input_identity.json','train.jsonl','dev.jsonl')]
    files += [ROOT/'reports'/name for name in ('day7_sft_checkpoint_manifest.json','day9_preparation.json','day9_docker_data_validation.json')]
    public=ROOT/'runs/day9/public_data';manifest=json.loads((public/'manifest.json').read_text())
    files += [public/'manifest.json']+[public/name for name in manifest['files']]
    payload={}
    for path in sorted(set(files)):
        name=str(path.relative_to(ROOT))
        if path.is_symlink() or not path.is_file():raise ValueError('Regular file required: '+name)
        if any(part in ('reference','ssh','.venv','data') for part in Path(name).parts) or path.name=='private_tests.json':
            raise ValueError('Disallowed overlay resource: '+name)
        payload[name]=path.read_bytes()
    identity={'files':{name:hashlib.sha256(data).hexdigest() for name,data in payload.items()},
        'needs_existing_day6_environment_and_day7_sft':True,
        'contains_credentials_or_private_cases_or_reference_sources':False}
    payload['runs/day9/overlay_manifest.json']=(json.dumps(identity,sort_keys=True,indent=2)+'\n').encode()
    archive=ROOT/'runs/day9/day9-overlay.tar.gz'
    with archive.open('wb') as output:
        with gzip.GzipFile(fileobj=output,filename='',mode='wb',mtime=0) as zipped:
            with tarfile.open(fileobj=zipped,mode='w') as tar:
                for name,data in sorted(payload.items()):
                    member=tarfile.TarInfo(name);member.size=len(data);member.mode=0o644;member.mtime=0
                    tar.addfile(member,io.BytesIO(data))
    with tarfile.open(archive) as tar:
        actual={m.name:tar.extractfile(m).read() for m in tar.getmembers()}
    if actual!=payload:raise ValueError('Overlay bytes changed')
    report={'complete':True,'files':len(payload),'bytes':archive.stat().st_size,
        'sha256':hashlib.sha256(archive.read_bytes()).hexdigest(),'archive':str(archive.relative_to(ROOT)),
        'contains_credentials_or_private_cases_or_reference_sources':False,'gpu_runtime_verified':False}
    (ROOT/'reports/day9_bundle.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
