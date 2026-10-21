"""Actual pinned Agent-R1 AgentEnv adapter; credentials are control-plane environment only."""

import os
from pathlib import Path

from agent_r1.env.base import Action, AgentEnv, Observation

from .agent_session import RepairSession
from .evaluation import RemoteEvaluator
from .public_data import load_public_task


@AgentEnv.register('zzh_code_repair')
class CodeRepairAgentEnv(AgentEnv):
    def __init__(self, task_id, max_steps=6, episode_timeout=240, test_timeout=10):
        task = load_public_task(os.environ['CODE_REPAIR_PUBLIC_DATA_DIR'], task_id)
        token = Path(os.environ['CODE_REPAIR_TOKEN_FILE']).read_text().strip()
        evaluator = RemoteEvaluator(os.environ['CODE_REPAIR_EVALUATOR_URL'], token, task.task_id)
        self.session = RepairSession(task, evaluator, max_steps=max_steps,
            episode_timeout=episode_timeout, test_timeout=test_timeout)
        self.tool_schemas = self.session.tools

    def reset(self, **kwargs):
        return Observation(messages=self.session.reset())

    async def step(self, action):
        if not isinstance(action, Action) or not isinstance(action.text, str):
            raise TypeError('Code repair requires an Agent-R1 text Action')
        import asyncio
        try:
            result = await asyncio.to_thread(self.session.step, action.text)
        except BaseException:
            self.close()
            raise
        if result.done:
            self.close()
        return Observation(messages=self.session.observation()), result.reward, result.done, result.info

    def close(self):
        self.session.close()
