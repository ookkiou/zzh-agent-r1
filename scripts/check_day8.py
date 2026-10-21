"""Final Day8 acceptance: complete dev baselines plus real bounded repair GRPO training."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def main():
    def read(name):
        return json.loads((ROOT/'reports'/name).read_text())
    baseline=read('day8_baseline_comparison.json')
    checkpoint=read('day8_checkpoint_verification.json')
    config=read('day8_config_status.json')
    probe=read('day8_credit_probe.json')
    preflight=read('day8_preflight.json')
    smoke=read('day8_smoke_status.json')
    evaluator=read('day8_evaluator_health.json')
    precision=read('day8_export_precision.json')
    source=read('day8_source_lock.json')
    frozen=json.loads((ROOT/'data/mbpp_repair/v0.1/manifest.json').read_text())
    source_checks={f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest()==d for f,d in source['files'].items()}
    pipeline_checks={f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest()==d for f,d in frozen['pipeline_files'].items()}
    train=[json.loads(line) for line in (ROOT/'runs/day8/train_smoke.jsonl').read_text().splitlines()]
    protocol=json.loads((ROOT/'runs/day8/evaluation_protocol.json').read_text())
    train_sources={r['extra_info']['source_id'] for r in train}
    dev_sources={r['source_id'] for r in protocol['tasks']}
    audits=[json.loads(line) for line in (ROOT/'runs/day8/smoke/training_batch_audit.jsonl').read_text().splitlines()]
    trace_checks=[]
    hashes={}
    for audit in audits:
        for item in audit['trajectories']:
            path=ROOT/'runs/day8/smoke_traces'/(item['trace_id']+'.json')
            trace=json.loads(path.read_text())
            hashes[str(path.relative_to(ROOT))]=hashlib.sha256(path.read_bytes()).hexdigest()
            trace_checks.append(trace['reward']==item['reward'] and len(trace['token_steps'])==item['steps']
                and not trace['guided'] and trace['model_generation']=='real vLLM, not scripted')
    checks={
        'unchanged_frozen_data_pipeline':all(pipeline_checks.values()),
        'actual_training_sources_match_lock':all(source_checks.values()),
        'preflight_sft_checkpoint_and_protocol':preflight['complete'],
        'isolated_formal_evaluator':evaluator['backend']=='docker' and evaluator['container_isolation_configured']
            and protocol['source_manifest_sha256'] in evaluator['dataset_manifest_sha256'],
        'full_paired_dev_baseline':baseline['complete'],
        'train_only_source_disjoint_smoke':all(r['extra_info']['split']=='train' for r in train) and not (train_sources & dev_sources),
        'resolved_real_recipe_configuration':config['returncode']==0,
        'actual_upstream_grpo_credit_probe':probe['complete'] and probe['actual_pinned_upstream_grpo'],
        'five_real_grpo_updates_completed':smoke['returncode']==0 and checkpoint['complete'] and len(checkpoint['updates'])==5,
        'five_actual_optimizer_batches_audited':[r['global_step'] for r in audits]==[1,2,3,4,5]
            and all(r['trajectory_count']==16 and r['group_count']==4 and r['actual_trajectory_grpo_advantages_verified'] for r in audits),
        'real_multi_step_vllm_and_relative_rewards':checkpoint['training_audit']['real_multi_step_episodes']>0
            and checkpoint['training_audit']['mixed_reward_groups']>0,
        'all_80_real_training_traces_match':len(trace_checks)==len(hashes)==80 and all(trace_checks),
        'weights_changed_from_sft_start':checkpoint['weight_comparison']['changed_elements']>0
            and checkpoint['weight_comparison']['compared_to']=='SFT-only merged checkpoint',
        'checkpoint_gpu_reload':checkpoint['checkpoint_reload']['nonempty'],
    }
    report={'recorded_at':datetime.now(timezone.utc).isoformat(),'complete':all(checks.values()),
        'checks':checks,'baseline':{k:baseline['metrics'][k]['success_rate'] for k in ('base','sft')},
        'baseline_paired_outcomes':baseline['paired_outcomes'],'training_audit':checkpoint['training_audit'],
        'weight_comparison':checkpoint['weight_comparison'],'real_training_trace_sha256':hashes,
        'export_precision_verification':precision,
        'optimizer_state_saved':False,
        'code_repair_grpo_smoke_performed':True,'formal_grpo_performed':False,
        'grpo_ability_improvement_proven':False,'repair_test_executed':False,
        'next_stage':'Day9-10: extend validated train data and plan bounded formal GRPO from measured throughput.',
        'limitations':['Dev contains 32 variants from 14 sources; repeated seeds are correlated.',
            'Five-update smoke repeatedly uses only four train tasks; it does not prove GRPO generalization gains.',
            'Full training checkpoints and merged weights remain on remote data disk; small experiment artifacts are backed up locally.',
            'Smoke checkpoints save model and extra state, without optimizer state; they support model reload, not exact optimizer resume.']}
    (ROOT/'reports/day8_acceptance.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:report[k] for k in ('complete','checks','baseline','training_audit','weight_comparison')},indent=2))
    if not report['complete']:
        raise SystemExit(1)


if __name__=='__main__':
    main()
