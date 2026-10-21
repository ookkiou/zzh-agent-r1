"""Exercise actual upstream trajectory GRPO credit and the pre-optimizer auditor."""
import json
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))


def main():
    import numpy as np
    import torch
    from tensordict import TensorDict
    from verl.protocol import DataProto
    from agent_r1.trainer.ppo.core_algos import compute_grpo_outcome_advantage
    from code_repair.day8_audit import audit_batch
    mask=torch.tensor([[1,1,0]]*5)
    rewards=torch.zeros((5,3));rewards[1,1]=1
    trajectories=np.array(['success','success','fail','fail','fail'],dtype=object)
    groups=np.array(['question']*5,dtype=object)
    advantages,_=compute_grpo_outcome_advantage(rewards,mask,groups,trajectories)
    data=DataProto(batch=TensorDict({'response_mask':mask,'token_level_scores':rewards,
        'advantages':advantages,'attention_mask':torch.tensor([[1,1,1,1,0]]*5)},batch_size=5),
        non_tensor_batch={'trajectory_uids':trajectories,'uid':groups,
            'step_indices':np.array([0,1,0,1,2]),
            'repair_task_id':np.array(['fixture']*5,dtype=object),
            'repair_trace_id':trajectories,'repair_valid_episode':np.array([True]*5),
            'repair_episode_reward':np.array([1.,1.,0.,0.,0.])})
    result=audit_batch(data,2)
    assert result['trajectory_count']==2 and result['mixed_reward_groups']==1
    assert advantages[0,0]>0 and advantages[2,0]<0
    assert torch.equal(advantages[0],advantages[1]) and torch.equal(advantages[2],advantages[4])
    assert not bool(advantages[:,2].any())
    data.batch['token_level_scores'][0,1]=1
    try:
        audit_batch(data,2)
    except ValueError:
        rejected=True
    else:
        rejected=False
    assert rejected,'Repeated terminal reward must be rejected'
    report={'complete':True,'actual_pinned_upstream_grpo':True,'scripted_tensor_probe':True,
        'positive_and_negative_advantages':True,'same_advantage_across_trajectory_steps':True,
        'padding_advantages_zero':True,'repeated_reward_rejected':True,'real_training':False}
    (ROOT/'reports/day8_credit_probe.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))


if __name__=='__main__':
    main()
