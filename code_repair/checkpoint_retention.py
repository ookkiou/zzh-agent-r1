"""Rotate only completed checkpoints created by this formal run; preserve the latest.

Pure filesystem helpers permit meaningful CPU tests. Existing Day6/7/8 artifacts
are outside this run root and are never considered for removal.
"""
import json
from pathlib import Path
import re
import shutil

MARKER='zzh_completed_checkpoint.json'
REQUIRED=('data.pt','actor/model_world_size_1_rank_0.pt',
    'actor/extra_state_world_size_1_rank_0.pt')


def ensure_run_root(root,fingerprint):
    root=Path(root)
    if root.is_symlink():raise ValueError('Checkpoint root cannot be a symlink')
    root.mkdir(parents=True,exist_ok=True)
    lock=root/'zzh_run_identity.json'
    if lock.exists():
        if lock.is_symlink() or json.loads(lock.read_text())['fingerprint']!=fingerprint:
            raise ValueError('Checkpoint root belongs to another run')
    else:
        if any(root.glob('global_step_*')):raise ValueError('Unowned checkpoints in run root')
        lock.write_text(json.dumps({'fingerprint':fingerprint})+'\n')
    return root.resolve()


def completed_checkpoints(root,fingerprint):
    root=ensure_run_root(root,fingerprint)
    found=[]
    for directory in root.glob('global_step_*'):
        match=re.fullmatch(r'global_step_(\d+)',directory.name)
        if directory.is_symlink() or not directory.is_dir() or not match:
            raise ValueError('Unexpected checkpoint path')
        marker=directory/MARKER
        if not marker.exists():
            raise ValueError('Incomplete checkpoint retained for inspection: '+str(directory))
        if marker.is_symlink():raise ValueError('Checkpoint marker cannot be a symlink')
        info=json.loads(marker.read_text())
        if info['fingerprint']!=fingerprint or info['global_step']!=int(match[1]):
            raise ValueError('Checkpoint marker identity mismatch')
        if not set(REQUIRED).issubset(info['files']) or not info.get('model_extra_and_dataloader_saved') or info.get('optimizer_state_saved'):
            raise ValueError('Incorrect lightweight checkpoint state in marker')
        for name,size in info['files'].items():
            path=directory/name
            if not path.resolve().is_relative_to(directory.resolve()) or path.is_symlink() or not path.is_file() or size<=0 or path.stat().st_size!=size:
                raise ValueError('Completed checkpoint file missing/changed')
        found.append((int(match[1]),directory,info))
    return sorted(found)


def prepare_checkpoint_save(root,fingerprint,current_step):
    completed=completed_checkpoints(root,fingerprint)
    if completed and completed[-1][0]>=current_step:
        raise ValueError('Refusing checkpoint overwrite or nonmonotonic save')
    removed=[]
    # Keep the newest complete state while the next checkpoint is being written.
    for step,directory,_ in completed[:-1]:
        shutil.rmtree(directory);removed.append(step)
    return removed


def mark_checkpoint_complete(root,fingerprint,step):
    root=ensure_run_root(root,fingerprint);directory=root/f'global_step_{step}'
    if directory.is_symlink():raise ValueError('Checkpoint directory cannot be a symlink')
    for name in REQUIRED:
        path=directory/name
        if not path.is_file() or path.is_symlink() or path.stat().st_size<=0:
            raise ValueError('Missing lightweight checkpoint state: '+name)
    if list(directory.rglob('optim_world_size_*.pt')):
        raise ValueError('Optimizer state forbidden by lightweight policy')
    files={}
    for path in directory.rglob('*'):
        if path.is_symlink():raise ValueError('Symlink in saved checkpoint')
        if path.is_file() and path.name!=MARKER:files[str(path.relative_to(directory))]=path.stat().st_size
    info={'fingerprint':fingerprint,'global_step':step,'files':files,
        'model_extra_and_dataloader_saved':True,'optimizer_state_saved':False,
        'restart_semantics':'model/data/scheduler/RNG restore; Adam moments reset',
        'bitwise_resume_guaranteed':False}
    temporary=directory/(MARKER+'.tmp')
    if temporary.is_symlink() or (directory/MARKER).is_symlink():raise ValueError('Marker cannot be a symlink')
    temporary.write_text(json.dumps(info,indent=2)+'\n')
    temporary.replace(directory/MARKER)
    return info


def storage_budget(root,fingerprint,minimum_gib):
    """Credit existing owned checkpoints toward the two-checkpoint capacity budget."""
    root=Path(root);parent=root
    while not parent.exists():parent=parent.parent
    free=shutil.disk_usage(parent).free
    existing=completed_checkpoints(root,fingerprint) if (root/'zzh_run_identity.json').exists() else []
    owned=sum(sum(info['files'].values()) for _,_,info in existing)
    return {'available_gib':round(free/1024**3,2),'owned_checkpoint_gib':round(owned/1024**3,2),
        'checkpoint_budget_gib':round((free+owned)/1024**3,2),
        'required_budget_gib':minimum_gib,'storage_ready':free+owned>=minimum_gib*1024**3}
