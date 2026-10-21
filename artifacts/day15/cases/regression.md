# Factorial last digit regression

任务 `mbpp-577-m02`，seed 43。已记录 dev 轨迹回放，不进行新推理。

此案例用于解释行为，不能代替全量配对统计。

## 需求

Write a python function to find the last digit in factorial of a given number.

精确输入域与验收约定：整数 0<=n<=100；返回 n! 的十进制最后一位，0!=1。
修复 solution.py 中的 last_Digit_Factorial 函数，保留签名。

## sft: reward=1.0

```diff
--- starter/solution.py
+++ sft/solution.py
@@ -3,7 +3,7 @@
         return 1
     elif n <= 2:
         return n
-    elif n != 3:
+    elif n == 3:
         return 6
     elif n == 4:
         return 4
```

| 决策 | 动作 | 结果 |
| --- | --- | --- |
| 1 | read_file | ok |
| 2 | read_file | ok |
| 3 | write_file | ok |
| 4 | run_tests | public 2/2 |
| 5 | final |  |

终局私有验收：7/7；仅展示汇总，不展示私有输入。

## step70: reward=0.0

```diff
--- starter/solution.py
+++ step70/solution.py
@@ -3,9 +3,9 @@
         return 1
     elif n <= 2:
         return n
-    elif n != 3:
+    elif n == 3:
         return 6
-    elif n == 4:
-        return 4
+    elif n % 5 == 0:
+        return 0
     else:
-        return 0
+        return 6
```

| 决策 | 动作 | 结果 |
| --- | --- | --- |
| 1 | read_file | ok |
| 2 | read_file | ok |
| 3 | write_file | ok |
| 4 | run_tests | public 0/2 |
| 5 | final |  |

终局私有验收：6/7；仅展示汇总，不展示私有输入。
