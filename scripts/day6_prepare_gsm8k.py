"""Prepare small official-recipe diagnostic subsets; never use repair test sources."""

import hashlib
import json
from pathlib import Path
import re
import runpy

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]


def main():
    upstream = ROOT / 'runs/day6/Agent-R1'
    prompts = runpy.run_path(str(upstream / 'recipes/gsm8k/prompts.py'))
    lock = json.loads((ROOT / 'reports/day6_gsm8k_source.lock.json').read_text())
    output = ROOT / 'data/day6-gsm8k'
    report = {'purpose': 'training-stack diagnostics, not benchmark scores', 'source_revision': lock['revision'],
              'repair_test_sources_used': False, 'subsets': {}}
    for split, count in (('train', 32), ('test', 8)):
        name = f'main/{split}-00000-of-00001.parquet'
        item = next(row for row in lock['files'] if row['name'] == name)
        raw = ROOT / 'data/day6-gsm8k-source' / name
        if hashlib.sha256(raw.read_bytes()).hexdigest() != item['lfs']['sha256']:
            raise ValueError('Raw GSM8K checksum mismatch')
        data = pd.read_parquet(raw)
        indices = sorted(range(len(data)), key=lambda index: (len(data.iloc[index]['question']), index))[:count]
        for mode in ('single', 'tool'):
            rows = []
            for index in indices:
                question, answer = data.iloc[index]['question'], data.iloc[index]['answer']
                match = re.search(r'#### (\-?[0-9\.\,]+)', answer)
                if not match:
                    raise ValueError('No official answer marker')
                solution = match.group(1).replace(',', '')
                row = {'data_source': 'openai/gsm8k', 'agent_name': 'gsm8k_tool' if mode == 'tool' else 'single_step_agent',
                       'prompt': prompts['build_agent_messages' if mode == 'tool' else 'build_plain_messages'](question),
                       'question': question, 'ground_truth': solution, 'ability': 'math',
                       'reward_model': {'style': 'rule', 'ground_truth': solution},
                       'extra_info': {'split': split, 'index': index, 'answer': answer, 'question': question,
                                      'ground_truth': solution}}
                if mode == 'tool':
                    row['env_kwargs'] = json.dumps({'tools_kwargs': {'ground_truth': solution}})
                rows.append(row)
            destination = output / mode / (split + '.parquet')
            destination.parent.mkdir(parents=True, exist_ok=True)
            pd.DataFrame(rows).to_parquet(destination, index=False)
            report['subsets'][mode + '/' + split] = {'rows': len(rows), 'original_indices': indices,
                                                    'selection': 'shortest questions to bound diagnostic cost',
                                                    'sha256': hashlib.sha256(destination.read_bytes()).hexdigest()}
    (ROOT / 'reports/day6_gsm8k_preparation.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
