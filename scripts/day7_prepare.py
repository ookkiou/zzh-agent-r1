"""Export frozen train/dev public resources and a fixed small diagnostic selection."""

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from code_repair.agent_protocol import PROTOCOL_VERSION, initial_messages
from code_repair.public_data import load_public_task


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--parquet-only', action='store_true', help='On the GPU host, convert prepared public JSONL to parquet')
    args = parser.parse_args()
    output = ROOT / 'runs/day7'
    output.mkdir(parents=True, exist_ok=True)
    public = output / 'public_data'
    if not args.parquet_only:
        source = ROOT / 'data/mbpp_repair/v0.1'
        original = json.loads((source / 'manifest.json').read_text())
        for name, digest in original['pipeline_files'].items():
            if hashlib.sha256((ROOT / name).read_bytes()).hexdigest() != digest:
                raise ValueError('Frozen pipeline changed: ' + name)
        manifest = {'schema_version': 1, 'protocol_version': PROTOCOL_VERSION,
            'source_manifest_sha256': hashlib.sha256((source / 'manifest.json').read_bytes()).hexdigest(),
            'tasks': [], 'files': {}}
        for row in sorted(original['tasks'], key=lambda item: item['task_id']):
            split = row.get('split', Path(row['path']).parts[0])
            if split not in ('train', 'dev'):
                raise ValueError('Only train/dev are exportable')
            metadata = json.loads((source / row['path'] / 'task.json').read_text())
            entry = {key: metadata[key] for key in ('task_id', 'source_id', 'split')}
            entry['path'] = row['path']
            manifest['tasks'].append(entry)
            for name in ('task.json', 'starter/solution.py', 'public_tests.py'):
                relative = row['path'] + '/' + name
                path = source / relative
                if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != original['files'][relative]:
                    raise ValueError('Frozen public resource changed: ' + relative)
                destination = public / relative
                destination.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, destination)
                manifest['files'][relative] = original['files'][relative]
        (public / 'manifest.json').write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + '\n')
        selection = {'protocol_version': PROTOCOL_VERSION, 'n': 4, 'seeds': [17, 29, 43, 59],
            'temperature': 0.8, 'top_p': 0.95, 'max_steps': 6,
            'max_prompt_length': 4096, 'max_response_length': 512,
            'purpose': 'small train/dev diagnostic, not full baseline or effectiveness evaluation', 'tasks': []}
        for split in ('train', 'dev'):
            seen = set()
            rows = []
            for row in manifest['tasks']:
                if row['split'] != split or row['source_id'] in seen:
                    continue
                seen.add(row['source_id'])
                task = load_public_task(public, row['task_id'])
                rows.append({'data_source': 'zzh_code_repair/v0.1', 'agent_name': 'zzh_code_repair',
                    'prompt': initial_messages(task), 'env_kwargs': json.dumps({'task_id': task.task_id}),
                    'reward_model': {'style': 'rule', 'ground_truth': ''},
                    'extra_info': {**{key: row[key] for key in ('task_id', 'source_id', 'split')}, 'index': len(rows)}})
                selection['tasks'].append({key: row[key] for key in ('task_id', 'source_id', 'split')})
                if len(rows) == 4:
                    break
            if len(rows) != 4:
                raise ValueError('Four distinct sources required per split')
            (output / (split + '.jsonl')).write_text(''.join(json.dumps(r, ensure_ascii=False) + '\n' for r in rows))
        (output / 'selection.json').write_text(json.dumps(selection, ensure_ascii=False, indent=2) + '\n')
        expected = {'manifest.json'} | set(manifest['files'])
        actual = {str(p.relative_to(public)) for p in public.rglob('*') if p.is_file()}
        if actual != expected:
            raise ValueError('Public export contains unexpected or missing files')
        report = {'local_export_complete': True, 'day7_complete': False,
            'exported_tasks': len(manifest['tasks']), 'diagnostic_tasks': len(selection['tasks']),
            'source_manifest_sha256': manifest['source_manifest_sha256'],
            'selection_sha256': hashlib.sha256((output / 'selection.json').read_bytes()).hexdigest(),
            'private_resources_exported': False, 'repair_test_sources_executed': False,
            'gpu_diagnostics_performed': False}
        (ROOT / 'reports/day7_data_preparation.json').write_text(json.dumps(report, indent=2) + '\n')
        print(json.dumps(report, indent=2))
    else:
        import pandas as pd
        for split in ('train', 'dev'):
            rows = [json.loads(line) for line in (output / (split + '.jsonl')).read_text().splitlines()]
            for row in rows:
                load_public_task(public, json.loads(row['env_kwargs'])['task_id'])
            pd.DataFrame(rows).to_parquet(output / (split + '.parquet'), index=False)
        print('Prepared train/dev diagnostic parquet; no private resources loaded')


if __name__ == '__main__':
    main()
