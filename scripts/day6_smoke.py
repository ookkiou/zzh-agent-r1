"""Resolve or execute a small GRPO run using the pinned official GSM8K recipe."""

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stage', choices=('single', 'tool'), default='single')
    parser.add_argument('--execute', action='store_true', help='Without this option, only resolve Hydra configuration')
    args = parser.parse_args()
    upstream = ROOT / 'runs/day6/Agent-R1'
    lock = json.loads((ROOT / 'TRAINING_SOURCE_LOCK.json').read_text())
    model = ROOT / 'models' / ('qwen-coder-1.5b-' + lock['model']['revision'])
    download = json.loads((ROOT / 'reports/day6_model_download_status.json').read_text())
    if download['complete'] is not True or download['revision'] != lock['model']['revision']:
        raise SystemExit('Verified model download required')
    output = ROOT / 'runs/day6-smoke' / args.stage
    output.mkdir(parents=True, exist_ok=True)
    values = {
        'algorithm.adv_estimator': 'grpo', 'algorithm.use_kl_in_reward': False,
        'data.train_files': str(ROOT / 'data/day6-gsm8k' / args.stage / 'train.parquet'),
        'data.val_files': str(ROOT / 'data/day6-gsm8k' / args.stage / 'test.parquet'),
        'data.train_batch_size': 4, 'data.val_batch_size': 8,
        'data.max_prompt_length': 1536, 'data.max_response_length': 256,
        'data.filter_overlong_prompts': True, 'data.truncation': 'error', 'data.return_raw_chat': True,
        'actor_rollout_ref.model.path': str(model),
        'actor_rollout_ref.model.enable_gradient_checkpointing': True,
        'actor_rollout_ref.actor.optim.lr': 1e-6,
        'actor_rollout_ref.actor.optim.weight_decay': 0.0,
        'actor_rollout_ref.actor.checkpoint.save_contents': ['model', 'extra'],
        'actor_rollout_ref.actor.ppo_mini_batch_size': 4,
        'actor_rollout_ref.actor.ppo_micro_batch_size_per_gpu': 1,
        'actor_rollout_ref.actor.use_kl_loss': True, 'actor_rollout_ref.actor.kl_loss_coef': 0.001,
        'actor_rollout_ref.actor.fsdp_config.param_offload': True,
        'actor_rollout_ref.actor.fsdp_config.optimizer_offload': True,
        'actor_rollout_ref.rollout.name': 'vllm', 'actor_rollout_ref.rollout.tensor_model_parallel_size': 1,
        'actor_rollout_ref.rollout.gpu_memory_utilization': 0.35,
        'actor_rollout_ref.rollout.n': 2, 'actor_rollout_ref.rollout.enforce_eager': True,
        'actor_rollout_ref.rollout.prompt_length': 1536, 'actor_rollout_ref.rollout.response_length': 256,
        'actor_rollout_ref.rollout.log_prob_micro_batch_size_per_gpu': 1,
        'actor_rollout_ref.rollout.agent.num_workers': 1,
        'actor_rollout_ref.rollout.agent.max_steps': 3 if args.stage == 'tool' else 1,
        'actor_rollout_ref.ref.log_prob_micro_batch_size_per_gpu': 1,
        'actor_rollout_ref.ref.fsdp_config.param_offload': True,
        'critic.enable': False, 'reward_model.enable': False,
        'custom_reward_function.path': str(upstream / 'recipes/gsm8k/reward_fn.py'),
        'custom_reward_function.name': 'compute_score',
        'trainer.logger': ['console'], 'trainer.project_name': 'zzh_day6_official_diagnostic',
        'trainer.experiment_name': args.stage, 'trainer.n_gpus_per_node': 1, 'trainer.nnodes': 1,
        'trainer.default_local_dir': str(output), 'trainer.save_freq': 1, 'trainer.test_freq': -1,
        'trainer.val_before_train': False, 'trainer.total_epochs': 1, 'trainer.total_training_steps': 2,
        'trainer.max_actor_ckpt_to_keep': 1, 'trainer.resume_mode': 'disable',
        'trainer.rollout_data_dir': str(output / 'rollouts'),
        'ray_kwargs.ray_init.num_cpus': 8,
    }
    if args.stage == 'tool':
        values['actor_rollout_ref.rollout.agent.agent_flow_config_path'] = str(upstream / 'recipes/gsm8k/base.yaml')
        values['actor_rollout_ref.rollout.agent.default_agent_flow'] = 'gsm8k_tool'
    command = [sys.executable, '-m', 'agent_r1.trainer.main_agent_ppo']
    command.extend(key + '=' + (json.dumps(value, separators=(',', ':')) if not isinstance(value, str) else value)
                   for key, value in values.items())
    if not args.execute:
        command.extend(['--cfg', 'job', '--resolve'])
    environment = os.environ.copy()
    environment.update({'CUDA_VISIBLE_DEVICES': '0', 'VLLM_USE_V1': '1', 'CUDA_HOME': '/usr/local/cuda',
                        'VLLM_ATTENTION_BACKEND': 'FLASH_ATTN',
                        'PATH': str(Path(sys.executable).parent) + ':/usr/local/cuda/bin:/root/miniconda3/bin:' + os.defpath,
                        'HF_HUB_OFFLINE': '1', 'TRANSFORMERS_OFFLINE': '1', 'TOKENIZERS_PARALLELISM': 'false',
                        'OMP_NUM_THREADS': '4'})
    (output / 'launch.json').write_text(json.dumps({'argv': command, 'overrides': values,
        'execute': args.execute, 'purpose': 'official recipe diagnostic; not code-repair training'}, indent=2) + '\n')
    result = subprocess.run(command, cwd=upstream, env=environment, timeout=1800 if args.execute else 120)
    status_name = args.stage + ('_smoke' if args.execute else '_config')
    (ROOT / 'reports' / ('day6_' + status_name + '_status.json')).write_text(json.dumps({
        'returncode': result.returncode, 'process_completed': True,
        'training_attempted': args.execute, 'training_acceptance_complete': False,
        'note': 'Exit status alone does not prove nonzero updates or checkpoint reload'}, indent=2) + '\n')
    return result.returncode


if __name__ == '__main__':
    raise SystemExit(main())
