"""Audit staged public files without displaying credential contents or making network requests."""
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]


def main():
    names=[p for p in subprocess.check_output(['git','ls-files','--cached','-z'],cwd=ROOT).decode().split('\0') if p]
    if not names:
        raise ValueError('Stage the reviewed public files before running this check')
    known=[]
    for p in (ROOT/'runs/day6/evaluator_token',ROOT/'runs/final_test/evaluator_token'):
        if p.is_file():known.append(p.read_bytes().strip())
    patterns=[('private_key',rb'-----BEGIN (?:OPENSSH |RSA |EC )?PRIVATE KEY-----'),
        ('github_token',rb'\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{40,})\b'),
        ('api_key',rb'\bsk-[A-Za-z0-9_-]{32,}\b')]
    errors=[];size=0
    for name in names:
        p=Path(name)
        if p.parts[0] in ('runs','.git','.ssh','.publish') or p.name.startswith('.env') or p.suffix in ('.pt','.pth','.safetensors','.ckpt','.pem','.key','.partial','.log'):
            errors.append({'file':name,'reason':'excluded_runtime_or_sensitive_path'})
        data=subprocess.check_output(['git','show',':'+name],cwd=ROOT)
        size+=len(data)
        if len(data)>50*1024*1024:errors.append({'file':name,'reason':'large_file'})
        if any(value and value in data for value in known):errors.append({'file':name,'reason':'known_evaluator_token'})
        for label,pattern in patterns:
            if re.search(pattern,data):errors.append({'file':name,'reason':label})
    sealed=json.loads((ROOT/'training/final_test/evaluation_protocol.json').read_text())
    expected={'reports/day11_candidate_freeze.json':sealed['candidate_freeze_sha256'],
        **sealed['core_files_sha256'],'code_repair/final_test.py':sealed['test_loader_sha256']}
    for name,sha in expected.items():
        data=subprocess.check_output(['git','show',':'+name],cwd=ROOT)
        if hashlib.sha256(data).hexdigest()!=sha:errors.append({'file':name,'reason':'frozen_source_changed'})
    report={'ready':not errors,'staged_files':len(names),'staged_bytes':size,
        'large_weights_excluded':True,'known_credential_value_scan_complete':True,
        'frozen_protocol_files_checked':len(expected),'findings':errors}
    (ROOT/'.publish').mkdir(exist_ok=True)
    (ROOT/'.publish/readiness.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
    return 0 if report['ready'] else 1


if __name__=='__main__':
    raise SystemExit(main())
