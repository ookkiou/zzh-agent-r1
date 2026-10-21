"""Pinned AgentFlow adapter sharing the exact episode runner used by model diagnostics."""

from uuid import uuid4

from agent_r1.agent_flow.agent_flow import AgentFlowBase, AgentFlowOutput, AgentFlowStep, register

from .agent_r1_env import CodeRepairAgentEnv
from .agent_protocol import parse_env_kwargs
from .agent_session import GeneratedTokens, run_trajectory


@register('zzh_code_repair')
class CodeRepairFlow(AgentFlowBase):
    async def run(self, sampling_params, **kwargs):
        config = self.config.actor_rollout_ref.rollout
        values = parse_env_kwargs(kwargs.get('env_kwargs', {}))
        env = CodeRepairAgentEnv(values['task_id'], max_steps=config.agent.max_steps)

        async def encode(messages, tools):
            return await self.apply_chat_template(messages, tools=tools)

        async def generate(prompt_ids):
            output = await self.server_manager.generate(request_id=uuid4().hex,
                prompt_ids=prompt_ids, sampling_params=sampling_params)
            return GeneratedTokens(output.token_ids, output.log_probs if output.log_probs else None)

        raw_steps, info, metrics = await run_trajectory(env.session, encode, generate,
            lambda ids: self.tokenizer.decode(ids, skip_special_tokens=False),
            max_prompt_length=config.prompt_length, max_response_length=config.response_length)
        steps = []
        for row in raw_steps:
            step = AgentFlowStep(prompt_ids=row.prompt_ids, response_ids=row.response_ids,
                response_mask=row.response_mask, response_logprobs=row.response_logprobs,
                reward_score=row.reward, extra_fields={'repair_valid_episode': info['valid_episode']})
            steps.append(await self._postprocess(step, **kwargs))
        return AgentFlowOutput(steps=steps, metrics=metrics)
