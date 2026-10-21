"""Compare complete paired application dev results, never reuse final test labels."""
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0,str(Path(__file__).resolve().parent))
from day13_prepare import PROTOCOL, digest


def main():
    protocol = json.loads(PROTOCOL.read_text())
    expected = {(row['task_id'],seed) for row in protocol['tasks'] for seed in protocol['seeds']}
    reports = {stage:json.loads((ROOT/'reports'/f'day13_{stage}_dev.json').read_text()) for stage in ('sft','step70')}
    tables = {}
    for stage,report in reports.items():
        inputs = report['inputs']
        if (not report['complete'] or inputs['protocol_sha256']!=digest(PROTOCOL)
                or inputs['stage']!=stage or inputs['scope']!='dev'
                or inputs['model_sha256']!=protocol['model_sha256'][stage]
                or len(report['episodes'])!=len(expected)):
            raise ValueError('Incomplete/changed application experiment')
        tables[stage] = {(row['task_id'],row['seed']):row['reward'] for row in report['episodes']}
        if set(tables[stage])!=expected or any(row['reward'] not in (0,1) or not row['terminal']['valid_episode']
                for row in report['episodes']):
            raise ValueError('Coverage, reward or infrastructure invalid')
    counts = {stage:sum(table.values()) for stage,table in tables.items()}
    result = {'complete':True,'split':'dev','profile':'code-repair-v1',
        'protocol_sha256':digest(PROTOCOL),'episodes_per_model':len(expected),
        'sft_successes':counts['sft'],'step70_successes':counts['step70'],
        'sft_success_rate':counts['sft']/len(expected),
        'step70_success_rate':counts['step70']/len(expected),
        'delta_percentage_points':100*(counts['step70']-counts['sft'])/len(expected),
        'paired_improved':sum(tables['sft'][key]==0 and tables['step70'][key]==1 for key in expected),
        'paired_regressed':sum(tables['sft'][key]==1 and tables['step70'][key]==0 for key in expected),
        'by_seed':{str(seed):{stage:sum(value for (task,s),value in table.items() if s==seed)
            for stage,table in tables.items()} for seed in protocol['seeds']},
        'invalid_attempts':{stage:len(report['invalid_attempts']) for stage,report in reports.items()},
        'source_reports_sha256':{stage:digest(ROOT/'reports'/f'day13_{stage}_dev.json') for stage in reports},
        'statistical_significance_evaluated':False,'final_test':False,
        'formal_225_updates_complete':False,'training_performed':False,
        'caveat':protocol['migration_caveat']}
    output = ROOT/'reports/day14_application_comparison.json'
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__ == '__main__':
    main()
