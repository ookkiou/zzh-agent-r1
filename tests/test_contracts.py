import unittest

from code_repair.contracts import (
    ContractError, MAX_SOURCE_BYTES, TOOL_SCHEMAS, tool_result,
    validate_candidate_source, validate_tool_call,
)


class ContractTests(unittest.TestCase):
    def test_tools_accept_the_declared_arguments(self):
        for path in ("solution.py", "public_tests.py"):
            self.assertEqual(validate_tool_call("read_file", {"path": path}), {"path": path})
        self.assertEqual(validate_tool_call("run_tests", {}), {})
        validate_tool_call("write_file", {"path": "solution.py", "content": "def f(x):\n    return x\n"})

    def test_paths_cannot_escape_or_read_private_resources(self):
        for path in ("../solution.py", "/tmp/solution.py", "./solution.py",
                     "private_tests.json", "reference/solution.py", "solution.py/../task.json"):
            with self.subTest(path=path), self.assertRaises(ContractError):
                validate_tool_call("read_file", {"path": path})

    def test_public_tests_cannot_be_overwritten(self):
        with self.assertRaises(ContractError):
            validate_tool_call("write_file", {"path": "public_tests.py", "content": "pass"})

    def test_run_tests_cannot_accept_commands(self):
        with self.assertRaises(ContractError):
            validate_tool_call("run_tests", {"command": "python something.py"})

    def test_missing_unknown_and_non_object_arguments_fail(self):
        for name, arguments in (("run_bash", {}), (None, {}), ([], {}), ("read_file", {}),
                                ("read_file", {"path": "solution.py", "extra": True}),
                                ("run_tests", []), ("read_file", {"path": 1})):
            with self.subTest(name=name, arguments=arguments), self.assertRaises(ContractError):
                validate_tool_call(name, arguments)

    def test_source_budget_counts_utf8_bytes(self):
        for content in (" ", None, "x" * (MAX_SOURCE_BYTES + 1), "中" * 6000, "\ud800"):
            with self.subTest(content_type=type(content).__name__), self.assertRaises(ContractError):
                validate_tool_call("write_file", {"path": "solution.py", "content": content})

    def test_valid_body_change_preserves_signature(self):
        validate_candidate_source("def f(x, y=1):\n    return x + y\n",
                                  "def f(x, y=1):\n    return 0\n", "f")

    def test_renamed_missing_and_async_entries_are_rejected(self):
        for content in ("def g(x):\n    return x\n", "x = 1\n",
                        "async def f(x):\n    return x\n",
                        "def f(x):\n    return x\ndef f(x):\n    return 1\n"):
            with self.subTest(content=content), self.assertRaises(ContractError):
                validate_candidate_source(content, "def f(x):\n    return x\n", "f")

    def test_signature_and_syntax_changes_are_rejected(self):
        for content in ("def f(y):\n    return y\n", "def f(x=1):\n    return x\n",
                        "def f(x, y):\n    return x\n", "def f(x):\n    return (\n"):
            with self.subTest(content=content), self.assertRaises(ContractError):
                validate_candidate_source(content, "def f(x):\n    return x\n", "f")

    def test_response_envelope_does_not_mix_output_and_error(self):
        self.assertEqual(tool_result(ok=True, output="source"),
                         {"ok": True, "output": "source", "error": None})
        result = tool_result(ok=False, error_code="invalid_path", message="路径不可访问")
        self.assertIsNone(result["output"])
        self.assertEqual(result["error"]["code"], "invalid_path")
        for kwargs in ({"ok": 1}, {"ok": True, "error_code": "oops"},
                       {"ok": False, "error_code": "oops", "message": "bad", "output": 1},
                       {"ok": False, "error_code": "oops", "message": ""}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ContractError):
                tool_result(**kwargs)

    def test_schema_exposes_only_three_tools(self):
        names = {schema["function"]["name"] for schema in TOOL_SCHEMAS}
        self.assertEqual(names, {"read_file", "write_file", "run_tests"})


if __name__ == "__main__":
    unittest.main()
