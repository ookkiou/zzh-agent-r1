"""Recreate ignored public resource exports after cloning; no model or candidate execution."""
import hashlib
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from code_repair.agent_protocol import PROTOCOL_VERSION


def digest(data):
    return hashlib.sha256(data).hexdigest()


def text(value):
    return json.dumps(value,ensure_ascii=False,indent=2)+'\n'


def export(version, destination):
    source=ROOT/'data/mbpp_repair'/version
    original=json.loads((source/'manifest.json').read_text())
    files={};tasks=[];resources={}
    rows=sorted(original['tasks'],key=lambda r:r['task_id']) if version=='v0.1' else original['tasks']
    for row in rows:
        if row['split'] not in ('train','dev'):
            raise ValueError('Unexpected split')
        for name in ('task.json','starter/solution.py','public_tests.py'):
            relative=row['path']+'/'+name
            value=(source/relative).read_bytes()
            if digest(value)!=original['files'][relative]:
                raise ValueError('Source asset changed: '+relative)
            if version=='v0.2' and name=='task.json':
                metadata=json.loads(value)
                value=text({k:metadata[k] for k in ('task_id','source_id','split','entrypoint','instruction')}).encode()
            resources[relative]=value
            files[relative]=digest(value)
        tasks.append({k:row[k] for k in ('task_id','source_id','split','path')})
    if version=='v0.1':
        manifest={'schema_version':1,'protocol_version':PROTOCOL_VERSION,
            'source_manifest_sha256':digest((source/'manifest.json').read_bytes()),'tasks':tasks,'files':files}
    else:
        manifest={'schema_version':1,'source_manifest_sha256':digest((source/'manifest.json').read_bytes()),
            'parent_manifest_sha256':original['parent_manifest_sha256'],'tasks':tasks,'files':files,
            'redacted_task_metadata_keys':['task_id','source_id','split','entrypoint','instruction']}
    resources['manifest.json']=text(manifest).encode()
    for name,value in resources.items():
        path=destination/name
        if path.exists() and path.read_bytes()!=value:
            raise ValueError('Refusing to overwrite a different export: '+str(path))
        path.parent.mkdir(parents=True,exist_ok=True);path.write_bytes(value)
    return digest(resources['manifest.json'])


def main():
    result={}
    for version,stage in [('v0.1','day7'),('v0.2','day9')]:
        result[stage]=export(version,ROOT/'runs'/stage/'public_data')
    # Reuse the exact frozen test export routine; this function does not execute cases.
    from scripts.verify_final_test import export_public
    source=ROOT/'data/mbpp_repair/test-v0.1'
    manifest=json.loads((source/'manifest.json').read_text())
    result['test'],_=export_public(manifest,digest((source/'manifest.json').read_bytes()))
    expected=json.loads((ROOT/'training/final_test/evaluation_protocol.json').read_text())
    if result['test']!=expected['public_manifest_sha256'] or result['day9']!='59eb1edb9c7f7ce19e0afa9c441a868d251ba7c704938e620a6584a2fd18c196':
        raise ValueError('Rebuilt exports differ from the frozen experiment')
    print(json.dumps({'public_exports_ready':True,'manifest_sha256':result,
        'model_invoked':False,'candidate_code_executed':False},indent=2))


if __name__=='__main__':
    main()
