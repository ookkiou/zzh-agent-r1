"""Explicit held-out repair entry point, separate from the frozen dev profile.

Install next to zzhclaw/agent/repair.py. The existing trajectory, transport,
tools, prompts, budgets and application session handling remain inherited.
"""
from .core import Agent
from .repair import CodeRepairAgent


class ApplicationTestRepairAgent(CodeRepairAgent):
    def __init__(self, task, evaluator, transport, *, task_split,
                 test_task_ids, session_manager=None):
        if task_split != "test" or task.task_id not in test_task_ids:
            raise ValueError("Explicit frozen test task allowlist required")
        if task.private_cases:
            raise ValueError("Application inference requires public-only task resources")
        # The original constructor deliberately allows dev only. This separate
        # entry initializes the same Agent state without relabeling test as dev.
        Agent.__init__(self, llm=transport, session_manager=session_manager,
                       system_prompt=None, permission_mode="auto")
        self.task, self.evaluator, self.transport = task, evaluator, transport
        self.last_result = None

    def run(self, *args, **kwargs):
        result = super().run(*args, **kwargs)
        self.last_result.update(final_test=True, split="test")
        return result
