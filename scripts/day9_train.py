"""Preview, CPU-resolve, or execute bounded formal GRPO phases with recovery gates."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
from uuid import uuid4

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from code_repair.checkpoint_retention import completed_checkpoints,ensure_run_root,storage_budget


def fingerprint(root):
    root=Path(root)
    parts=[(root/'runs/day9/input_identity.json').read_bytes(),
           (root/'reports/day7_sft_checkpoint_manifest.json').read_bytes()]
    return hashlib.sha256(b'\n'.join(parts)).hexdigest()


def build_overrides(root,checkpoint_root,phase):
    root=Path(root);checkpoint_root=Path(checkpoint_root)
    plan=json.loads((root/'training/day9/run_plan.json').read_text())
    values={
        'algorithm.adv_estimator':'grpo','algorithm.norm_adv_by_std_in_grpo':True,'algorithm.use_kl_in_reward':False,
        'data.train_files':str(root/'runs/day9/train.parquet'),'data.val_files':str(root/'runs/day9/dev.parquet'),
        'data.train_batch_size':4,'data.val_batch_size':32,'data.seed':42,'data.shuffle':True,
        'data.max_prompt_length':4096,'data.max_response_length':512,'data.return_raw_chat':True,
        'data.filter_overlong_prompts':True,'data.truncation':'error',
        'actor_rollout_ref.model.path':str(root/'runs/day7/sft_warmup/merged'),
        'actor_rollout_ref.model.enable_gradient_checkpointing':True,
        'actor_rollout_ref.actor.optim.lr':1e-6,'actor_rollout_ref.actor.optim.lr_scheduler_type':'constant',
        'actor_rollout_ref.actor.optim.weight_decay':0.0,
        'actor_rollout_ref.actor.checkpoint.save_contents':['model','extra'],
        'actor_rollout_ref.actor.checkpoint.load_contents':['model','extra'],
        'actor_rollout_ref.actor.ppo_mini_batch_size':4,'actor_rollout_ref.actor.ppo_micro_batch_size_per_gpu':1,
        'actor_rollout_ref.actor.ppo_epochs':1,'actor_rollout_ref.actor.data_loader_seed':42,
        'actor_rollout_ref.actor.use_kl_loss':True,'actor_rollout_ref.actor.kl_loss_coef':0.001,
        'actor_rollout_ref.actor.fsdp_config.param_offload':True,'actor_rollout_ref.actor.fsdp_config.optimizer_offload':True,
        'actor_rollout_ref.rollout.name':'vllm','actor_rollout_ref.rollout.tensor_model_parallel_size':1,
        'actor_rollout_ref.rollout.gpu_memory_utilization':0.35,'actor_rollout_ref.rollout.n':4,
        'actor_rollout_ref.rollout.temperature':0.8,'actor_rollout_ref.rollout.top_p':0.95,
        'actor_rollout_ref.rollout.enforce_eager':True,'actor_rollout_ref.rollout.prompt_length':4096,
        'actor_rollout_ref.rollout.response_length':512,'actor_rollout_ref.rollout.log_prob_micro_batch_size_per_gpu':1,
        'actor_rollout_ref.rollout.agent.num_workers':1,'actor_rollout_ref.rollout.agent.max_steps':6,
        'actor_rollout_ref.rollout.agent.agent_flow_config_path':str(root/'training/code_repair/day9.yaml'),
        'actor_rollout_ref.rollout.agent.default_agent_flow':'zzh_code_repair_day9',
        'actor_rollout_ref.ref.log_prob_micro_batch_size_per_gpu':1,'actor_rollout_ref.ref.fsdp_config.param_offload':True,
        'critic.enable':False,'reward_model.enable':False,'custom_reward_function.path':None,
        'trainer.logger':['console'],'trainer.project_name':'zzh_repair_grpo_v02','trainer.experiment_name':'sft_plus_grpo_v02',
        'trainer.n_gpus_per_node':1,'trainer.nnodes':1,'trainer.default_local_dir':str(checkpoint_root),
        'trainer.save_freq':10,'trainer.max_actor_ckpt_to_keep':None,
        'trainer.del_local_ckpt_after_load':False,
        'trainer.test_freq':-1,'trainer.val_before_train':False,
        'trainer.total_epochs':3,'trainer.total_training_steps':plan['phases'][phase]['total_updates'],
        'trainer.resume_mode':'disable' if phase=='pilot' else 'resume_path',
        'trainer.rollout_data_dir':str(checkpoint_root/'rollouts'),'ray_kwargs.ray_init.num_cpus':8,
        'hydra.run.dir':str(checkpoint_root/'hydra'/phase),
    }
    if phase!='pilot':
        complete=completed_checkpoints(checkpoint_root,fingerprint(root))
        expected=10 if phase=='reload_probe' else 11
        if not complete or complete[-1][0]<expected:raise ValueError('Required completed recovery checkpoint absent')
        values['trainer.resume_from_path']=str(complete[-1][1])
    runtime={'PYTHONPATH':str(root)+':'+str(root/'runs/day6/Agent-R1'),
        'CODE_REPAIR_PUBLIC_DATA_DIR':str(root/'runs/day9/public_data'),
        'CODE_REPAIR_TOKEN_FILE':str(root/'runs/day6/evaluator_token'),
        'CODE_REPAIR_EVALUATOR_URL':'http://127.0.0.1:18765',
        'CODE_REPAIR_TRACE_DIR':str(checkpoint_root/'traces'),
        'CODE_REPAIR_RUN_INPUTS':str(root/'runs/day9/public_data/manifest.json'),
        'CODE_REPAIR_RUN_FINGERPRINT':fingerprint(root),
        'CODE_REPAIR_ZERO_SIGNAL_LIMIT':str(plan['consecutive_zero_signal_limit'])}
    for key,value in runtime.items():values['+ray_kwargs.ray_init.runtime_env.env_vars.'+key]=value
    return values,runtime


def hydra_override(key,value):
    # Hydra infers bare numeric values; Ray requires every env value to stay str.
    encoded=json.dumps(value,separators=(',',':')) if not isinstance(value,str) or key.startswith('+ray_kwargs.ray_init.runtime_env.env_vars.') else value
    return key+'='+encoded


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('action',choices=('preview','resolve','execute'),nargs='?',default='preview')
    p.add_argument('--phase',choices=('pilot','reload_probe','formal'),default='pilot')
    p.add_argument('--checkpoint-root',type=Path,default=Path('/root/zzh-day9-checkpoints'))
    args=p.parse_args();checkpoint_root=args.checkpoint_root.resolve()
    plan=json.loads((ROOT/'training/day9/run_plan.json').read_text())
    if args.action=='execute':
        preflight=json.loads((ROOT/'reports/day9_remote_preflight.json').read_text())
        if not preflight['ready_for_gpu_pilot'] or preflight['run_fingerprint']!=fingerprint(ROOT):
            raise ValueError('Current successful remote preflight and adequate checkpoint storage required')
        if str(checkpoint_root)!=preflight['checkpoint_root']:raise ValueError('Storage root differs from preflight')
        if args.phase=='formal' and not json.loads((ROOT/'reports/day9_reload_verification.json').read_text())['complete']:
            raise ValueError('Actual weight/data reload probe required before long run')
        ensure_run_root(checkpoint_root,fingerprint(ROOT))
        if args.phase=='pilot' and ((checkpoint_root/'training_batch_audit.jsonl').exists() or list(checkpoint_root.glob('global_step_*'))):
            raise ValueError('Pilot already attempted; inspect artifacts or use a new run root')
        if not storage_budget(checkpoint_root,fingerprint(ROOT),plan['minimum_free_gib'])['storage_ready']:
            raise ValueError('Checkpoint space below conservative preflight threshold')
        if preflight.get('source_files'):
            for f,d in preflight['source_files'].items():
                if hashlib.sha256((ROOT/f).read_bytes()).hexdigest()!=d:raise ValueError('Runtime source changed after preflight')
        gpu=subprocess.run(['nvidia-smi','--query-compute-apps=pid','--format=csv,noheader'],capture_output=True,text=True)
        if gpu.returncode!=0 or gpu.stdout.strip():raise ValueError('GPU unavailable or occupied at launch')
        from code_repair.evaluation import RemoteEvaluator
        evaluator=RemoteEvaluator('http://127.0.0.1:18765',
            (ROOT/'runs/day6/evaluator_token').read_text().strip(),'mbpp-627-x01')
        health=evaluator.health()
        manifest=json.loads((ROOT/'runs/day9/input_identity.json').read_text())['dataset_manifest_sha256']
        if (health.get('backend')!='docker' or not health.get('container_isolation_configured')
                or health.get('task_count')!=332 or manifest not in health.get('dataset_manifest_sha256',[])):
            raise ValueError('Evaluator does not serve the validated v0.2 Docker dataset')
    values,runtime=build_overrides(ROOT,checkpoint_root,args.phase)
    launches=ROOT/'runs/day9/launch';launches.mkdir(parents=True,exist_ok=True)
    attempt=uuid4().hex[:8]
    record={'action':args.action,'phase':args.phase,'attempt':attempt,'overrides':values,
        'run_fingerprint':fingerprint(ROOT),'wall_time_limit_seconds':plan['phases'][args.phase]['max_wall_seconds'],
        'optimizer_recovery_verified':False,'formal_training_complete':False}
    record.update({'optimizer_state_saved':False,'restart_semantics':'restore weights/data/extra; reset Adam moments'})
    path=launches/(args.phase+'-'+args.action+'-'+attempt+'.json')
    path.write_text(json.dumps(record,indent=2)+'\n')
    if args.action=='preview':print(json.dumps(record,indent=2));return
    upstream=ROOT/'runs/day6/Agent-R1';source=upstream/'agent_r1/trainer/main_agent_ppo.py'
    lock=json.loads((ROOT/'TRAINING_SOURCE_LOCK.json').read_text())
    if hashlib.sha256(source.read_bytes()).hexdigest()!=lock['agent_r1']['reviewed_files_sha256']['agent_r1/trainer/main_agent_ppo.py']:
        raise ValueError('Pinned official entry changed')
    text=source.read_text()
    replacements={
        'from agent_r1.trainer.ppo.ray_trainer import RayAgentTrainer, need_critic_agent_ppo':
            'from agent_r1.trainer.ppo.ray_trainer import need_critic_agent_ppo\nfrom code_repair.day9_audit import FormalRepairTrainer as RayAgentTrainer',
        'config_path="../config"':'config_path='+repr(str(upstream/'agent_r1/config')),
        'if __name__ == "__main__":\n    main()':
            'if __name__ == "__main__":\n    import signal\n    def stop_owned_job(signum, frame):\n        raise SystemExit(124)\n    signal.signal(signal.SIGTERM, stop_owned_job)\n    try:\n        main()\n    finally:\n        ray.shutdown()'}
    for old,new in replacements.items():
        if text.count(old)!=1:raise ValueError('Pinned entry extension anchor mismatch')
        text=text.replace(old,new)
    entry=ROOT/'runs/day9/formal_entry.py';entry.write_text(text)
    command=[sys.executable,str(entry)]
    command.extend(hydra_override(k,v) for k,v in values.items())
    if args.action=='resolve':command+=['--cfg','job','--resolve']
    environment=os.environ.copy();environment.update(runtime)
    environment.update({'CUDA_VISIBLE_DEVICES':'0','VLLM_USE_V1':'1','CUDA_HOME':'/usr/local/cuda',
        'VLLM_ATTENTION_BACKEND':'FLASH_ATTN','HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1',
        'OMP_NUM_THREADS':'4','TOKENIZERS_PARALLELISM':'false',
        'PATH':str(Path(sys.executable).parent)+':/usr/local/cuda/bin:/root/miniconda3/bin:'+os.defpath})
    logfile=ROOT/'reports'/('day9_'+args.phase+'_'+args.action+'_'+attempt+'.log')
    start=time.monotonic();timeout=120 if args.action=='resolve' else record['wall_time_limit_seconds']
    with logfile.open('w') as stream:
        process=subprocess.Popen(command,cwd=upstream,env=environment,stdout=stream,stderr=subprocess.STDOUT,start_new_session=True)
        try:code=process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid,signal.SIGTERM)
            try:process.wait(timeout=20)
            except subprocess.TimeoutExpired:
                os.killpg(process.pid,signal.SIGKILL);process.wait(timeout=10)
            code=124
    record.update({'returncode':code,'elapsed_seconds':time.monotonic()-start,'log':str(logfile),
        'official_entry_sha256':hashlib.sha256(source.read_bytes()).hexdigest(),
        'extended_entry_sha256':hashlib.sha256(entry.read_bytes()).hexdigest()})
    path.write_text(json.dumps(record,indent=2)+'\n')
    (ROOT/'reports'/('day9_'+args.phase+'_'+args.action+'_status.json')).write_text(json.dumps(record,indent=2)+'\n')
    print('Day9',args.phase,args.action,'returncode',code,'log',logfile)
    return code


if __name__=='__main__':raise SystemExit(main())
