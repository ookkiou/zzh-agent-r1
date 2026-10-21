"""Bounded Mac-side synchronization and final weight backup for the active Day9 run.

No instance shutdown/release, no scheduling service, and no optimizer checkpoint.
Only this project's service/tunnel/keep-awake processes are cleaned up at the end.
"""
from datetime import datetime,timezone
import hashlib
import io
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tarfile
import time

ROOT=Path(__file__).resolve().parents[1]
HOST='root@connect.westc.seetacloud.com'
REMOTE='/root/autodl-tmp/agent-r1-day6'
OPTIONS=['-i',str(ROOT/'runs/ssh/autodl_day6_ed25519'),'-o','IdentitiesOnly=yes',
    '-o','BatchMode=yes','-o','StrictHostKeyChecking=yes','-o','ConnectTimeout=15']


def ssh(script,timeout=90):
    return subprocess.run(['ssh',*OPTIONS,'-p','37105',HOST,
        REMOTE+'/.venv/bin/python -'],input=script.encode(),capture_output=True,timeout=timeout,check=True).stdout


def synchronize():
    script='''import io,json,subprocess,sys,tarfile
from pathlib import Path
root=Path(REMOTE)
subprocess.run([str(root/'.venv/bin/python'),str(root/'scripts/day9_snapshot.py')],cwd=root,check=True,stdout=subprocess.DEVNULL)
files={}
for pattern in ('day9*.json','day9*.log','day9_gpu_samples.jsonl'):
 for path in (root/'reports').glob(pattern):
  if path.is_file() and not path.is_symlink():files[str(path.relative_to(root))]=path
for path in (root/'runs/day9/launch').glob('*.json'):files[str(path.relative_to(root))]=path
checkpoint=Path('/root/zzh-day9-checkpoints')
for name in ('training_batch_audit.jsonl','checkpoint_events.jsonl','zzh_run_identity.json'):
 path=checkpoint/name
 if path.exists():files['runs/day9/formal/'+name]=path
pipeline=json.loads((root/'reports/day9_pipeline_status.json').read_text())
if pipeline['status'] in ('formal_updates_completed','stopped_for_inspection','paused_by_user'):
 for directory in ('traces','rollouts'):
  for path in (checkpoint/directory).glob('*'):
   if path.is_file() and not path.is_symlink():files['runs/day9/formal/'+directory+'/'+path.name]=path
buffer=io.BytesIO()
with tarfile.open(fileobj=buffer,mode='w:gz') as tar:
 for name,path in sorted(files.items()):
  data=path.read_bytes();member=tarfile.TarInfo(name);member.size=len(data);member.mode=0o644
  tar.addfile(member,io.BytesIO(data))
sys.stdout.buffer.write(buffer.getvalue())
'''.replace('REMOTE',repr(REMOTE))
    payload=ssh(script,timeout=120)
    with tarfile.open(fileobj=io.BytesIO(payload)) as tar:
        members=tar.getmembers()
        for member in members:
            name=member.name
            if (not member.isfile() or not (ROOT/name).resolve().is_relative_to(ROOT)
                    or not name.startswith(('reports/day9','runs/day9/launch/','runs/day9/formal/'))):
                raise ValueError('Unexpected synchronization path')
        for member in members:
            target=ROOT/member.name;target.parent.mkdir(parents=True,exist_ok=True)
            temporary=target.with_name(target.name+'.sync-tmp');temporary.write_bytes(tar.extractfile(member).read());temporary.replace(target)
    return json.loads((ROOT/'reports/day9_pipeline_status.json').read_text())


def backup_weights():
    script='''import hashlib,json,sys
from pathlib import Path
root=Path(REMOTE);sys.path.insert(0,str(root));sys.path.insert(0,str(root/'scripts'))
from day9_train import fingerprint
from code_repair.checkpoint_retention import completed_checkpoints
files={};steps=[]
for step,directory,info in completed_checkpoints(Path('/root/zzh-day9-checkpoints'),fingerprint(root)):
 steps.append(step)
 for name in list(info['files'])+['zzh_completed_checkpoint.json']:
  path=directory/name;digest=hashlib.sha256()
  with path.open('rb') as stream:
   for chunk in iter(lambda:stream.read(1024*1024),b''):digest.update(chunk)
  files['global_step_'+str(step)+'/'+name]={'sha256':digest.hexdigest(),'bytes':path.stat().st_size}
print(json.dumps({'steps':steps,'files':files}))
'''.replace('REMOTE',repr(REMOTE))
    manifest=json.loads(ssh(script,timeout=600))
    destination=ROOT/'runs/day9/checkpoints';destination.mkdir(exist_ok=True)
    for step in manifest['steps']:
        if not isinstance(step,int):raise ValueError('Invalid checkpoint step')
        subprocess.run(['scp',*OPTIONS,'-P','37105','-r',HOST+':/root/zzh-day9-checkpoints/global_step_'+str(step),
            str(destination)],timeout=3600,check=True,stdout=subprocess.DEVNULL)
    for name,expected in manifest['files'].items():
        path=destination/name
        if not path.resolve().is_relative_to(destination.resolve()):raise ValueError('Invalid backup path')
        digest=hashlib.sha256()
        with path.open('rb') as stream:
            for chunk in iter(lambda:stream.read(1024*1024),b''):digest.update(chunk)
        if digest.hexdigest()!=expected['sha256'] or path.stat().st_size!=expected['bytes']:
            raise ValueError('Checkpoint backup bytes differ')
    report={'complete':True,'steps':manifest['steps'],'files':manifest['files'],
        'bytes':sum(v['bytes'] for v in manifest['files'].values()),'optimizer_state_saved':False}
    (ROOT/'reports/day9_weight_backup.json').write_text(json.dumps(report,indent=2)+'\n')
    return report


def cleanup_local():
    for script,action in [('day6_tunnel.py','stop'),('day6_local_service.py','stop')]:
        result=subprocess.run([sys.executable,str(ROOT/'scripts'/script),action],capture_output=True,text=True,timeout=30)
        print(result.stdout.strip(),result.stderr.strip(),flush=True)
    keep=ROOT/'runs/day9/keep_awake.json'
    if keep.exists():
        pid=json.loads(keep.read_text())['pid']
        command=subprocess.run(['ps','-p',str(pid),'-o','command='],capture_output=True,text=True)
        if command.returncode==0 and 'caffeinate -i -s -t 36000' in command.stdout:os.kill(pid,signal.SIGTERM)


def main():
    start=time.monotonic();last_status=None
    while time.monotonic()-start<36000:
        try:
            status=synchronize()
            if status['status']!=last_status:
                print(datetime.now(timezone.utc).isoformat(),status['status'],flush=True);last_status=status['status']
            if status['status'] in ('formal_updates_completed','stopped_for_inspection'):
                try:backup=backup_weights();print('Weight backup verified:',backup['steps'],flush=True)
                finally:cleanup_local()
                (ROOT/'reports/day9_monitor_status.json').write_text(json.dumps({'complete':True,
                    'pipeline_status':status['status'],'local_services_stopped':True,'instance_shutdown_or_released':False},indent=2)+'\n')
                return
        except Exception as error:
            print(datetime.now(timezone.utc).isoformat(),type(error).__name__,str(error)[:300],flush=True)
        time.sleep(45)
    (ROOT/'reports/day9_monitor_status.json').write_text(json.dumps({'complete':False,'reason':'10-hour monitor limit reached',
        'instance_shutdown_or_released':False},indent=2)+'\n')


if __name__=='__main__':main()
