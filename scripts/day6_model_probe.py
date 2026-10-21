"""GPU inference and guided three-tool protocol diagnostic, never a benchmark."""

import json
from pathlib import Path
import re
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def parse_model_tool_call(response):
    text = response.strip()
    if text.endswith('<|im_end|>'):
        text = text[:-len('<|im_end|>')].strip()
    for format_name, pattern in (
        ('hermes', r'<tool_call>\s*(.*?)\s*</tool_call>'),
        ('fenced_json', r'```json\s*(.*?)\s*```'),
    ):
        match = re.fullmatch(pattern, text, re.S)
        if match:
            action = json.loads(match.group(1))
            if not isinstance(action, dict) or set(action) != {'name', 'arguments'}:
                raise ValueError('Tool call must contain exactly name and arguments')
            return action, format_name
    raise ValueError('Expected one complete Hermes or fenced JSON tool call')


def main():
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer
    from code_repair.environment import RepairEnvironment
    from code_repair.evaluation import RemoteEvaluator
    from code_repair.tasks import load_task

    report_path = ROOT / 'reports/day6_model_protocol.json'
    report = {'complete': False, 'guided': True, 'training_performed': False,
              'model_ability_benchmark': False, 'started_at': time.time(), 'steps': []}
    def save():
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    save()
    try:
        lock = json.loads((ROOT / 'TRAINING_SOURCE_LOCK.json').read_text())
        model_path = ROOT / 'models' / ('qwen-coder-1.5b-' + lock['model']['revision'])
        tokenizer = AutoTokenizer.from_pretrained(model_path, local_files_only=True)
        report['native_template_mentions_tools'] = 'tools' in (tokenizer.chat_template or '')
        report['protocol_prompt'] = 'Explicit schema; strict whole-message Hermes/fenced JSON adapter; guided diagnostic'
        model = AutoModelForCausalLM.from_pretrained(model_path, local_files_only=True,
                    torch_dtype=torch.bfloat16, attn_implementation='sdpa').to('cuda').eval()
        report['gpu'] = torch.cuda.get_device_name(0)
        task = load_task(ROOT / 'data/day6-public-task', include_private=False)
        token = (ROOT / 'runs/day6/evaluator_token').read_text().strip()
        evaluator = RemoteEvaluator('http://127.0.0.1:18765', token, task.task_id)
        report['service_health'] = evaluator.health()
        with RepairEnvironment(task, evaluator=evaluator, max_steps=6, episode_timeout=240,
                               test_timeout=15) as environment:
            for name, guidance in (
                ('read_file', 'Call read_file with path solution.py. Do not answer in prose.'),
                ('write_file', 'Repair the bug from the instruction and file you read. Call write_file with path solution.py and the complete corrected Python source in content.'),
                ('run_tests', 'Request the run_tests tool; never invent test results. '
                    'Return exactly this tool request JSON, wrapped in tool_call tags or a json code block: '
                    '{"name":"run_tests","arguments":{}}. Do not return ok, output, error or test results.'),
            ):
                observation = environment.observation()
                if name == 'write_file':
                    guidance += (' The content argument must be raw valid Python source, starting with def; '
                        'do not copy any JSON envelope, tool_response tags or Markdown fences into content. '
                        'Here is the public source as plain Python:\n' + task.starter_source)
                observation['messages'][0]['content'] += (
                    '\nTool protocol: return exactly one <tool_call>{"name":"TOOL_NAME",'
                    '"arguments":{...}}</tool_call>. Use valid JSON; no Markdown fences. '
                    'Available tool JSON schemas: ' + json.dumps(observation['tools'], ensure_ascii=False))
                messages = observation['messages'] + [{'role': 'user', 'content': guidance}]
                inputs = tokenizer.apply_chat_template(messages, tools=observation['tools'],
                            add_generation_prompt=True, return_tensors='pt', return_dict=True).to('cuda')
                started = time.monotonic()
                with torch.inference_mode():
                    generated = model.generate(**inputs, max_new_tokens=384, do_sample=False,
                                               pad_token_id=tokenizer.eos_token_id)
                response = tokenizer.decode(generated[0, inputs['input_ids'].shape[1]:], skip_special_tokens=False)
                report['last_response'] = {'expected_tool': name, 'generated_text': response}
                save()
                action, wire_format = parse_model_tool_call(response)
                if action.get('name') != name:
                    raise ValueError('Unexpected model tool name for guided stage ' + name)
                result = environment.step(action)
                report['steps'].append({'expected_tool': name, 'generated_text': response,
                    'wire_format': wire_format,
                    'elapsed_seconds': time.monotonic() - started, 'action': action,
                    'tool_response': result.tool_response})
                save()
                if not result.tool_response or not result.tool_response['ok']:
                    raise ValueError('Tool rejected model action: ' + name)
            result = environment.step({'final': 'Guided protocol diagnostic finished.'})
            report.update({'controller_terminated': True, 'terminal_reward': result.reward,
                           'terminal_info': result.info,
                           'complete': bool(result.info['valid_episode'])})
        serialized = json.dumps(report, ensure_ascii=False)
        if token in serialized:
            raise RuntimeError('Control credential leaked into diagnostic report')
        report['credential_absent_from_report'] = True
        save()
        print(json.dumps({'complete': report['complete'], 'tools': [s['expected_tool'] for s in report['steps']],
                          'terminal_reward': report['terminal_reward'], 'guided': True}))
    except Exception as error:
        report['error'] = type(error).__name__ + ': ' + str(error)
        save()
        raise


if __name__ == '__main__':
    main()
