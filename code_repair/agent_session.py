"""Shared model episode driver: preserve generated text and keep observations out of responses."""

import copy
from dataclasses import dataclass
import json
import time

from .agent_protocol import initial_messages, message_content, parse_action
from .contracts import ContractError, TOOL_SCHEMAS, validate_tool_call
from .environment import RepairEnvironment


class InfrastructureUnavailable(RuntimeError):
    """Abort the rollout/batch instead of training on an invalid infrastructure failure."""


class RepairSession:
    def __init__(self, task, evaluator, *, max_steps=6, episode_timeout=240, test_timeout=10):
        self.environment = RepairEnvironment(task, evaluator=evaluator, max_steps=max_steps,
            episode_timeout=episode_timeout, test_timeout=test_timeout)
        self.task = task
        self.max_steps = max_steps
        self.tools = copy.deepcopy(TOOL_SCHEMAS)

    def reset(self):
        self.environment.reset()
        self.messages = initial_messages(self.task, self.max_steps)
        self.trace = []
        return self.observation()

    def observation(self):
        return copy.deepcopy(self.messages)

    def step(self, text):
        try:
            action = parse_action(text)
            parsed = True
        except ValueError:
            action, parsed = None, False
        contract_valid = parsed
        if parsed and 'name' in action:
            try:
                validate_tool_call(action['name'], action['arguments'])
            except ContractError:
                contract_valid = False
        result = self.environment.step(action)
        self.messages.append({'role': 'assistant', 'content': message_content(text)})
        if result.tool_response is not None:
            self.messages.append({'role': 'user', 'content': '<tool_response>\n' +
                json.dumps(result.tool_response, ensure_ascii=False, allow_nan=False) + '\n</tool_response>'})
        self.trace.append({'model_text': text, 'parsed': parsed, 'contract_valid': contract_valid, 'action': action,
            'tool_response': result.tool_response, 'reward': result.reward,
            'done': result.done, 'valid_episode': result.info['valid_episode']})
        if not result.info['valid_episode']:
            raise InfrastructureUnavailable('Repair evaluator unavailable; abort invalid rollout')
        return result

    def finish_context_limit(self):
        # Automatic budget termination evaluates the current patch, without inventing model tokens.
        with self.environment._lock:
            reason = 'episode_timeout' if self.environment._remaining() <= 0 else 'context_limit'
            result = self.environment._finish(reason)
        if not result.info['valid_episode']:
            raise InfrastructureUnavailable('Repair evaluator unavailable at context limit')
        return result

    def close(self):
        self.environment.close()


@dataclass
class GeneratedTokens:
    token_ids: list
    log_probs: list | None = None


@dataclass
class ModelStep:
    prompt_ids: list
    response_ids: list
    response_mask: list
    reward: float
    response_logprobs: list | None = None


async def run_trajectory(session, encode, generate, decode, *, max_prompt_length, max_response_length):
    """One training row per generation: all tool observations belong to the next prompt."""
    steps = []
    timings = {'generate_sequences': 0.0, 'tool_calls': 0.0}
    try:
        session.reset()
        for _ in range(session.max_steps):
            prompt_ids = list(await encode(session.observation(), session.tools))
            if len(prompt_ids) > max_prompt_length:
                if not steps:
                    raise ValueError('Initial repair prompt exceeds configured limit')
                result = session.finish_context_limit()
                steps[-1].reward = result.reward
                return steps, result.info, timings
            start = time.monotonic()
            output = await generate(prompt_ids)
            timings['generate_sequences'] += time.monotonic() - start
            response_ids = list(output.token_ids[:max_response_length])
            if not response_ids:
                raise InfrastructureUnavailable('Generation returned no tokens; abort invalid rollout')
            log_probs = None
            if output.log_probs is not None:
                log_probs = list(output.log_probs[:len(response_ids)])
                if len(log_probs) != len(response_ids):
                    raise ValueError('Generated log probabilities are not aligned')
            start = time.monotonic()
            result = session.step(decode(response_ids))
            timings['tool_calls'] += time.monotonic() - start
            steps.append(ModelStep(prompt_ids, response_ids, [1] * len(response_ids), result.reward, log_probs))
            if result.done:
                return steps, result.info, timings
        raise RuntimeError('Environment did not terminate at its configured decision limit')
    finally:
        session.close()
