"""Model-free repair episode; a later adapter will implement Agent-R1 AgentEnv."""

import asyncio
import copy
from dataclasses import dataclass
import json
import os
from pathlib import Path
import tempfile
import threading
import time
import uuid

from .contracts import ContractError, TOOL_SCHEMAS, tool_result, validate_candidate_source, validate_tool_call
from .evaluation import LocalEvaluator


@dataclass(frozen=True)
class StepResult:
    observation: dict
    reward: float
    done: bool
    info: dict
    tool_response: dict | None = None


class RepairEnvironment:
    def __init__(self, task, *, backend=None, evaluator=None, max_steps=6, episode_timeout=120,
                 test_timeout=5, clock=time.monotonic):
        if type(max_steps) is not int or max_steps < 1:
            raise ValueError("max_steps must be a positive integer")
        if episode_timeout <= 0 or test_timeout <= 0:
            raise ValueError("Timeouts must be positive")
        if (backend is None) == (evaluator is None):
            raise ValueError("Provide exactly one backend or evaluator")
        self.task, self.backend = task, backend if backend is not None else evaluator
        self.evaluator = evaluator if evaluator is not None else LocalEvaluator(task, backend)
        self.max_steps, self.episode_timeout = max_steps, episode_timeout
        self.test_timeout, self.clock = test_timeout, clock
        self._lock = threading.RLock()
        self._temporary = None
        self.workspace = None
        self.done = False
        self.closed = True
        self.trace = []

    def reset(self):
        with self._lock:
            self.close()
            self._temporary = tempfile.TemporaryDirectory(prefix="code-repair-episode-")
            self.workspace = Path(self._temporary.name)
            (self.workspace / "solution.py").write_text(self.task.starter_source, encoding="utf-8")
            (self.workspace / "public_tests.py").write_text(self.task.public_test_source, encoding="utf-8")
            (self.workspace / "public_tests.py").chmod(0o444)
            self.steps, self.started = 0, self.clock()
            self.done, self.closed = False, False
            self.trace, self._terminal_info = [], None
            self._invalid_infrastructure = False
            self.messages = [
                {"role": "system", "content": (
                    "修复 solution.py 中的目标函数，保留签名。只使用提供的三个工具，"
                    "根据公开测试反馈修改。完成后给出最终回复。"
                    f"最多 {self.max_steps} 次决策。")},
                {"role": "user", "content": self.task.instruction}]
            return self.observation()

    def observation(self):
        return {"messages": copy.deepcopy(self.messages), "tools": copy.deepcopy(TOOL_SCHEMAS)}

    def _file(self, name):
        path = self.workspace / name
        if path.is_symlink() or path.resolve().parent != self.workspace.resolve():
            raise ContractError("任务文件不能是符号链接或指向工作区外")
        return path

    def _remaining(self):
        return self.episode_timeout - (self.clock() - self.started)

    def _execute_tool(self, name, arguments):
        try:
            arguments = validate_tool_call(name, arguments)
        except ContractError as error:
            return tool_result(ok=False, error_code="invalid_arguments", message=str(error))
        try:
            if name == "read_file":
                return tool_result(ok=True, output=self._file(arguments["path"]).read_text(encoding="utf-8"))
            if name == "write_file":
                try:
                    validate_candidate_source(arguments["content"], self.task.starter_source, self.task.entrypoint)
                except ContractError as error:
                    return tool_result(ok=False, error_code="invalid_source", message=str(error))
                target = self._file("solution.py")
                temporary = self.workspace / (".write-" + uuid.uuid4().hex)
                try:
                    temporary.write_text(arguments["content"], encoding="utf-8")
                    os.replace(temporary, target)
                finally:
                    temporary.unlink(missing_ok=True)
                return tool_result(ok=True, output={"path": "solution.py", "written": True})
            source = self._file("solution.py").read_text(encoding="utf-8")
            result = self.evaluator.check(source, "public",
                                          timeout=max(0.001, min(self.test_timeout, self._remaining())))
            if result["status"] == "infrastructure_error":
                self._invalid_infrastructure = True
                return tool_result(ok=False, error_code="infrastructure_error", message="执行后端不可用")
            if result["status"] != "completed":
                return tool_result(ok=False, error_code="execution_" + result["status"],
                                   message="公开测试未正常完成")
            return tool_result(ok=True, output=result)
        except ContractError as error:
            return tool_result(ok=False, error_code="invalid_path", message=str(error))
        except OSError:
            self._invalid_infrastructure = True
            return tool_result(ok=False, error_code="infrastructure_error", message="工作区文件操作失败")

    def _result(self, reward=0.0, response=None):
        info = copy.deepcopy(self._terminal_info) if self.done else {
            "step_index": self.steps, "valid_episode": True, "backend": self.backend.name}
        return StepResult(self.observation(), reward, self.done, info, response)

    def _finish(self, reason, response=None):
        if self.done:
            return self._result(response=response)
        acceptance = None
        if self._invalid_infrastructure:
            reason, valid, reward = "infrastructure_error", False, 0.0
        elif reason == "episode_timeout":
            valid, reward = True, 0.0
        else:
            try:
                source = self._file("solution.py").read_text(encoding="utf-8")
                validate_candidate_source(source, self.task.starter_source, self.task.entrypoint)
                result = self.evaluator.check(source, "private", timeout=self.test_timeout)
                # Private case IDs, inputs, expected values and exceptions never enter observations/trace.
                acceptance = {key: result[key] for key in ("status", "tests", "passed", "failed")}
                valid = result["status"] != "infrastructure_error"
                reward = float(valid and result["status"] == "completed" and result["failed"] == 0)
                if not valid:
                    reason = "infrastructure_error"
            except ContractError:
                valid, reward = True, 0.0
            except OSError:
                reason, valid, reward = "infrastructure_error", False, 0.0
        self.done = True
        self._terminal_info = {"termination_reason": reason, "step_index": self.steps,
                               "valid_episode": valid, "backend": self.backend.name,
                               "acceptance": acceptance}
        self.trace.append({"event": "terminal", "reward": reward, **copy.deepcopy(self._terminal_info)})
        return self._result(reward, response)

    def step(self, action):
        with self._lock:
            if self.closed:
                raise RuntimeError("Environment is closed; call reset() first")
            if self.done:
                return self._result()
            if self._remaining() <= 0:
                return self._finish("episode_timeout")
            self.steps += 1
            started = self.clock()
            if isinstance(action, dict) and set(action) == {"final"} and isinstance(action["final"], str):
                self.messages.append({"role": "assistant", "content": action["final"]})
                self.trace.append({"event": "action", "step": self.steps, "action": copy.deepcopy(action)})
                return self._finish("agent_final")
            if isinstance(action, dict) and set(action) == {"name", "arguments"}:
                name, arguments = action["name"], action["arguments"]
                response = self._execute_tool(name, arguments)
                call_id = "call_" + uuid.uuid4().hex
                self.messages.append({"role": "assistant", "content": None, "tool_calls": [{
                    "id": call_id, "type": "function", "function": {
                        "name": name if isinstance(name, str) else "invalid_action",
                        "arguments": json.dumps(arguments, ensure_ascii=False)}}]})
                self.messages.append({"role": "tool", "tool_call_id": call_id,
                                      "content": json.dumps(response, ensure_ascii=False)})
            else:
                response = tool_result(ok=False, error_code="invalid_action", message="需要工具调用或最终回复")
                self.messages.append({"role": "user", "content": json.dumps(response, ensure_ascii=False)})
            self.trace.append({"event": "action", "step": self.steps, "action": copy.deepcopy(action),
                               "tool_response": copy.deepcopy(response),
                               "elapsed_seconds": self.clock() - started})
            if self._invalid_infrastructure:
                return self._finish("infrastructure_error", response)
            if self._remaining() <= 0:
                return self._finish("episode_timeout", response)
            if self.steps >= self.max_steps:
                return self._finish("step_limit", response)
            return self._result(response=response)

    async def astep(self, action):
        return await asyncio.to_thread(self.step, action)

    def close(self):
        with self._lock:
            if self._temporary is not None:
                self._temporary.cleanup()
                self._temporary = None
            self.closed = True

    def __enter__(self):
        if self.closed:
            self.reset()
        return self

    def __exit__(self, *args):
        self.close()
