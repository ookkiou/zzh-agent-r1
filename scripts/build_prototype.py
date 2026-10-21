"""Reproduce the 20 authored prototype fixtures; --check detects any drift."""

import argparse
import ast
import hashlib
import json
from pathlib import Path
import textwrap

ROOT = Path(__file__).resolve().parents[1]
TASKS = []


def add(name, title, instruction, reference, old, new, bug_type, public, private, split):
    reference = textwrap.dedent(reference).lstrip()
    if reference.count(old) != 1:
        raise ValueError(f"Mutation must identify one location: {name}")
    starter = reference.replace(old, new, 1)
    ast.parse(starter)
    TASKS.append(dict(name=name, title=title, instruction=instruction,
                      reference=reference, starter=starter, bug_type=bug_type,
                      public=public, private=private, split=split))


add("count_at_least", "统计达到阈值的元素", "输入整数列表 values 和整数 threshold，返回大于或等于阈值的元素数量；空列表返回 0。", '''
def count_at_least(values, threshold):
    return sum(value >= threshold for value in values)
''', "value >= threshold", "value > threshold", "boundary",
    [([[2, 3, 4], 3], 2), ([[], 5], 0)],
    [([[1], 1], 1), ([[0, 0], 0], 2), ([[-3, -2, -1], -2], 2),
     ([[5, 6], 2], 2), ([[1, 2], 3], 0), ([[7, 7, 8, 6], 7], 3)], "train")

add("valid_port", "校验服务端口", "输入整数 port，当且仅当 1 <= port <= 65535 时返回布尔 True，否则返回布尔 False。", '''
def valid_port(port):
    return 1 <= port <= 65535
''', "1 <= port", "0 <= port", "boundary",
    [([0], False), ([8080], True)],
    [([1], True), ([65535], True), ([65536], False), ([-1], False),
     ([0], False), ([443], True)], "train")

add("ticket_category", "按年龄划分票种", "输入 0 至 120 的整数 age；年龄达到 18 岁返回字符串 adult，未达到返回 child。", '''
def ticket_category(age):
    return "adult" if age >= 18 else "child"
''', "age >= 18", "age > 18", "boundary",
    [([18], "adult"), ([10], "child")],
    [([0], "child"), ([17], "child"), ([18], "adult"), ([19], "adult"),
     ([65], "adult"), ([120], "adult")], "dev")

add("within_limit", "检查额度是否足够", "输入非负整数 amount 和 limit；amount 不超过 limit 时返回布尔 True，包括相等的情况，否则返回 False。", '''
def within_limit(amount, limit):
    return amount <= limit
''', "amount <= limit", "amount < limit", "boundary",
    [([10, 10], True), ([11, 10], False)],
    [([0, 0], True), ([0, 1], True), ([1, 0], False), ([5, 5], True),
     ([4, 5], True), ([100, 99], False)], "dev")

add("ranges_overlap", "判断闭区间交集", "输入整数 a_start、a_end、b_start、b_end，保证每段起点不大于终点。两个闭区间有公共点时返回布尔 True；只接触端点也算相交。", '''
def ranges_overlap(a_start, a_end, b_start, b_end):
    return max(a_start, b_start) <= min(a_end, b_end)
''', "<= min", "< min", "boundary",
    [([1, 3, 3, 5], True), ([1, 2, 4, 5], False)],
    [([0, 0, 0, 0], True), ([-3, -1, -1, 2], True), ([2, 4, 1, 2], True),
     ([1, 5, 2, 3], True), ([6, 8, 1, 5], False), ([1, 1, 2, 2], False)], "dev")

add("tail_items", "取列表末尾元素", "输入整数列表 items 和非负整数 n，返回最后 n 个元素组成的新列表；n 为 0 返回空列表，n 超过长度时返回整个列表。", '''
def tail_items(items, n):
    return items[-n:] if n else []
''', "items[-n:] if n else []", "items[-n:]", "index_slice",
    [([[1, 2, 3], 0], []), ([[1, 2, 3], 2], [2, 3])],
    [([[], 0], []), ([[], 4], []), ([[8], 0], []), ([[8], 1], [8]),
     ([[1, 2], 5], [1, 2]), ([[4, 5, 6], 1], [6])], "train")

add("middle_item", "取奇数长度列表中项", "输入非空、长度为奇数的整数列表 items，返回正中间的一个元素。", '''
def middle_item(items):
    return items[len(items) // 2]
''', "len(items) // 2", "len(items) // 2 + 1", "index_slice",
    [([[4, 5, 6]], 5), ([[9]], 9)],
    [([[0]], 0), ([[-3, -2, -1]], -2), ([[1, 2, 3, 4, 5]], 3),
     ([[7, 6, 5, 4, 3, 2, 1]], 4), ([[8, 8, 9]], 8), ([[1, 0, 2]], 0)], "train")

add("rotate_left", "循环左移列表", "输入整数列表 items 和非负整数 k，返回循环左移 k 位的新列表；允许 k 大于列表长度，空列表返回空列表。", '''
def rotate_left(items, k):
    if not items:
        return []
    offset = k % len(items)
    return items[offset:] + items[:offset]
''', "k % len(items)", "(k + 1) % len(items)", "index_slice",
    [([[1, 2, 3], 1], [2, 3, 1]), ([[], 7], [])],
    [([[1, 2, 3], 0], [1, 2, 3]), ([[1, 2, 3], 3], [1, 2, 3]),
     ([[1, 2, 3], 5], [3, 1, 2]), ([[9], 8], [9]),
     ([[1, 2, 3, 4], 2], [3, 4, 1, 2]), ([[-1, 0], 1], [0, -1])], "train")

add("every_other", "取偶数下标元素", "输入整数列表 items，返回下标 0、2、4 等位置的元素，保持顺序；空列表返回空列表。", '''
def every_other(items):
    return items[::2]
''', "items[::2]", "items[1::2]", "index_slice",
    [([[1, 2, 3, 4]], [1, 3]), ([[]], [])],
    [([[7]], [7]), ([[7, 8]], [7]), ([[0, 1, 2]], [0, 2]),
     ([[1, 2, 3, 4, 5]], [1, 3, 5]), ([[-2, -1, 0, 1]], [-2, 0]),
     ([[9, 9, 8, 8, 7, 7]], [9, 8, 7])], "dev")

add("prefix_items", "取列表前缀", "输入整数列表 items 和非负整数 n，返回前 n 个元素；n 为 0 返回空列表，n 超过长度时返回整个列表。", '''
def prefix_items(items, n):
    return items[:n]
''', "items[:n]", "items[:n - 1]", "index_slice",
    [([[1, 2, 3], 2], [1, 2]), ([[1, 2], 0], [])],
    [([[], 0], []), ([[8], 1], [8]), ([[1, 2], 2], [1, 2]),
     ([[1, 2], 5], [1, 2]), ([[3, 4, 5], 1], [3]), ([[9, 8, 7], 0], [])], "dev")

add("product", "计算整数连乘", "输入整数列表 values，返回所有元素的乘积；空列表的乘积定义为 1。", '''
def product(values):
    result = 1
    for value in values:
        result *= value
    return result
''', "result = 1", "result = 0", "initialization",
    [([[2, 3]], 6), ([[]], 1)],
    [([[5]], 5), ([[0, 3]], 0), ([[-2, 3]], -6), ([[-2, -3]], 6),
     ([[1, 1, 1]], 1), ([[2, 3, 4]], 24)], "train")

add("count_words", "统计空白分隔词数", "输入字符串 text，按任意连续空白字符分词，返回词数；空字符串或全空白字符串返回 0。", '''
def count_words(text):
    count = 0
    for word in text.split():
        count += 1
    return count
''', "count = 0", "count = 1", "initialization",
    [(["one two"], 2), ([""], 0)],
    [([" "], 0), (["hello"], 1), ([" a  b "], 2), (["a\tb\nc"], 3),
     (["你好 世界"], 2), (["a,b"], 1)], "train")

add("sum_positive", "累加正整数", "输入整数列表 values，只对严格大于 0 的元素求和；空列表或没有正数时返回 0。", '''
def sum_positive(values):
    total = 0
    for value in values:
        if value > 0:
            total += value
    return total
''', "total = 0", "total = 1", "initialization",
    [([[-1, 0, 2, 3]], 5), ([[]], 0)],
    [([[-5]], 0), ([[0, 0]], 0), ([[1]], 1), ([[2, 2, 2]], 6),
     ([[-3, 4, -2, 6]], 10), ([[10, -10]], 10)], "dev")

add("max_value", "求非空列表最大值", "输入非空整数列表 values，返回最大元素；必须正确处理所有元素均为负数的列表。", '''
def max_value(values):
    result = values[0]
    for value in values:
        if value > result:
            result = value
    return result
''', "result = values[0]", "result = 0", "initialization",
    [([[-5, -2, -8]], -2), ([[1, 4, 2]], 4)],
    [([[-1]], -1), ([[-9, -3]], -3), ([[0]], 0), ([[7]], 7),
     ([[-4, 0, -1]], 0), ([[3, 3, 2]], 3)], "dev")

add("count_runs", "统计相邻相同元素分段数", "输入整数列表 items，每一段连续相等元素算一段，返回段数；例如 [1,1,2,1] 有 3 段，空列表为 0 段。", '''
def count_runs(items):
    if not items:
        return 0
    count = 1
    for previous, current in zip(items, items[1:]):
        if previous != current:
            count += 1
    return count
''', "count = 1", "count = 0", "initialization",
    [([[1, 1, 2, 1]], 3), ([[]], 0)],
    [([[9]], 1), ([[2, 2, 2]], 1), ([[1, 2, 3]], 3),
     ([[0, 0, 1, 1, 0, 0]], 3), ([[-1, -1, -2]], 2), ([[1, 2, 1, 2]], 4)], "dev")

add("is_leap_year", "判断公历闰年", "输入 1 至 9999 的整数 year。能被 400 整除，或能被 4 整除但不能被 100 整除的年份为闰年，返回布尔值。", '''
def is_leap_year(year):
    if year % 400 == 0:
        return True
    return year % 4 == 0 and year % 100 != 0
''', "    if year % 400 == 0:\n        return True\n", "", "missing_branch",
    [([2000], True), ([1900], False)],
    [([1600], True), ([2400], True), ([2024], True), ([2023], False),
     ([2100], False), ([1], False)], "train")

add("safe_divide", "安全除法", "输入整数 numerator 和 denominator。分母为 0 返回 None，否则返回 Python / 运算产生的浮点结果。", '''
def safe_divide(numerator, denominator):
    if denominator == 0:
        return None
    return numerator / denominator
''', "    if denominator == 0:\n        return None\n", "", "missing_branch",
    [([4, 0], None), ([5, 2], 2.5)],
    [([0, 0], None), ([-3, 0], None), ([0, 3], 0.0), ([6, 2], 3.0),
     ([-6, 2], -3.0), ([4, -2], -2.0)], "train")

add("shipping_cost", "按订单金额计算运费", "输入非负整数 total。金额为 0 表示空订单，运费为 0；金额达到 100 免运费；其余订单运费为 10。返回整数。", '''
def shipping_cost(total):
    if total == 0:
        return 0
    if total >= 100:
        return 0
    return 10
''', "    if total == 0:\n        return 0\n", "", "missing_branch",
    [([0], 0), ([50], 10)],
    [([0], 0), ([1], 10), ([99], 10), ([100], 0), ([101], 0), ([1000], 0)], "train")

add("parse_bool", "解析布尔字符串", "输入字符串 text，先去掉两端空白并转小写。true/yes/1 返回布尔 True；false/no/0 返回布尔 False；其他值返回 None。", '''
def parse_bool(text):
    value = text.strip().lower()
    if value in ("true", "yes", "1"):
        return True
    if value in ("false", "no", "0"):
        return False
    return None
''', "    if value in (\"false\", \"no\", \"0\"):\n        return False\n", "", "missing_branch",
    [(["false"], False), (["YES"], True)],
    [([" no "], False), (["0"], False), (["FALSE"], False), ([" true "], True),
     (["1"], True), (["maybe"], None), ([""], None)], "dev")

add("unique_in_order", "按首次出现顺序去重", "输入整数列表 items，返回每个不同整数首次出现时组成的新列表，保持原顺序；空列表返回空列表。", '''
def unique_in_order(items):
    result = []
    seen = set()
    for item in items:
        if item not in seen:
            result.append(item)
            seen.add(item)
    return result
''', "        if item not in seen:\n            result.append(item)\n            seen.add(item)\n",
    "        result.append(item)\n        seen.add(item)\n", "missing_branch",
    [([[1, 2, 1, 3]], [1, 2, 3]), ([[]], [])],
    [([[1, 1, 1]], [1]), ([[0, 0, -1, 0]], [0, -1]), ([[3, 2, 1]], [3, 2, 1]),
     ([[-2, -2, -1, -2]], [-2, -1]), ([[7]], [7]), ([[2, 1, 2, 1, 3]], [2, 1, 3])], "dev")


def dumps(value):
    return json.dumps(value, ensure_ascii=False, indent=2) + "\n"


def public_module(task):
    lines = ["\"\"\"Visible debugging tests; private acceptance cases are not included.\"\"\"",
             "import unittest", f"from solution import {task['name']}", "", "",
             "class PublicTests(unittest.TestCase):"]
    for index, (args, expected) in enumerate(task["public"], 1):
        lines.extend([f"    def test_public_{index:02d}(self):",
                      f"        actual = {task['name']}(*{args!r})",
                      f"        expected = {expected!r}",
                      "        self.assertIs(type(actual), type(expected))",
                      "        self.assertEqual(actual, expected)", ""])
    lines.extend(["", "if __name__ == '__main__':", "    unittest.main()", ""])
    return "\n".join(lines)


def build_resources():
    files, tasks = {}, []
    for index, task in enumerate(TASKS, 1):
        task_id = f"repair-{index:03d}"
        relative = f"{task['split']}/{task_id}"
        entry = ast.parse(task["reference"]).body[0]
        metadata = dict(schema_version=1, task_id=task_id,
                        source_id=f"authored-prototype-{index:03d}", split=task["split"],
                        title=task["title"], instruction=task["instruction"],
                        entrypoint=task["name"], signature=f"{task['name']}({ast.unparse(entry.args)})",
                        bug_type=task["bug_type"],
                        readable_files=["solution.py", "public_tests.py"],
                        writable_files=["solution.py"],
                        provenance={"kind": "repository_authored_prototype", "version": "0.1.0"},
                        public_case_count=len(task["public"]), private_case_count=len(task["private"]))
        cases = [{"id": f"private-{i:02d}", "args": args, "expected": expected}
                 for i, (args, expected) in enumerate(task["private"], 1)]
        files[f"{relative}/task.json"] = dumps(metadata)
        files[f"{relative}/starter/solution.py"] = task["starter"]
        files[f"{relative}/reference/solution.py"] = task["reference"]
        files[f"{relative}/public_tests.py"] = public_module(task)
        files[f"{relative}/private_tests.json"] = dumps(cases)
        tasks.append({"task_id": task_id, "path": relative})
    manifest = dict(schema_version=1, name="code-repair-prototype", version="0.1.0",
                    purpose="development fixtures, not a final evaluation benchmark",
                    tasks=tasks, files={path: hashlib.sha256(content.encode()).hexdigest()
                                        for path, content in sorted(files.items())})
    files["manifest.json"] = dumps(manifest)
    return files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    output = ROOT / "data/prototype"
    resources = build_resources()
    problems = []
    for relative, content in resources.items():
        path = output / relative
        if path.exists():
            if path.read_text() != content:
                problems.append(f"changed: {relative}")
        elif args.check:
            problems.append(f"missing: {relative}")
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content)
    if problems:
        print("\n".join(problems))
        return 1
    print(f"{'Checked' if args.check else 'Built'} {len(TASKS)} tasks / {len(resources)} files")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
