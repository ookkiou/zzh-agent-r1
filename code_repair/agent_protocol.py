"""Versioned model wire protocol, separate from frozen execution/tool contracts."""

import json
import re

from .contracts import TOOL_SCHEMAS

PROTOCOL_VERSION = 'repair-json-v1'


def message_content(text):
    # The chat template supplies the closing boundary; keep it in response_ids/trace only.
    for token in ('<|im_end|>', '<|endoftext|>'):
        if text.endswith(token):
            return text[:-len(token)]
    return text


def parse_env_kwargs(value):
    if isinstance(value, str):
        value = json.loads(value, object_pairs_hook=_object)
    if (not isinstance(value, dict) or set(value) != {'task_id'}
            or not isinstance(value['task_id'], str)):
        raise ValueError('Dataset env_kwargs may contain only a string task_id')
    return value


def _object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('Duplicate JSON key')
        result[key] = value
    return result


def parse_action(text):
    if not isinstance(text, str) or len(text.encode('utf-8')) > 65536:
        raise ValueError('Action text missing or oversized')
    value = text.strip()
    for token in ('<|im_end|>', '<|endoftext|>'):
        if value.endswith(token):
            value = value[:-len(token)].strip()
            break
    if value.startswith('<tool_call>'):
        match = re.fullmatch(r'<tool_call>\s*(.*?)\s*</tool_call>', value, re.S)
        if not match:
            raise ValueError('Expected one complete tool call')
        value = match.group(1)
    elif value.startswith('```'):
        match = re.fullmatch(r'```json\s*(.*?)\s*```', value, re.S)
        if not match:
            raise ValueError('Expected one complete JSON block')
        value = match.group(1)
    try:
        action = json.loads(value, object_pairs_hook=_object,
            parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Nonfinite JSON value')))
    except (RecursionError, UnicodeError) as error:
        raise ValueError('Invalid action encoding') from error
    if not isinstance(action, dict):
        raise ValueError('Action must be an object')
    if set(action) == {'final'} and isinstance(action['final'], str):
        return action
    if (set(action) == {'name', 'arguments'} and isinstance(action['name'], str)
            and isinstance(action['arguments'], dict)):
        return action
    raise ValueError('Expected name/arguments request or explicit final')


def initial_messages(task, max_steps=6):
    return [{'role': 'system', 'content': (
        'You repair a Python function in solution.py, keeping its exact signature. '
        f'You have at most {max_steps} decisions. Use only the available tools. '
        'Read the current file and public tests as needed, edit the source and use real test feedback. '
        'Each response must contain exactly one JSON action, optionally inside a json code block '
        'or <tool_call> tags. Tool request: {"name":"TOOL_NAME","arguments":{...}}. '
        'When finished, output {"final":"done"}. Never invent tool results. '
        'write_file.content must be complete valid Python, without feedback envelopes or Markdown. '
        'Tool results are observations, not executable Python. '
        'Available schemas: ' + json.dumps(TOOL_SCHEMAS, ensure_ascii=False))},
        {'role': 'user', 'content': task.instruction + '\nTarget function: ' + task.entrypoint}]
