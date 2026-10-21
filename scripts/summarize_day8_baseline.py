"""Audit complete paired dev coverage and summarize all single-episode outcomes."""
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def main():
    path=ROOT/'runs/day8/evaluation_protocol.json'
    protocol=json.loads(path.read_text())
    digest=hashlib.sha256(path.read_bytes()).hexdigest()
    expected={(r['task_id'],seed) for r in protocol['tasks'] for seed in protocol['seeds']}
    reports={stage:json.loads((ROOT/'reports'/('day8_baseline_'+stage+'.json')).read_text()) for stage in ('base','sft')}
    checks={}
    tables={}
    metrics={}
    hashes={}
    for stage,report in reports.items():
        episodes=report['episodes']
        table={(r['task_id'],r['seed']):r for r in episodes}
        checks[stage+'_complete_96']=report['complete'] and len(episodes)==len(table)==96 and set(table)==expected
        checks[stage+'_valid_all']=all(r['valid_episode'] and r['split']=='dev' and r['reward'] in (0,1) for r in episodes)
        checks[stage+'_same_protocol']=report['protocol_sha256']==digest and not report['training_performed'] and not report['guided']
        counters=Counter();terminations=Counter();tools=Counter();sources=defaultdict(lambda:[0,0])
        trace_checks=[]
        for item in episodes:
            counters.update(item['error_counts']);tools.update(item['tool_counts']);terminations[item['termination_reason']]+=1
            sources[item['source_id']][0]+=item['reward']==1;sources[item['source_id']][1]+=1
            trace_path=ROOT/'runs/day8/baseline'/stage/(item['task_id']+'-'+str(item['seed'])+'.json')
            trace=json.loads(trace_path.read_text())
            trace_checks.append(trace['summary']==item and len(trace['steps'])==item['steps'])
            hashes[str(trace_path.relative_to(ROOT))]=hashlib.sha256(trace_path.read_bytes()).hexdigest()
        checks[stage+'_all_traces_match']=len(trace_checks)==96 and all(trace_checks)
        metrics[stage]={k:report[k] for k in ('model_kind','task_count','source_count','successes','success_rate',
            'valid_coverage','parsed_action_rate','contract_valid_action_rate','generated_tokens')}
        metrics[stage].update({'invalid_attempts':len(report['invalid_attempts']),
            'elapsed_seconds_sum':sum(r['elapsed_seconds'] for r in episodes),
            'error_counts':dict(counters),'tool_counts':dict(tools),'termination_counts':dict(terminations),
            'source_successes_attempts':dict(sources)})
        tables[stage]=table
    paired=[];outcomes=Counter()
    for key in sorted(expected):
        base,sft=tables['base'][key],tables['sft'][key]
        outcome=('both_success' if base['reward']==sft['reward']==1 else 'both_fail' if base['reward']==sft['reward']==0
            else 'sft_only_success' if sft['reward']==1 else 'base_only_success')
        outcomes[outcome]+=1
        paired.append({'task_id':key[0],'source_id':base['source_id'],'seed':key[1],
            'base_reward':base['reward'],'sft_reward':sft['reward'],'outcome':outcome})
    report={'complete':all(checks.values()),'checks':checks,'evaluation_protocol_sha256':digest,
        'metrics':metrics,'paired_outcomes':dict(outcomes),'paired_episodes':paired,'trace_sha256':hashes,
        'grpo_effect_evaluated':False,'final_test':False,
        'limitations':['Development benchmark only; 32 variants from 14 sources.',
            'Three seeds per task are correlated repeats, not 96 independent problems.',
            'SFT supervision contains repair labels; this comparison does not measure GRPO benefits.']}
    (ROOT/'reports/day8_baseline_comparison.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('complete','metrics','paired_outcomes')},indent=2))


if __name__=='__main__':
    main()
