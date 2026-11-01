"""Run in the ZzhClaw checkout with the training runtime on PYTHONPATH."""
import pytest

from test_repair_profile import Evaluator, ScriptedTransport, action, runtime, task
from zzhclaw.agent.repair import CodeRepairAgent
from zzhclaw.agent.repair_test import ApplicationTestRepairAgent


def test_test_entry_preserves_runner_tools_and_marks_test(task, session_manager):
    transport = ScriptedTransport([
        action('write_file', path='solution.py', content='def increment(x):\n    return x + 1\n'),
        action('run_tests'), '{"final":"done"}'])
    evaluator = Evaluator()
    agent = ApplicationTestRepairAgent(task, evaluator, transport,
        task_split='test', test_task_ids={task.task_id}, session_manager=session_manager)
    agent.run()
    assert isinstance(agent, CodeRepairAgent)
    assert agent.last_result['final_test'] is True
    assert agent.last_result['split'] == 'test'
    assert agent.last_result['reward'] == 1
    assert [mode for _, mode in evaluator.calls] == ['public', 'private']
    assert len(session_manager.list_sessions()) == 1


@pytest.mark.parametrize('split,ids', [('dev', {'dev-fixture'}), ('train', {'dev-fixture'}),
                                      ('test', {'other-task'})])
def test_requires_explicit_test_allowlist(task, session_manager, split, ids):
    with pytest.raises(ValueError, match='allowlist'):
        ApplicationTestRepairAgent(task, Evaluator(), ScriptedTransport([]),
            task_split=split, test_task_ids=ids, session_manager=session_manager)


def test_private_resources_cannot_enter_application(task, session_manager):
    from dataclasses import replace
    private_task = replace(task, private_cases=({'args': [1], 'expected': 2},))
    with pytest.raises(ValueError, match='public-only'):
        ApplicationTestRepairAgent(private_task, Evaluator(), ScriptedTransport([]),
            task_split='test', test_task_ids={task.task_id}, session_manager=session_manager)


def test_original_dev_entry_still_rejects_test(task, session_manager):
    with pytest.raises(ValueError, match='dev'):
        CodeRepairAgent(task, Evaluator(), ScriptedTransport([]),
            task_split='test', session_manager=session_manager)


def test_infra_error_remains_invalid(task, runtime, session_manager):
    agent = ApplicationTestRepairAgent(task, Evaluator(unavailable=True),
        ScriptedTransport(['{"final":"done"}']), task_split='test',
        test_task_ids={task.task_id}, session_manager=session_manager)
    with pytest.raises(runtime.InfrastructureUnavailable):
        agent.run()
    assert agent.last_result is None
