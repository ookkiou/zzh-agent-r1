"""Exercise actual Agent-R1 tensor postprocessing using scripted public-task actions, no training."""

import asyncio
import json
import os
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / 'runs/day6/Agent-R1')]


async def probe():
    import torch
    from omegaconf import OmegaConf
    from transformers import AutoTokenizer
    from code_repair.agent_r1_flow import CodeRepairFlow
    from code_repair.agent_protocol import initial_messages
    from code_repair.public_data import load_public_task
    selection = json.loads((ROOT / 'runs/day7/selection.json').read_text())
    task = load_public_task(os.environ['CODE_REPAIR_PUBLIC_DATA_DIR'], selection['tasks'][0]['task_id'])
    lock = json.loads((ROOT / 'TRAINING_SOURCE_LOCK.json').read_text())
    model = ROOT / 'models' / ('qwen-coder-1.5b-' + lock['model']['revision'])
    tokenizer = AutoTokenizer.from_pretrained(model, local_files_only=True)
    texts = ['{"name":"read_file","arguments":{"path":"solution.py"}}',
             '{"name":"run_tests","arguments":{}}', '{"final":"done"}']
    expected = [tokenizer.encode(text, add_special_tokens=False) for text in texts]
    prompts = []
    class ScriptedServer:
        async def generate(self, *, request_id, prompt_ids, sampling_params):
            index = len(prompts)
            prompts.append(list(prompt_ids))
            return SimpleNamespace(token_ids=expected[index], log_probs=None)
    config = OmegaConf.create({'actor_rollout_ref': {'rollout': {'prompt_length': 4096,
        'response_length': 512, 'agent': {'max_steps': 6}}}})
    flow = CodeRepairFlow(trainer_config=SimpleNamespace(config=config), server_manager=ScriptedServer(),
        reward_loop_worker=None, tokenizer=tokenizer, processor=None,
        dataset_cls=None, dataset_config=OmegaConf.create({}))
    output = await flow.run({}, raw_prompt=initial_messages(task), env_kwargs={'task_id': task.task_id})
    assert len(output.steps) == 3
    for row, ids in zip(output.steps, expected):
        assert row.response_ids.shape == (1, 512)
        assert row.prompt_ids.shape == (1, 4096)
        assert row.response_ids[0, :len(ids)].tolist() == ids
        assert row.response_mask[0, :len(ids)].tolist() == [1] * len(ids)
        assert int(row.response_mask[0, len(ids):].sum()) == 0
        assert torch.isfinite(row.input_ids).all()
    assert '<tool_response>' in tokenizer.decode(prompts[1], skip_special_tokens=False)
    assert all(row.reward_score == 0 for row in output.steps)
    report = {'complete': True, 'scripted': True, 'uses_model_generation': False,
        'training_performed': False, 'actual_pinned_agent_r1_tensor_path': True,
        'steps': 3, 'tool_observations_only_in_prompts': True,
        'response_mask_generated_one_padding_zero': True, 'terminal_reward': 0.0,
        'note': 'Current defective formal task; no reference or private resources loaded by client'}
    (ROOT / 'reports/day7_trainer_contract.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    asyncio.run(probe())
