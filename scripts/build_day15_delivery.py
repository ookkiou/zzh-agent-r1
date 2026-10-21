"""Build figures, factual summaries and recorded dev cases. No inference or training."""
import argparse
import csv
import difflib
import hashlib
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT/'artifacts/day15'
SOURCES = [
    'reports/day9_eval_step70_comparison.json', 'reports/day9_eval_step70_sft.json',
    'reports/day9_eval_step70_step70.json', 'reports/final_test_eval_comparison.json',
    'reports/final_test_eval_sft.json', 'reports/final_test_eval_step70.json',
    'reports/day14_application_comparison.json', 'reports/day13_sft_dev.json',
    'reports/day13_step70_dev.json', 'reports/day14_acceptance.json',
    'reports/day9_training_snapshot.json', 'reports/day9_zero_signal_diagnosis.json',
    'reports/day9_live_progress.json', 'reports/day9_training_batch_audit_1_11.jsonl',
    'training/integration/evaluation_protocol.json', 'training/day7/sft_warmup.json',
    'reports/day7_sft_warmup.json']
CASES = [
    ('improvement','mbpp-548-m01',29,'LIS boundary repaired',0,1),
    ('regression','mbpp-577-m02',43,'Factorial last digit regression',1,0),
    ('shared-failure','mbpp-526-m01',17,'Both miss the last-letter requirement',0,0)]


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read(relative):
    return json.loads((ROOT/relative).read_text())


def write_json(path, value):
    path.parent.mkdir(parents=True,exist_ok=True)
    path.write_text(json.dumps(value,ensure_ascii=False,indent=2)+'\n')


def paired_summary(comparison, sft, step70):
    tables = []
    for report in (sft,step70):
        es = report['episodes']
        table = {(e['task_id'],e['seed']):e for e in es}
        if not report['complete'] or len(table)!=len(es) or not all(
                e.get('valid_episode',e.get('terminal',{}).get('valid_episode',False)) for e in es):
            raise ValueError('Incomplete, duplicate or invalid source episodes')
        tables.append(table)
    left,right = tables
    if set(left)!=set(right):
        raise ValueError('Unpaired evaluation')
    counts = [sum(e['reward']==1 for e in table.values()) for table in tables]
    gains = sum(left[k]['reward']==0 and right[k]['reward']==1 for k in left)
    losses = sum(left[k]['reward']==1 and right[k]['reward']==0 for k in left)
    improved = comparison.get('paired_improved',comparison.get('paired_improved_episodes'))
    regressed = comparison.get('paired_regressed',comparison.get('paired_regressed_episodes'))
    if not comparison['complete'] or counts!=[comparison['sft_successes'],comparison['step70_successes']] or (gains,losses)!=(improved,regressed):
        raise ValueError('Comparison does not match source episodes')
    return {'episodes_per_model':len(left),'sft_successes':counts[0],'step70_successes':counts[1],
        'sft_rate':counts[0]/len(left),'step70_rate':counts[1]/len(left),
        'delta_pp':100*(counts[1]-counts[0])/len(left),'paired_improved':gains,'paired_regressed':losses,
        'by_seed':{str(seed):{'sft':sum(e['reward']==1 for (task,s),e in left.items() if s==seed),
            'step70':sum(e['reward']==1 for (task,s),e in right.items() if s==seed)} for seed in (17,29,43)}}


def collect():
    specs = [
        ('frozen_dev','Transformers SDPA BF16','day9_eval_step70','step70',32,14),
        ('independent_test','Transformers SDPA BF16','final_test_eval','step70',42,42),
        ('application_dev','ZzhClaw + vLLM 0.11 BF16','day13','step70',32,14)]
    evaluations = {}
    for name,backend,prefix,candidate,tasks,sources in specs:
        comp = 'day14_application_comparison' if name=='application_dev' else prefix+'_comparison'
        suffix = '_dev' if name=='application_dev' else ''
        r = paired_summary(read('reports/'+comp+'.json'),read('reports/'+prefix+'_sft'+suffix+'.json'),
                           read('reports/'+prefix+'_'+candidate+suffix+'.json'))
        r.update(backend=backend,task_count=tasks,source_count=sources)
        evaluations[name] = r
    audit = [json.loads(line) for line in (ROOT/SOURCES[13]).read_text().splitlines() if line.strip()]
    if [r['global_step'] for r in audit]!=list(range(1,12)):
        raise ValueError('Expected the preserved pilot/reload audit 1-11; review new provenance before adding it')
    diagnosis = read('reports/day9_zero_signal_diagnosis.json')
    if diagnosis['audit_steps']!=list(range(1,75)):
        raise ValueError('Unexpected completed update index')
    early = {r['global_step']:r for r in audit}
    tail = {r['step']:r for r in diagnosis['last_batches']}
    snapshot = read('reports/day9_training_snapshot.json')
    observations = []
    for step in range(1,75):
        row = {'step':step,'checkpoint_includes_update':step<=70,'batch_success_rate':'',
            'mixed_groups':'','group_count':'','pg_loss':'','kl_loss':'','grad_norm':'',
            'evidence':'diagnosis_completed_update_index_only'}
        if step in early:
            r = early[step]
            row.update(batch_success_rate=sum(t['reward'] for t in r['trajectories'])/r['trajectory_count'],
                mixed_groups=r['mixed_reward_groups'],group_count=r['group_count'],evidence='pilot_reload_raw_audit')
            metrics = snapshot['updates'][str(step)]
            row.update(pg_loss=metrics['actor/pg_loss'],kl_loss=metrics['actor/kl_loss'],grad_norm=metrics['actor/grad_norm'])
        if step in tail:
            r = tail[step]
            row.update(batch_success_rate=r['successes']/r['episodes'],mixed_groups=r['mixed_groups'],
                group_count=4,evidence='persisted_read_only_diagnosis_tail')
        observations.append(row)
    missing = [r['step'] for r in observations if r['batch_success_rate']=='']
    metrics = {'candidate_step':70,'completed_optimizer_updates':74,'original_target_updates':225,
        'optimizer_moments_saved':False,'training_was_uninterrupted':False,
        'training_observation_steps':[r['step'] for r in observations if r['batch_success_rate']!=''],
        'missing_batch_metric_steps':missing,'full_training_curve_available':not missing,
        'early_loss_gradient_steps':list(range(1,12)),
        'stop_reason':'fifth consecutive zero-relative-reward batch aborted before update75/audit writing',
        'training_curve_caveat':'Different train batches; not held-out evaluation or evidence of convergence',
        'evaluations':evaluations,'independent_test_excluded_sources':8,
        'statistical_significance_evaluated':False,'weight_backup_verified':False,
        'fresh_gpu_reproduction_performed':False,'recorded_demo_only':True,
        'source_sha256':{name:digest(ROOT/name) for name in SOURCES}}
    sft = read('reports/day7_sft_warmup.json')
    if not sft['complete'] or [r['update'] for r in sft['updates']]!=list(range(1,81)):
        raise ValueError('Expected 80 actual SFT update records')
    metrics['sft_updates'] = sft['updates']
    metrics['sft_examples'] = sft['eligible_examples']
    if not read('reports/day14_acceptance.json')['complete']:
        raise ValueError('Application migration acceptance not complete')
    return metrics,observations


def build_cases():
    tables = {stage:{(e['task_id'],e['seed']):e for e in read(f'reports/day13_{stage}_dev.json')['episodes']}
        for stage in ('sft','step70')}
    index = []
    for slug,task_id,seed,title,old,new in CASES:
        public = ROOT/'runs/day9/public_data/dev'/task_id
        portable = OUT/'source_public'/task_id
        portable.mkdir(parents=True,exist_ok=True)
        # Export public metadata/starter only; never copy private cases or reference patches.
        for filename,source in [('task.json',public/'task.json'),('solution.py',public/'starter/solution.py')]:
            if source.exists():
                (portable/filename).write_bytes(source.read_bytes())
            elif not (portable/filename).exists():
                raise FileNotFoundError(source)
        starter = (portable/'solution.py').read_text()
        metadata = json.loads((portable/'task.json').read_text())
        episodes = {stage:table[(task_id,seed)] for stage,table in tables.items()}
        if [episodes[s]['reward'] for s in ('sft','step70')]!=[old,new]:
            raise ValueError('Case classification changed')
        case = {'case_id':slug,'title':title,'task_id':task_id,'seed':seed,'split':'dev',
            'selected_for':'illustration of observed paired outcomes, not a random sample',
            'recorded_replay':True,'live_model_invocation':False,
            'instruction':metadata['instruction'],'starter_source':starter,
            'episodes':episodes,'source_reports':{s:f'reports/day13_{s}_dev.json' for s in episodes}}
        write_json(OUT/'cases'/f'{slug}.json',case)
        lines = [f'# {title}', '',f'任务 `{task_id}`，seed {seed}。已记录 dev 轨迹回放，不进行新推理。',
            '', '此案例用于解释行为，不能代替全量配对统计。', '', '## 需求', '',metadata['instruction']]
        for stage in ('sft','step70'):
            e = episodes[stage]
            lines += ['',f'## {stage}: reward={e["reward"]}', '', '```diff',
                *difflib.unified_diff(starter.splitlines(),e['patch'].splitlines(),fromfile='starter/solution.py',tofile=stage+'/solution.py',lineterm=''),
                '```', '', '| 决策 | 动作 | 结果 |', '| --- | --- | --- |']
            for i,t in enumerate(e['trace'],1):
                a = t['action'] or {}
                name = a.get('name','final' if 'final' in a else 'invalid_action')
                response = t['tool_response']
                description = ''
                if response:
                    output = response.get('output')
                    if name=='run_tests' and isinstance(output,dict):
                        description = f"public {output['passed']}/{output['tests']}"
                    elif not response['ok']:
                        description = str(response.get('error'))
                    else:
                        description = 'ok'
                lines.append(f'| {i} | {name} | {description} |')
            acc = e['terminal']['acceptance']
            lines += ['',f'终局私有验收：{acc["passed"]}/{acc["tests"]}；仅展示汇总，不展示私有输入。']
        (OUT/'cases'/f'{slug}.md').write_text('\n'.join(lines)+'\n')
        index.append({'case_id':slug,'task_id':task_id,'seed':seed,'sft_reward':old,'step70_reward':new})
    write_json(OUT/'case_index.json',index)


def plots(metrics, rows):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    import numpy as np
    plt.rcParams.update({'font.family':'DejaVu Sans','axes.spines.top':False,'axes.spines.right':False,
        'figure.facecolor':'white','axes.titleweight':'bold','font.size':10,'savefig.dpi':170})
    figure = OUT/'figures'
    figure.mkdir(exist_ok=True)
    sft = metrics['sft_updates']
    fig,sftaxes = plt.subplots(1,2,figsize=(11,4.5),layout='constrained')
    for ax,key,label in [(sftaxes[0],'loss','Supervised loss'),(sftaxes[1],'grad_norm','Gradient norm')]:
        ax.plot([r['update'] for r in sft],[r[key] for r in sft],color='#247789',lw=1.5)
        ax.set(title=label,xlabel='SFT optimizer update',ylabel=label)
        ax.grid(alpha=.18)
    fig.suptitle('LoRA SFT warmup: 80 recorded updates',fontsize=14)
    fig.supxlabel('315 train-only examples; assistant-response labels. Training loss is not a held-out capability score.',fontsize=9)
    fig.savefig(figure/'sft_training.png')
    fig.savefig(figure/'sft_training.pdf',metadata={'CreationDate':None,'ModDate':None})
    plt.close(fig)
    fig,axes = plt.subplots(2,2,figsize=(12,7.8),layout='constrained')
    x = [r['step'] for r in rows]
    for ax,key,title,ylabel in [
        (axes[0,0],'batch_success_rate','Observed train-batch reward','Successful episodes / batch'),
        (axes[0,1],'mixed_groups','Groups with relative reward signal','Mixed-reward groups / 4'),
        (axes[1,0],'pg_loss','Policy loss: pilot + reload only','actor/pg_loss'),
        (axes[1,1],'grad_norm','Gradient norm: pilot + reload only','actor/grad_norm')]:
        y = [np.nan if r[key]=='' else r[key] for r in rows]
        ax.plot(x,y,color='#247789',marker='o',markersize=3,lw=1.4)
        ax.set(title=title,xlabel='Completed optimizer update',ylabel=ylabel,xlim=(0,76))
        ax.axvline(70,color='#bd6127',ls='--',lw=1.2,label='Retained checkpoint 70')
        ax.axvspan(70.5,74.5,color='#bd6127',alpha=.12)
        ax.grid(alpha=.18)
        if key in ('batch_success_rate','mixed_groups'):
            ax.axvspan(11.5,62.5,color='gray',alpha=.08)
            ax.text(.42,.25,'Missing local per-step data\n(no interpolation)',transform=ax.transAxes,
                ha='center',color='#59636e',fontsize=9)
        else:
            ax.text(.6,.65,'Later loss/gradient points\nnot captured locally',transform=ax.transAxes,
                ha='center',color='#59636e',fontsize=9)
    axes[0,0].set_ylim(-.05,1.08)
    axes[0,1].set_ylim(-.2,4.6)
    axes[0,0].legend(loc='lower right',fontsize=8)
    fig.suptitle('GRPO diagnostics: observed slices, not a held-out learning curve',fontsize=14)
    fig.supxlabel('Completed through 74; update 75 blocked by signal guard. Restarts reset Adam moments.\n'
        'Shading after 70 = unsaved updates. Batch tasks vary; reward is not a generalization metric.',fontsize=9)
    fig.savefig(figure/'training_diagnostics.png')
    fig.savefig(figure/'training_diagnostics.pdf',metadata={'CreationDate':None,'ModDate':None})
    plt.close(fig)
    fig,ax = plt.subplots(figsize=(11,5.3),layout='constrained')
    rows_eval = list(metrics['evaluations'].values())
    positions = np.arange(3)
    width = .32
    for offset,key,label,color in [(-.5,'sft','SFT-only','#8a99ab'),(.5,'step70','GRPO step70','#247789')]:
        bars = ax.bar(positions+offset*width,[100*r[key+'_rate'] for r in rows_eval],width,label=label,color=color)
        for b,r in zip(bars,rows_eval):
            ax.text(b.get_x()+b.get_width()/2,b.get_height()+1.2,
                f"{r[key+'_successes']}/{r['episodes_per_model']}\n{100*r[key+'_rate']:.3f}%",ha='center',fontsize=9)
    for i,r in enumerate(rows_eval):
        ax.text(i,94,f"Delta {r['delta_pp']:+.3f} pp",ha='center',weight='bold',color='#245968')
    ax.set_xticks(positions,['Frozen dev\nTransformers','Independent test\nTransformers','Application dev\nZzhClaw + vLLM'])
    ax.set(ylabel='Valid single-episode success (%)',ylim=(0,102),title='Compare models within each evaluation protocol')
    ax.legend(loc='upper left',ncol=2,frameon=False)
    ax.grid(axis='y',alpha=.15)
    ax.set_axisbelow(True)
    fig.supxlabel('3 repeated seeds per task; correlated observations. No significance test or confidence intervals.\n'
        'Each pair shares its backend; scores across backends are separate experiments.',fontsize=9)
    fig.savefig(figure/'evaluation_comparison.png')
    fig.savefig(figure/'evaluation_comparison.pdf',metadata={'CreationDate':None,'ModDate':None})
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--skip-plots',action='store_true',help='Recompute numeric evidence with Python standard library only')
    args = parser.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    metrics,observations = collect()
    write_json(OUT/'metrics.json',metrics)
    with (OUT/'sft_updates.csv').open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=['update','loss','grad_norm']);writer.writeheader();writer.writerows(metrics['sft_updates'])
    with (OUT/'training_observations.csv').open('w',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=list(observations[0])); writer.writeheader(); writer.writerows(observations)
    with (OUT/'evaluation_summary.csv').open('w',newline='') as stream:
        fields=['evaluation','backend','episodes_per_model','sft_successes','step70_successes','sft_rate','step70_rate','delta_pp','paired_improved','paired_regressed']
        writer=csv.DictWriter(stream,fieldnames=fields,extrasaction='ignore');writer.writeheader()
        for name,row in metrics['evaluations'].items():
            writer.writerow({'evaluation':name,**row})
    build_cases()
    if not args.skip_plots:
        plots(metrics,observations)
    print(json.dumps({'output':str(OUT),'numeric_evaluations_recomputed':3,'recorded_cases':3,
        'training_observed_batch_steps':len(metrics['training_observation_steps']),
        'missing_batch_steps':len(metrics['missing_batch_metric_steps']),
        'model_invoked':False,'training_performed':False},ensure_ascii=False,indent=2))


if __name__=='__main__':
    main()
