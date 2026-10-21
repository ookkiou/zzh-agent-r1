"""Observe the actual pre-optimizer batch; delegate optimization to pinned upstream code."""
from collections import defaultdict
import json
from pathlib import Path

import torch
from agent_r1.trainer.ppo.ray_trainer import RayAgentTrainer


def audit_batch(batch,n):
    mask=batch.batch['response_mask']
    rewards=batch.batch['token_level_scores']
    advantages=batch.batch['advantages']
    response_attention=batch.batch['attention_mask'][:,-mask.shape[1]:]
    if not bool(((mask==0)|(mask==1)).all()) or bool((mask[response_attention==0]!=0).any()):
        raise ValueError('Loss mask/padding contract violated')
    if bool((rewards[mask==0]!=0).any()) or bool((advantages[mask==0]!=0).any()):
        raise ValueError('Reward or advantage assigned to ungenerated/padded tokens')
    trajectories=defaultdict(list)
    for i,uid in enumerate(batch.non_tensor_batch['trajectory_uids']):
        trajectories[str(uid)].append(i)
    groups=defaultdict(list)
    actual=[]
    for uid,indices in trajectories.items():
        indices=sorted(indices,key=lambda i:int(batch.non_tensor_batch['step_indices'][i]))
        group={str(batch.non_tensor_batch['uid'][i]) for i in indices}
        task_ids={str(batch.non_tensor_batch['repair_task_id'][i]) for i in indices}
        if len(group)!=1 or len(task_ids)!=1 or [int(batch.non_tensor_batch['step_indices'][i]) for i in indices]!=list(range(len(indices))):
            raise ValueError('Broken trajectory/group alignment')
        scores=[float(rewards[i].sum()) for i in indices]
        if any(s!=0 for s in scores[:-1]) or sum(scores) not in (0.0,1.0):
            raise ValueError('Terminal reward repeated or nonbinary')
        if not all(bool(batch.non_tensor_batch['repair_valid_episode'][i]) for i in indices):
            raise ValueError('Invalid infrastructure episode entered optimizer batch')
        if float(batch.non_tensor_batch['repair_episode_reward'][indices[0]])!=sum(scores):
            raise ValueError('Environment reward differs from actual trainer reward')
        item={'trajectory_uid':uid,'group_uid':next(iter(group)),'task_id':next(iter(task_ids)),
            'trace_id':str(batch.non_tensor_batch['repair_trace_id'][indices[0]]),
            'steps':len(indices),'step_rewards':scores,'reward':sum(scores)}
        groups[item['group_uid']].append((item,indices))
        actual.append(item)
    mixed=0
    for group,rows in groups.items():
        if len(rows)!=n:
            raise ValueError('Incomplete same-task rollout group')
        if len({item['task_id'] for item,_ in rows})!=1:
            raise ValueError('Cross-task GRPO group')
        values=torch.tensor([item['reward'] for item,_ in rows],device=advantages.device,dtype=advantages.dtype)
        expected=(values-values.mean())/(values.std()+1e-6)
        mixed+=len(set(values.tolist()))>1
        for target,(item,indices) in zip(expected,rows):
            for i in indices:
                selected=advantages[i][mask[i].bool()]
                if not torch.allclose(selected,target.expand_as(selected),atol=1e-5,rtol=1e-5):
                    raise ValueError('Actual GRPO advantage differs from trajectory-level group advantage')
    return {'trajectory_count':len(actual),'group_count':len(groups),'mixed_reward_groups':mixed,
        'response_mask_verified':True,'terminal_reward_once_verified':True,
        'actual_trajectory_grpo_advantages_verified':True,
        'nonzero_advantage_tokens':int(torch.count_nonzero(advantages)),
        'trajectories':actual}


class AuditedRayAgentTrainer(RayAgentTrainer):
    def _update_actor(self,batch):
        report=audit_batch(batch,self.config.actor_rollout_ref.rollout.n)
        report['global_step']=self.global_steps
        report['before_real_optimizer_update']=True
        path=Path(self.config.trainer.default_local_dir)/'training_batch_audit.jsonl'
        path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('a') as stream:
            stream.write(json.dumps(report)+'\n')
        return super()._update_actor(batch)
