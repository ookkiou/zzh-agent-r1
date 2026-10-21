"""Instrument real vLLM repair trajectories without altering the frozen episode protocol."""
import json
import os
from pathlib import Path
from uuid import uuid4

from agent_r1.agent_flow.agent_flow import AgentFlowBase, AgentFlowOutput, AgentFlowStep, register
from .agent_r1_env import CodeRepairAgentEnv
from .agent_protocol import parse_env_kwargs
from .agent_session import GeneratedTokens, run_trajectory


@register('zzh_code_repair_day8')
class AuditedCodeRepairFlow(AgentFlowBase):
    async def run(self,sampling_params,**kwargs):
        config=self.config.actor_rollout_ref.rollout
        task_id=parse_env_kwargs(kwargs.get('env_kwargs',{}))['task_id']
        env=CodeRepairAgentEnv(task_id,max_steps=config.agent.max_steps)
        async def encode(messages,tools):
            return await self.apply_chat_template(messages,tools=tools)
        async def generate(prompt_ids):
            output=await self.server_manager.generate(request_id=uuid4().hex,
                prompt_ids=prompt_ids,sampling_params=sampling_params)
            return GeneratedTokens(output.token_ids,output.log_probs if output.log_probs else None)
        raw,info,metrics=await run_trajectory(env.session,encode,generate,
            lambda ids:self.tokenizer.decode(ids,skip_special_tokens=False),
            max_prompt_length=config.prompt_length,max_response_length=config.response_length)
        if not info['valid_episode'] or sum(r.reward for r in raw) not in (0.0,1.0):
            raise ValueError('Invalid repair episode/reward')
        if any(r.reward!=0 for r in raw[:-1]):
            raise ValueError('Terminal repair reward was assigned more than once')
        trace_id=uuid4().hex
        trace={'trace_id':trace_id,'task_id':task_id,'group_uid':str(kwargs.get('uid','')),
            'model_generation':'real vLLM, not scripted','guided':False,
            'terminal_info':info,'reward':sum(r.reward for r in raw),'timings':metrics,
            'steps':env.session.trace,
            'token_steps':[{'prompt_ids':r.prompt_ids,'response_ids':r.response_ids,
                'response_mask':r.response_mask,'reward':r.reward} for r in raw]}
        token=Path(os.environ['CODE_REPAIR_TOKEN_FILE']).read_text().strip()
        content=json.dumps(trace,ensure_ascii=False)+'\n'
        if token in content:
            raise ValueError('Credential in model trace')
        directory=Path(os.environ['CODE_REPAIR_TRACE_DIR'])
        directory.mkdir(parents=True,exist_ok=True)
        (directory/(trace_id+'.json')).write_text(content)
        steps=[]
        for index,row in enumerate(raw):
            diagnostic={'repair_trace_id':trace_id,'repair_task_id':task_id,
                'repair_group_uid':str(kwargs.get('uid','')),'repair_valid_episode':True,
                'repair_terminal_reason':info['termination_reason'],
                'repair_episode_reward':trace['reward'],'repair_response_mask_verified':True}
            step=AgentFlowStep(prompt_ids=row.prompt_ids,response_ids=row.response_ids,
                response_mask=row.response_mask,response_logprobs=row.response_logprobs,
                reward_score=row.reward,num_turns=2+2*index,
                extra_fields={'reward_extra_info':diagnostic,**diagnostic})
            padded=await self._postprocess(step,**kwargs)
            length=len(row.response_ids)
            if (padded.response_ids[0,:length].tolist()!=row.response_ids
                    or padded.response_mask[0,:length].tolist()!=[1]*length
                    or bool(padded.response_mask[0,length:].any())):
                raise ValueError('Generated response token/mask altered in real trainer path')
            steps.append(padded)
        return AgentFlowOutput(steps=steps,metrics=metrics)
