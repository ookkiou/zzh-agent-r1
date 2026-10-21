"""Static conversion, conservative deduplication and one-site AST mutations.

The source filter is a dataset eligibility check, NOT a security sandbox.
Only explicitly reviewed, known sources may use the local fixture backend.
"""

import ast
from collections import Counter
import copy
import difflib
import hashlib
import json
import math
import re

BUILTINS = frozenset("abs all any bool dict enumerate filter float int len list map max min pow range reversed round set sorted str sum tuple zip".split())
METHODS = frozenset("add append count extend get index intersection isdigit islower isupper items join keys lower pop replace reverse sort split strip title upper values".split())
FORBIDDEN = (ast.AsyncFunctionDef, ast.Await, ast.ClassDef, ast.Delete, ast.Global,
             ast.Nonlocal, ast.Import, ast.ImportFrom, ast.With, ast.AsyncWith,
             ast.Try, ast.Raise, ast.Yield, ast.YieldFrom)


def sha256(content):
    return hashlib.sha256(content.encode() if isinstance(content, str) else content).hexdigest()


def source_split(task_id):
    if 601 <= task_id <= 974:
        return "train"
    if 511 <= task_id <= 600:
        return "dev"
    if 11 <= task_id <= 510:
        return "test"
    if 1 <= task_id <= 10:
        return "prompt_only"
    raise ValueError("Unknown MBPP task ID")


def native_json(value):
    if type(value) in (str, int, bool, type(None)):
        return True
    if type(value) is float:
        return math.isfinite(value)
    if type(value) is list:
        return all(native_json(item) for item in value)
    if type(value) is dict:
        return all(type(key) is str and native_json(item) for key, item in value.items())
    return False


def inspect_source(source):
    tree = ast.parse(source)
    functions = [node for node in tree.body if isinstance(node, ast.FunctionDef)]
    if len(functions) != 1 or len(tree.body) != 1:
        raise ValueError("requires_one_top_level_function_without_imports")
    entry = functions[0]
    if entry.decorator_list or entry.returns or entry.args.defaults or entry.args.kw_defaults:
        raise ValueError("unsupported_signature")
    if entry.args.vararg or entry.args.kwarg or entry.args.kwonlyargs or entry.args.posonlyargs:
        raise ValueError("requires_positional_arguments")
    if any(arg.annotation for arg in entry.args.args):
        raise ValueError("unsupported_annotation")
    nodes = list(ast.walk(tree))
    if len(source.encode()) > 16384 or len(source.splitlines()) > 60 or len(nodes) > 600:
        raise ValueError("source_too_large")
    for node in nodes:
        if isinstance(node, FORBIDDEN):
            raise ValueError("unsupported_statement")
        if isinstance(node, ast.Attribute) and (node.attr not in METHODS or not isinstance(node.ctx, ast.Load)):
            raise ValueError("unsupported_attribute")
        if isinstance(node, ast.Name) and node.id.startswith("__"):
            raise ValueError("unsupported_dunder")
        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                if node.func.id not in BUILTINS | {entry.name}:
                    raise ValueError("unsupported_call")
            elif not isinstance(node.func, ast.Attribute):
                raise ValueError("unsupported_indirect_call")
    return entry.name, ast.unparse(tree) + "\n"


def parse_assertion(text, entrypoint):
    body = ast.parse(text).body
    if len(body) != 1 or not isinstance(body[0], ast.Assert):
        raise ValueError("requires_assert_statement")
    comparison = body[0].test
    if (not isinstance(comparison, ast.Compare) or len(comparison.ops) != 1
            or not isinstance(comparison.ops[0], ast.Eq)):
        raise ValueError("requires_literal_equality")
    call = comparison.left
    if (not isinstance(call, ast.Call) or not isinstance(call.func, ast.Name)
            or call.func.id != entrypoint or call.keywords):
        raise ValueError("requires_direct_positional_call")
    try:
        args = [ast.literal_eval(arg) for arg in call.args]
        expected = ast.literal_eval(comparison.comparators[0])
    except (ValueError, TypeError, SyntaxError) as error:
        raise ValueError("requires_literal_values") from error
    if not native_json(args) or not native_json(expected):
        raise ValueError("non_json_input_or_output")
    return {"args": args, "expected": expected}


def normalize_record(record):
    entrypoint, source = inspect_source(record["code"])
    if record.get("test_setup_code", "").strip():
        raise ValueError("requires_test_setup")
    cases = [parse_assertion(text, entrypoint) for text in record["test_list"]]
    if len(cases) < 3 or len({json.dumps(case["args"], sort_keys=True) for case in cases}) < 3:
        raise ValueError("requires_three_distinct_upstream_inputs")
    return {"source_id": f"mbpp-{record['task_id']:03d}", "upstream_task_id": record["task_id"],
            "split": source_split(record["task_id"]), "instruction": record["text"],
            "entrypoint": entrypoint, "reference": source, "upstream_cases": cases,
            "raw_code_sha256": sha256(record["code"]), "reference_sha256": sha256(source)}


class CanonicalNames(ast.NodeTransformer):
    def __init__(self, bound_names, abstract_constants=False):
        self.names = {}
        self.bound_names = bound_names
        self.abstract_constants = abstract_constants

    def identifier(self, name):
        if name in BUILTINS and name not in self.bound_names:
            return name
        if name not in self.names:
            self.names[name] = f"v{len(self.names)}"
        return self.names[name]

    def visit_FunctionDef(self, node):
        node.name = self.identifier(node.name)
        return self.generic_visit(node)

    def visit_arg(self, node):
        node.arg = self.identifier(node.arg)
        return node

    def visit_Name(self, node):
        node.id = self.identifier(node.id)
        return node

    def visit_Constant(self, node):
        if self.abstract_constants:
            node.value = f"constant:{type(node.value).__name__}"
        return node


def canonical(source, *, abstract_constants=False):
    tree = ast.parse(source)
    bound = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store)}
    bound.update(node.arg for node in ast.walk(tree) if isinstance(node, ast.arg))
    bound.update(node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef))
    tree = CanonicalNames(bound, abstract_constants).visit(tree)
    return ast.dump(tree, annotate_fields=True, include_attributes=False)


def source_features(source):
    exact = canonical(source)
    shape = canonical(source, abstract_constants=True)
    tokens = tuple(re.findall(r"[\w:]+|[^\s\w]", shape))
    return {"normalized_sha256": sha256(exact), "shape_sha256": sha256(shape), "tokens": tokens}


def near_duplicate(left, right, threshold=0.92):
    if left["normalized_sha256"] == right["normalized_sha256"]:
        return "normalized_ast"
    if left["shape_sha256"] == right["shape_sha256"]:
        return "constant_abstracted_ast"
    a, b = left["tokens"], right["tokens"]
    if 2 * min(len(a), len(b)) / (len(a) + len(b)) < threshold:
        return None
    overlap = sum((Counter(a) & Counter(b)).values())
    if 2 * overlap / (len(a) + len(b)) < threshold:
        return None
    matcher = difflib.SequenceMatcher(None, a, b, autojunk=False)
    if matcher.quick_ratio() >= threshold and matcher.ratio() >= threshold:
        return "ast_token_similarity"
    return None


def walk_paths(node, path=()):
    yield path, node
    for field, value in ast.iter_fields(node):
        if isinstance(value, ast.AST):
            yield from walk_paths(value, path + (field,))
        elif isinstance(value, list):
            for index, item in enumerate(value):
                if isinstance(item, ast.AST):
                    yield from walk_paths(item, path + (field, index))


def replace_at(tree, path, replacement):
    parent = tree
    for part in path[:-1]:
        parent = parent[part] if isinstance(part, int) else getattr(parent, part)
    if isinstance(path[-1], int):
        parent[path[-1]] = replacement
    else:
        setattr(parent, path[-1], replacement)


def mutations(source):
    """Each candidate changes exactly one explicitly addressed AST location."""
    tree = ast.parse(source)
    candidates, seen = [], set()
    comparison_map = {ast.Lt: ast.LtE, ast.LtE: ast.Lt, ast.Gt: ast.GtE,
                      ast.GtE: ast.Gt, ast.Eq: ast.NotEq, ast.NotEq: ast.Eq}

    def emit(path, node, replacement, kind):
        changed = copy.deepcopy(tree)
        replace_at(changed, path, ast.copy_location(replacement, node))
        result = ast.unparse(ast.fix_missing_locations(changed)) + "\n"
        if result == source or result in seen:
            return
        seen.add(result)
        location = tree
        for part in path:
            value = location[part] if isinstance(part, int) else getattr(location, part)
            if isinstance(value, ast.AST) and hasattr(value, "lineno"):
                located = value
            location = value
        candidates.append({"source": result, "bug_type": kind, "mutation": {
            "ast_path": list(path), "line": located.lineno,
            "column": located.col_offset, "before": ast.dump(node),
            "after": ast.dump(replacement), "single_location": True}})

    for path, node in walk_paths(tree):
        if isinstance(node, ast.Compare):
            for index, operation in enumerate(node.ops):
                if type(operation) in comparison_map:
                    emit(path + ("ops", index), operation, comparison_map[type(operation)](), "boundary")
        if isinstance(node, ast.Assign) and isinstance(node.value, ast.Constant):
            if type(node.value.value) is int and node.value.value in (0, 1):
                emit(path + ("value",), node.value, ast.Constant(1 - node.value.value), "initialization")
        if isinstance(node, (ast.If, ast.IfExp)) and not isinstance(node.test, ast.Constant):
            emit(path + ("test",), node.test, ast.Constant(False), "missing_branch")
        if isinstance(node, ast.Subscript):
            if isinstance(node.slice, ast.Slice):
                for field in ("lower", "upper"):
                    value = getattr(node.slice, field)
                    if value is not None:
                        for operation in (ast.Add, ast.Sub):
                            emit(path + ("slice", field), value,
                                 ast.BinOp(copy.deepcopy(value), operation(), ast.Constant(1)), "index_slice")
            else:
                emit(path + ("slice",), node.slice,
                     ast.BinOp(copy.deepcopy(node.slice), ast.Add(), ast.Constant(1)), "index_slice")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "range":
            # Preserve the step: perturb only the exclusive stop bound.
            index = 0 if len(node.args) == 1 else 1
            if len(node.args) in (1, 2, 3):
                value = node.args[index]
                for operation in (ast.Add, ast.Sub):
                    emit(path + ("args", index), value,
                         ast.BinOp(copy.deepcopy(value), operation(), ast.Constant(1)), "index_slice")
    return candidates


def render_public_tests(entrypoint, cases):
    lines = ["import unittest", f"from solution import {entrypoint}", "", "class PublicTests(unittest.TestCase):"]
    for index, case in enumerate(cases, 1):
        lines.extend([f"    def test_public_{index:02d}(self):",
                      f"        actual = {entrypoint}(*{case['args']!r})",
                      f"        expected = {case['expected']!r}",
                      "        self.assertIs(type(actual), type(expected))",
                      "        self.assertEqual(actual, expected)", ""])
    return "\n".join(lines) + "\n"
