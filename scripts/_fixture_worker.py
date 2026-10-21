"""Execute repository-authored trusted fixtures only. NOT a security sandbox."""

import contextlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import unittest


def strict_equal(actual, expected):
    if type(actual) is not type(expected):
        return False
    if isinstance(expected, list):
        return len(actual) == len(expected) and all(
            strict_equal(a, b) for a, b in zip(actual, expected))
    if isinstance(expected, dict):
        return actual.keys() == expected.keys() and all(
            strict_equal(actual[key], value) for key, value in expected.items())
    return actual == expected


def main():
    mode, workspace, entrypoint = sys.argv[1:]
    workspace = Path(workspace)
    sys.path.insert(0, str(workspace))
    log = io.StringIO()
    with contextlib.redirect_stdout(log), contextlib.redirect_stderr(log):
        if mode == "public":
            suite = unittest.defaultTestLoader.discover(
                str(workspace), pattern="public_tests.py")
            result = unittest.TextTestRunner(stream=log).run(suite)
            report = {"completed": True, "tests": result.testsRun,
                      "passed": result.testsRun - len(result.failures) - len(result.errors),
                      "failed": len(result.failures) + len(result.errors),
                      "failures": [str(test) for test, _ in result.failures + result.errors]}
        elif mode == "private":
            cases = json.load(sys.stdin)
            spec = importlib.util.spec_from_file_location("solution", workspace / "solution.py")
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            function = getattr(module, entrypoint)
            failures = []
            for case in cases:
                try:
                    actual = function(*case["args"])
                    if not strict_equal(actual, case["expected"]):
                        failures.append({"id": case["id"], "reason": "wrong_result"})
                except Exception as error:
                    failures.append({"id": case["id"], "reason": type(error).__name__})
            report = {"completed": True, "tests": len(cases),
                      "passed": len(cases) - len(failures), "failed": len(failures),
                      "failures": failures}
        else:
            raise ValueError("unknown fixture mode")
    report["log"] = log.getvalue()[-2000:]
    print(json.dumps(report, ensure_ascii=False))


if __name__ == "__main__":
    main()
