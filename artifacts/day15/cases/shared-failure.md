# Both miss the last-letter requirement

任务 `mbpp-526-m01`，seed 17。已记录 dev 轨迹回放，不进行新推理。

此案例用于解释行为，不能代替全量配对统计。

## 需求

Write a python function to capitalize first and last letters of each word of a given string.

精确输入域与验收约定：ASCII 单词字符串，允许空串和空白；按空白分词，以单个空格连接，首尾字母大写，其余字母小写。
修复 solution.py 中的 capitalize_first_last_letters 函数，保留签名。

## sft: reward=0.0

```diff
--- starter/solution.py
+++ sft/solution.py
@@ -2,5 +2,5 @@
     str1 = result = str1.title()
     result = ''
     for word in str1.split():
-        result += word[:-1 + 1] + word[-1].upper() + ' '
-    return result[:-1]
+        result += word[0].upper() + word[1:].lower() + ' '
+    return result[:-1] 
```

| 决策 | 动作 | 结果 |
| --- | --- | --- |
| 1 | read_file | ok |
| 2 | read_file | ok |
| 3 | write_file | ok |
| 4 | run_tests | public 0/2 |
| 5 | final |  |

终局私有验收：2/7；仅展示汇总，不展示私有输入。

## step70: reward=0.0

```diff
--- starter/solution.py
+++ step70/solution.py
@@ -2,5 +2,5 @@
     str1 = result = str1.title()
     result = ''
     for word in str1.split():
-        result += word[:-1 + 1] + word[-1].upper() + ' '
+        result += word[0].upper() + word[1:].lower() + ' '
     return result[:-1]
```

| 决策 | 动作 | 结果 |
| --- | --- | --- |
| 1 | read_file | ok |
| 2 | read_file | ok |
| 3 | write_file | ok |
| 4 | run_tests | public 0/2 |
| 5 | final |  |

终局私有验收：2/7；仅展示汇总，不展示私有输入。
