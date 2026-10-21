"""Shared tool schemas and validation. This module does not execute tools."""

import ast

READABLE_FILES = ("solution.py", "public_tests.py")
MAX_SOURCE_BYTES = 16_384

TOOL_SCHEMAS = [
    {"type": "function", "function": {
        "name": "read_file", "description": "读取当前任务的源码或公开测试。",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string", "enum": list(READABLE_FILES)}},
            "required": ["path"], "additionalProperties": False}}},
    {"type": "function", "function": {
        "name": "write_file", "description": "完整替换 solution.py，保留目标函数签名。",
        "parameters": {"type": "object", "properties": {
            "path": {"type": "string", "enum": ["solution.py"]},
            "content": {"type": "string", "minLength": 1}},
            "required": ["path", "content"], "additionalProperties": False}}},
    {"type": "function", "function": {
        "name": "run_tests", "description": "运行固定公开测试，返回结果与失败摘要。",
        "parameters": {"type": "object", "properties": {},
                       "additionalProperties": False}}},
]


class ContractError(ValueError):
    """A proposed tool action violates the code-repair contract."""


def validate_tool_call(name, arguments):
    """Validate arguments without accessing the filesystem or running code."""
    if not isinstance(name, str):
        raise ContractError("工具名称必须是字符串")
    if not isinstance(arguments, dict):
        raise ContractError("工具参数必须是对象")
    required = {"read_file": {"path"}, "write_file": {"path", "content"},
                "run_tests": set()}
    if name not in required:
        raise ContractError("未知工具")
    if set(arguments) != required[name]:
        raise ContractError("参数缺失或存在未声明的参数")
    if name in ("read_file", "write_file"):
        allowed = READABLE_FILES if name == "read_file" else ("solution.py",)
        path = arguments["path"]
        if not isinstance(path, str) or path not in allowed:
            raise ContractError("路径不在允许列表中")
    if name == "write_file":
        content = arguments["content"]
        if not isinstance(content, str) or not content.strip():
            raise ContractError("源码必须是非空字符串")
        try:
            size = len(content.encode("utf-8"))
        except UnicodeEncodeError as error:
            raise ContractError("源码必须是有效 UTF-8 文本") from error
        if size > MAX_SOURCE_BYTES:
            raise ContractError("源码超过 16384 UTF-8 字节")
    return dict(arguments)


def _entry(source, entrypoint):
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError) as error:
        raise ContractError("源码语法无效") from error
    entries = [node for node in tree.body
               if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
               and node.name == entrypoint]
    if len(entries) != 1 or isinstance(entries[0], ast.AsyncFunctionDef):
        raise ContractError("必须保留唯一的同步目标函数")
    return entries[0]


def validate_candidate_source(content, starter_source, entrypoint):
    """Check syntax and signature; this is not a code execution sandbox."""
    validate_tool_call("write_file", {"path": "solution.py", "content": content})
    candidate = _entry(content, entrypoint)
    original = _entry(starter_source, entrypoint)
    if ast.dump(candidate.args) != ast.dump(original.args):
        raise ContractError("目标函数参数签名发生变化")
    original_return = ast.dump(original.returns) if original.returns else None
    candidate_return = ast.dump(candidate.returns) if candidate.returns else None
    if original_return != candidate_return:
        raise ContractError("目标函数返回注解发生变化")


def tool_result(*, ok, output=None, error_code=None, message=None):
    """Stable envelope to be shared by later Agent-R1 and ZzhClaw adapters."""
    if type(ok) is not bool:
        raise ContractError("ok 必须是布尔值")
    if ok:
        if error_code is not None or message is not None:
            raise ContractError("成功响应不能包含错误")
        return {"ok": True, "output": output, "error": None}
    if output is not None or not isinstance(error_code, str) or not error_code:
        raise ContractError("失败响应必须包含错误代码且不能包含 output")
    if not isinstance(message, str) or not message:
        raise ContractError("失败响应必须包含错误说明")
    return {"ok": False, "output": None,
            "error": {"code": error_code, "message": message}}
