"""Verify completed Day9 preparation; deliberately do not claim the GPU run is complete."""
from datetime import datetime,timezone
import hashlib
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]


def main():
    def read(name):return json.loads((ROOT/'reports'/name).read_text())
    def digest(path):return hashlib.sha256(path.read_bytes()).hexdigest()
    data=read('day9_data_validation.json');docker=read('day9_docker_data_validation.json')
    prepared=read('day9_preparation.json');tests=read('day9_unit_tests.json')
    rebuilt=read('day9_reproducibility.json');uploaded=read('day9_upload_verification.json')
    preflight=read('day9_remote_preflight.json');resolved=read('day9_pilot_resolve_status.json')
    bundle=read('day9_bundle.json');identity=json.loads((ROOT/'runs/day9/input_identity.json').read_text())
    manifest=json.loads((ROOT/'data/mbpp_repair/v0.2/manifest.json').read_text())
    parent=json.loads((ROOT/'data/mbpp_repair/v0.1/manifest.json').read_text())
    public=ROOT/'runs/day9/public_data';export=json.loads((public/'manifest.json').read_text())
    day8=read('day8_source_lock.json');plan=json.loads((ROOT/'training/day9/run_plan.json').read_text())
    fingerprint=hashlib.sha256(b'\n'.join([(ROOT/'runs/day9/input_identity.json').read_bytes(),
        (ROOT/'reports/day7_sft_checkpoint_manifest.json').read_bytes()])).hexdigest()
    overrides=resolved['overrides']
    checks={
        'expanded_300_train_32_dev_74_14_sources':manifest['task_counts']=={'train':300,'dev':32}
            and manifest['source_counts']=={'train':74,'dev':14},
        'all_104_parent_tasks_and_frozen_test_unchanged':data['all_104_parent_tasks_unchanged']
            and (ROOT/'data/mbpp_repair/v0.2/test_sources.lock.json').read_bytes()==(ROOT/'data/mbpp_repair/v0.1/test_sources.lock.json').read_bytes()
            and all(digest(ROOT/'data/mbpp_repair/v0.1'/name)==value for name,value in parent['files'].items()),
        'current_v02_assets_and_pipeline_match_frozen_manifest':all(digest(ROOT/'data/mbpp_repair/v0.2'/name)==value for name,value in manifest['files'].items())
            and all(digest(ROOT/name)==value for name,value in manifest['pipeline_files'].items()),
        'all_332_independent_reference_and_starter_checks_passed':data['complete'] and len(data['tasks'])==332
            and all(row['valid'] for row in data['tasks']) and data['manifest_sha256']==digest(ROOT/'data/mbpp_repair/v0.2/manifest.json'),
        'all_332_real_docker_fixture_checks_passed':docker['complete'] and len(docker['tasks'])==332
            and all(row['valid'] for row in docker['tasks']) and docker['manifest_sha256']==data['manifest_sha256'],
        'deterministic_offline_rebuild_passed':rebuilt['complete'] and rebuilt['manifest_sha256']==data['manifest_sha256'],
        'public_export_exactly_997_allowed_files':len(export['files'])+1==997
            and {str(p.relative_to(public)) for p in public.rglob('*') if p.is_file()}==set(export['files'])|{'manifest.json'}
            and all(digest(public/name)==value for name,value in export['files'].items())
            and not any('private' in name or 'reference' in name for name in export['files']),
        'all_dev_model_inputs_preserved':prepared['dev_model_inputs_unchanged'] and identity['dev_model_inputs_unchanged'] and len(identity['dev_identity'])==32,
        'fourteen_targeted_tests_passed':tests['complete'] and tests['tests']==14 and tests['skipped']==0,
        'public_overlay_verified_on_server':uploaded['complete'] and uploaded['overlay_sha256']==bundle['sha256']
            and digest(ROOT/bundle['archive'])==bundle['sha256'] and not uploaded['private_resources_uploaded'],
        'actual_pinned_hydra_lightweight_config_resolved':resolved['returncode']==0 and resolved['run_fingerprint']==fingerprint
            and overrides['actor_rollout_ref.actor.checkpoint.save_contents']==['model','extra']
            and overrides['actor_rollout_ref.actor.checkpoint.load_contents']==['model','extra']
            and 'runs/day7/sft_warmup/merged' in overrides['actor_rollout_ref.model.path']
            and plan['total_updates']==225 and plan['phases']['formal']['max_wall_seconds']==28800,
        'all_39_server_cpu_checks_passed':preflight['cpu_preparation_complete'] and all(preflight['checks'].values())
            and len(preflight['checks'])==39 and preflight['run_fingerprint']==fingerprint,
        'lightweight_checkpoint_storage_budget_passed':preflight['storage_ready'] and preflight['required_budget_gib']==22
            and preflight['checkpoint_root']==plan['checkpoint_root'],
        'day8_runtime_and_protocol_remain_frozen':all(digest(ROOT/name)==value for name,value in day8['files'].items()),
    }
    report={'recorded_at':datetime.now(timezone.utc).isoformat(),'local_preparation_complete':all(checks.values()),
        'checks':checks,'day9_complete':False,'formal_225_updates_complete':False,
        'optimizer_state_saved':False,'optimizer_continuation_verified':False,
        'test_executed':False,'grpo_ability_improvement_proven':False,
        'run_fingerprint':fingerprint,'cpu_checks':len(preflight['checks']),
        'gpu_phase_status':'See day9_training_snapshot.json and individual phase status reports; this file verifies preparation only.'}
    (ROOT/'reports/day9_local_acceptance.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))
    if not report['local_preparation_complete']:raise SystemExit(1)


if __name__=='__main__':main()
