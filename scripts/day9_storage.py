"""Inventory storage and optionally remove only identified wheel/download caches.

Inventory and dry run are read-only. --clean-cache never removes models,
checkpoints, source data, credentials or arbitrary directory trees.
"""
import argparse
import json
import os
from pathlib import Path
import shutil

ROOT=Path(__file__).resolve().parents[1]


def cache_candidates(root):
    root=Path(root).resolve()
    candidates=[]
    for directory in (root/'.tmp',root/'wheels'):
        if not directory.exists():continue
        if directory.is_symlink():raise ValueError('Cache root is a symlink')
        for path in directory.rglob('*'):
            if (not path.is_symlink() and path.is_file() and path.resolve().is_relative_to(directory)
                    and (path.name.endswith('.whl') or path.name.endswith('.whl.part'))):
                candidates.append(path)
    return sorted(candidates)


def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--clean-cache',action='store_true');args=p.parse_args()
    cache=cache_candidates(ROOT)
    before={str(path):shutil.disk_usage(path)._asdict() for path in (ROOT,Path('/root')) if path.exists()}
    removed=[]
    if args.clean_cache:
        for path in cache:
            size=path.stat().st_size;path.unlink();removed.append({'path':str(path),'bytes':size})
    report={'read_only':not args.clean_cache,'before':before,
        'cache_candidates':[{'path':str(p),'bytes':p.stat().st_size} for p in cache if p.exists()],
        'removed_download_cache_files':removed,'removed_models_or_checkpoints':False,
        'after':{str(path):shutil.disk_usage(path)._asdict() for path in (ROOT,Path('/root')) if path.exists()}}
    (ROOT/'reports/day9_storage.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))


if __name__=='__main__':main()
