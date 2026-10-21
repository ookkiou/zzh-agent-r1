"""Recover exact completed-phase evidence from Ray's persisted worker stdout/stderr."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT));sys.path.insert(0,str(ROOT/'scripts'))
from day9_train import fingerprint


def collect(phase,allow_partial=False):
    status=json.loads((ROOT/'reports'/('day9_'+phase+'_execute_status.json')).read_text())
    pause_path=ROOT/'reports/day9_pause_status.json'
    pause=json.loads(pause_path.read_text()) if pause_path.exists() else {}
    paused=(allow_partial and phase=='formal' and pause.get('user_requested_pause')
        and pause.get('run_fingerprint')==fingerprint(ROOT))
    if (status['returncode']!=0 and not paused) or status['run_fingerprint']!=fingerprint(ROOT):
        raise ValueError('Successful matching phase required for worker evidence')
    forwarded=Path(status['log']).read_text(errors='replace')
    pids=set(re.findall(r'TaskRunner pid=(\d+)',forwarded))
    if len(pids)!=1:raise ValueError('Cannot identify a unique actual TaskRunner PID')
    pid=next(iter(pids))
    candidates=[]
    for path in Path('/tmp/ray').glob('session_[0-9]*/logs/*-'+pid+'.out'):
        text=path.read_text(errors='replace')
        if 'training/global_step:' in text and str(ROOT) in text:candidates.append(path)
    if len(candidates)!=1:raise ValueError('Cannot identify a unique persisted TaskRunner log')
    taskrunner=candidates[0];session=taskrunner.parent
    worker_pids=set(re.findall(r'WorkerDict pid=(\d+)',forwarded))
    paths=[taskrunner]
    for worker in sorted(worker_pids):
        paths += sorted(session.glob('*-'+worker+'.err'))
        paths += sorted(session.glob('*-'+worker+'.out'))
    provenance=[];parts=[]
    for index,path in enumerate(paths):
        raw=path.read_bytes();copy=ROOT/'reports'/('day9_'+phase+'_worker_'+str(index)+'.raw.log')
        copy.write_bytes(raw);provenance.append({'remote_source':str(path),'copy':str(copy.relative_to(ROOT)),
            'sha256':hashlib.sha256(raw).hexdigest(),'bytes':len(raw)})
        parts.append(raw.decode(errors='replace'))
    text='\n'.join(parts)
    evidence=ROOT/'reports'/('day9_'+phase+'_worker_evidence.log');evidence.write_text(text)
    actual=set(map(int,re.findall(r'training/global_step:(\d+)',text)))
    expected=set(range(1,11)) if phase=='pilot' else {11} if phase=='reload_probe' else set(range(12,226))
    if paused:
        if not actual.issubset(expected) or (actual and actual!=set(range(12,max(actual)+1))):
            raise ValueError('Partial paused phase has a noncontiguous update range')
    elif actual!=expected:raise ValueError('Persisted worker update range differs from expected phase')
    report={'complete':True,'phase':phase,'attempt':status['attempt'],'phase_completed':status['returncode']==0 and actual==expected,
        'user_requested_pause':bool(paused),'run_fingerprint':fingerprint(ROOT),'taskrunner_pid':int(pid),
        'ray_logs_directory':str(session),'sources':provenance,'evidence_log':str(evidence),
        'evidence_sha256':hashlib.sha256(evidence.read_bytes()).hexdigest(),'actual_updates':sorted(actual),
        'missing_from_forwarded_console':sorted(actual-set(map(int,re.findall(r'training/global_step:(\d+)',forwarded)))),
        'evidence_origin':'Unmodified persisted native Ray worker stdout/stderr; separate from forwarded driver console.'}
    (ROOT/'reports'/('day9_'+phase+'_worker_evidence.json')).write_text(json.dumps(report,indent=2)+'\n')
    return report


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--phase',choices=('pilot','reload_probe','formal'),required=True)
    p.add_argument('--allow-partial',action='store_true');args=p.parse_args()
    print(json.dumps(collect(args.phase,args.allow_partial),indent=2))


if __name__=='__main__':main()
