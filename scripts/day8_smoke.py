"""Resolve or run exactly five custom multi-turn repair GRPO updates."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute',action='store_true')
    args=parser.parse_args()
    upstream=ROOT/'runs/day6/Agent-R1'
    source=upstream/'agent_r1/trainer/main_agent_ppo.py'
    lock=json.loads((ROOT/'TRAINING_SOURCE_LOCK.json').read_text())
    expected=lock['agent_r1']['reviewed_files_sha256']['agent_r1/trainer/main_agent_ppo.py']
    if hashlib.sha256(source.read_bytes()).hexdigest()!=expected:
        raise ValueError('Pinned official entry changed')
    if args.execute:
        for stage in ('base','sft'):
            if not json.loads((ROOT/'reports'/('day8_baseline_'+stage+'.json')).read_text())['complete']:
                raise ValueError('Both complete dev baselines required before training')
        if not json.loads((ROOT/'reports/day8_credit_probe.json').read_text())['complete']:
            raise ValueError('Trajectory credit probe must pass')
    model=ROOT/'runs/day7/sft_warmup/merged'
    output=ROOT/'runs/day8/smoke'
    output.mkdir(parents=True,exist_ok=True)
    text=source.read_text()
    before='from agent_r1.trainer.ppo.ray_trainer import RayAgentTrainer, need_critic_agent_ppo'
    after='from agent_r1.trainer.ppo.ray_trainer import need_critic_agent_ppo\nfrom code_repair.day8_audit import AuditedRayAgentTrainer as RayAgentTrainer'
    path_before='config_path="../config"'
    path_after='config_path='+repr(str(upstream/'agent_r1/config'))
    for old,new in ((before,after),(path_before,path_after)):
        if text.count(old)!=1:
            raise ValueError('Pinned entry extension anchor mismatch')
        text=text.replace(old,new)
    entry=ROOT/'runs/day8/audited_main_agent_ppo.py'
    entry.write_text(text)
    values={
        'algorithm.adv_estimator':'grpo','algorithm.norm_adv_by_std_in_grpo':True,'algorithm.use_kl_in_reward':False,
        'data.train_files':str(ROOT/'runs/day8/train_smoke.parquet'),
        'data.val_files':str(ROOT/'runs/day8/dev.parquet'),
        'data.train_batch_size':4,'data.val_batch_size':32,
        'data.max_prompt_length':4096,'data.max_response_length':512,
        'data.filter_overlong_prompts':True,'data.truncation':'error','data.return_raw_chat':True,
        'actor_rollout_ref.model.path':str(model),'actor_rollout_ref.model.enable_gradient_checkpointing':True,
        'actor_rollout_ref.actor.optim.lr':1e-6,'actor_rollout_ref.actor.optim.weight_decay':0.0,
        'actor_rollout_ref.actor.checkpoint.save_contents':['model','extra'],
        'actor_rollout_ref.actor.ppo_mini_batch_size':4,'actor_rollout_ref.actor.ppo_micro_batch_size_per_gpu':1,
        'actor_rollout_ref.actor.use_kl_loss':True,'actor_rollout_ref.actor.kl_loss_coef':0.001,
        'actor_rollout_ref.actor.fsdp_config.param_offload':True,'actor_rollout_ref.actor.fsdp_config.optimizer_offload':True,
        'actor_rollout_ref.rollout.name':'vllm','actor_rollout_ref.rollout.tensor_model_parallel_size':1,
        'actor_rollout_ref.rollout.gpu_memory_utilization':0.35,'actor_rollout_ref.rollout.n':4,
        'actor_rollout_ref.rollout.temperature':0.8,'actor_rollout_ref.rollout.top_p':0.95,
        'actor_rollout_ref.rollout.enforce_eager':True,
        'actor_rollout_ref.rollout.prompt_length':4096,'actor_rollout_ref.rollout.response_length':512,
        'actor_rollout_ref.rollout.log_prob_micro_batch_size_per_gpu':1,
        'actor_rollout_ref.rollout.agent.num_workers':1,'actor_rollout_ref.rollout.agent.max_steps':6,
        'actor_rollout_ref.rollout.agent.agent_flow_config_path':str(ROOT/'training/code_repair/day8.yaml'),
        'actor_rollout_ref.rollout.agent.default_agent_flow':'zzh_code_repair_day8',
        'actor_rollout_ref.ref.log_prob_micro_batch_size_per_gpu':1,'actor_rollout_ref.ref.fsdp_config.param_offload':True,
        'critic.enable':False,'reward_model.enable':False,'custom_reward_function.path':None,
        'trainer.logger':['console'],'trainer.project_name':'zzh_day8_repair_smoke','trainer.experiment_name':'sft_plus_grpo_5',
        'trainer.n_gpus_per_node':1,'trainer.nnodes':1,'trainer.default_local_dir':str(output),
        'trainer.save_freq':5,'trainer.test_freq':-1,'trainer.val_before_train':False,
        'trainer.total_epochs':5,'trainer.total_training_steps':5,'trainer.max_actor_ckpt_to_keep':1,
        'trainer.resume_mode':'disable','trainer.rollout_data_dir':str(output/'rollouts'),
        'ray_kwargs.ray_init.num_cpus':8,
    }
    runtime={key:os.environ[key] for key in ('PYTHONPATH','CODE_REPAIR_PUBLIC_DATA_DIR','CODE_REPAIR_TOKEN_FILE',
        'CODE_REPAIR_EVALUATOR_URL','CODE_REPAIR_TRACE_DIR')}
    for key,value in runtime.items():
        values['+ray_kwargs.ray_init.runtime_env.env_vars.'+key]=value
    command=[sys.executable,str(entry)]
    command.extend(key+'='+(json.dumps(value,separators=(',',':')) if not isinstance(value,str) else value)
        for key,value in values.items())
    if not args.execute:
        command+=['--cfg','job','--resolve']
    environment=os.environ.copy()
    environment.update({'CUDA_VISIBLE_DEVICES':'0','VLLM_USE_V1':'1','CUDA_HOME':'/usr/local/cuda',
        'VLLM_ATTENTION_BACKEND':'FLASH_ATTN','HF_HUB_OFFLINE':'1','TRANSFORMERS_OFFLINE':'1','OMP_NUM_THREADS':'4'})
    launch={'execute':args.execute,'argv':command,'overrides':values,
        'official_entry_sha256':expected,'extended_entry_sha256':hashlib.sha256(entry.read_bytes()).hexdigest(),
        'entry_changes':['Import observer subclass; optimizer delegates to upstream unchanged','Absolute Hydra config directory'],
        'purpose':'bounded custom repair GRPO smoke; not formal training or ability claim'}
    (output/('launch_train.json' if args.execute else 'launch_config.json')).write_text(json.dumps(launch,indent=2)+'\n')
    try:
        result=subprocess.run(command,cwd=upstream,env=environment,timeout=5400 if args.execute else 120)
        code=result.returncode
    except subprocess.TimeoutExpired:
        code=124
    status={'returncode':code,'process_completed':True,'training_attempted':args.execute,'acceptance_complete':False}
    (ROOT/'reports'/('day8_smoke_status.json' if args.execute else 'day8_config_status.json')).write_text(json.dumps(status,indent=2)+'\n')
    return code


if __name__=='__main__':
    raise SystemExit(main())
