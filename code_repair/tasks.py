"""Load trusted task assets without executing public tests or reference code."""

import ast
from dataclasses import dataclass
import json
from pathlib import Path

from .contracts import validate_candidate_source


@dataclass(frozen=True)
class RepairTask:
    task_id: str
    instruction: str
    entrypoint: str
    starter_source: str
    public_test_source: str
    public_cases: tuple
    private_cases: tuple


def extract_public_cases(source, entrypoint):
    """Parse the fixture generator's literal test format, never eval test code."""
    cases = []
    for node in ast.walk(ast.parse(source)):
        if not isinstance(node, ast.FunctionDef) or not node.name.startswith("test_public_"):
            continue
        values = {}
        for statement in node.body:
            if isinstance(statement, ast.Assign) and len(statement.targets) == 1:
                target = statement.targets[0]
                if isinstance(target, ast.Name):
                    values[target.id] = statement.value
        call = values.get("actual")
        if (not isinstance(call, ast.Call) or not isinstance(call.func, ast.Name)
                or call.func.id != entrypoint or len(call.args) != 1 or call.keywords
                or not isinstance(call.args[0], ast.Starred) or "expected" not in values):
            raise ValueError("Unsupported public test format")
        args = ast.literal_eval(call.args[0].value)
        expected = ast.literal_eval(values["expected"])
        cases.append({"id": node.name, "args": args, "expected": expected})
    return cases


def load_task(task_dir, *, include_private=True):
    task_dir = Path(task_dir)
    names = ["task.json", "starter/solution.py", "public_tests.py"]
    if include_private:
        names.append("private_tests.json")
    paths = [task_dir / name for name in names]
    if any(path.is_symlink() for path in paths):
        raise ValueError("Task resources must be regular authored files")
    metadata = json.loads(paths[0].read_text(encoding="utf-8"))
    starter = paths[1].read_text(encoding="utf-8")
    public = paths[2].read_text(encoding="utf-8")
    entrypoint = metadata["entrypoint"]
    validate_candidate_source(starter, starter, entrypoint)
    public_cases = extract_public_cases(public, entrypoint)
    private_cases = json.loads(paths[3].read_text(encoding="utf-8")) if include_private else []
    groups = (public_cases, private_cases) if include_private else (public_cases,)
    for group in groups:
        if not isinstance(group, list) or not group:
            raise ValueError("Acceptance cannot contain zero cases")
        if len({case["id"] for case in group}) != len(group):
            raise ValueError("Case IDs must be unique")
        for case in group:
            if not isinstance(case["args"], list) or "expected" not in case:
                raise ValueError("Cases need args and expected")
        json.dumps(group, allow_nan=False)
    return RepairTask(metadata["task_id"], metadata["instruction"], entrypoint,
                      starter, public, tuple(public_cases), tuple(private_cases))
