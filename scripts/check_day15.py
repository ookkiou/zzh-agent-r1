"""Offline acceptance: recompute factual summaries, replay cases and validate the evidence bundle."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import tarfile

from build_day15_delivery import ROOT, OUT, CASES, collect, digest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--archive',type=Path,default=OUT/'zzh-repair-evidence.tar.gz',
        help='Original bundle path, useful when checking an extracted copy')
    args=parser.parse_args()
    checks=[]
    def check(name, condition):
        checks.append({'name':name,'passed':bool(condition)})
        if not condition:
            raise ValueError(name)
    report={'complete':False,'scope':'local evidence, documentation and recorded replay delivery',
        'checks':checks,'training_performed':False,'live_model_invoked':False,
        'fresh_gpu_reproduction_performed':False,'video_recorded':False,
        'model_weight_backup_verified':False,'full_grpo_training_curve_available':False,
        'formal_225_updates_complete':False,'published':False}
    try:
        metrics,observations=collect()
        saved=json.loads((OUT/'metrics.json').read_text())
        check('three_evaluations_recomputed_from_paired_source_episodes',saved==metrics)
        check('frozen_final_test_and_application_results_remain_separate',
            set(metrics['evaluations'])=={'frozen_dev','independent_test','application_dev'}
            and metrics['evaluations']['independent_test']['task_count']==42
            and metrics['independent_test_excluded_sources']==8)
        rows=list(csv.DictReader((OUT/'training_observations.csv').open()))
        check('missing_grpo_metrics_left_blank_not_interpolated',len(rows)==74
            and [int(r['step']) for r in rows if not r['batch_success_rate']]==metrics['missing_batch_metric_steps']
            and metrics['missing_batch_metric_steps']==list(range(12,63)))
        check('sft_has_80_actual_update_records',len(metrics['sft_updates'])==80
            and len(list(csv.DictReader((OUT/'sft_updates.csv').open())))==80)
        tables={stage:{(e['task_id'],e['seed']):e for e in json.loads((ROOT/f'reports/day13_{stage}_dev.json').read_text())['episodes']}
            for stage in ('sft','step70')}
        for slug,task,seed,title,old,new in CASES:
            case=json.loads((OUT/'cases'/f'{slug}.json').read_text())
            check('case_'+slug+'_equals_original_dev_trace',case['recorded_replay'] and not case['live_model_invocation']
                and all(case['episodes'][stage]==tables[stage][task,seed] for stage in tables)
                and [case['episodes'][s]['reward'] for s in ('sft','step70')]==[old,new])
            replay=subprocess.run([sys.executable,str(ROOT/'scripts/day15_demo.py'),'--case',slug],
                capture_output=True,text=True,timeout=10)
            check('recorded_demo_'+slug+'_runs_offline',replay.returncode==0
                and 'RECORDED DEV REPLAY' in replay.stdout and 'no model inference' in replay.stdout)
        for stem in ('sft_training','training_diagnostics','evaluation_comparison'):
            check('standalone_figure_'+stem+'_png_and_pdf',
                (OUT/'figures'/f'{stem}.png').read_bytes().startswith(b'\x89PNG\r\n\x1a\n')
                and (OUT/'figures'/f'{stem}.pdf').read_bytes().startswith(b'%PDF-'))
        check('project_reproduction_and_resume_docs_present',all((ROOT/'docs'/name).is_file()
            for name in ('PROJECT_CARD.md','DAY15_REPRODUCE.md','RESUME_AND_INTERVIEW.md','DAY15_RESULTS.md')))
        manifest=json.loads((OUT/'delivery_manifest.json').read_text())
        check('all_allowlisted_bundle_inputs_match_manifest',all(digest(ROOT/name)==sha for name,sha in manifest['files'].items())
            and not manifest['contains_model_weights'] and not manifest['contains_private_test_inputs'])
        expected={f'zzh-repair-evidence/{name}':sha for name,sha in manifest['files'].items()}
        expected['zzh-repair-evidence/artifacts/day15/delivery_manifest.json']=digest(OUT/'delivery_manifest.json')
        archive=args.archive.resolve()
        with tarfile.open(archive,'r:gz') as bundle:
            members=bundle.getmembers()
            check('bundle_contains_only_regular_allowlisted_files',len(members)==len(expected)
                and {m.name for m in members}==set(expected)
                and all(m.isfile() and '..' not in Path(m.name).parts and not m.name.startswith('/') for m in members))
            check('all_archived_file_hashes_verified',all(hashlib.sha256(bundle.extractfile(m).read()).hexdigest()==expected[m.name]
                for m in members))
        report.update(complete=True,evidence_delivery_complete=True,
            source_evidence_sha256=metrics['source_sha256'],evidence_archive_sha256=digest(archive),
            grpo_observed_batch_metric_steps=len(metrics['training_observation_steps']),
            grpo_missing_batch_metric_steps=metrics['missing_batch_metric_steps'])
    except Exception as error:
        report['error']=str(error)
    path=ROOT/'reports/day15_acceptance.json'
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='source_evidence_sha256'},ensure_ascii=False,indent=2))
    return 0 if report['complete'] else 1


if __name__=='__main__':
    raise SystemExit(main())
