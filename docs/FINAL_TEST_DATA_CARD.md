# 独立 test 数据构建与 Docker 验收

2026-10-21。本阶段在 Mac 完成，使用 CPU 和 Docker，无 GPU 模型推理。完整验收记录见 [本机验收](../reports/final_test_local_acceptance.json)。

## 目标与顺序

1. 根据冻结的 50 个原题来源审查函数契约，独立编写边界用例；先固定 step70 模型与构建规则。
2. 每个可验收来源选取一个单位置 AST 缺陷。按固定类别顺序，选择第一个在公开和私有用例上都能被捕获的候选；选择过程不使用模型表现。
3. 用独立验证器复查哈希、来源隔离、公开/私有用例隔离、单位置修改及 train/dev 未被修改。
4. 通过临时的独立 HTTP 服务调用真正的 Docker 容器，逐题运行正确实现与缺陷实现的公开/私有测试。
5. 验收后只导出说明、starter 和公开测试，并封存未来 GPU 评估的模型、任务、种子和参数。

## 本次结果

| 项目 | 已验证结果 |
|---|---|
| 冻结来源 | 50 个，不替换、不补入新来源 |
| 可验收 test | 42 个原题，各 1 个缺陷任务 |
| 排除 | 8 个，原因完整记录在 selection_report.json |
| 公开 / 私有用例 | 84 / 312 个 |
| Docker 执行 | 168 次，即 42 × 正确/缺陷 × 公开/私有 |
| 正确实现 | 42/42 的公开和私有验收均通过 |
| 缺陷实现 | 42/42 的公开和私有验收均检测到错误 |
| 确定性重建 | 逐字节一致 |
| 新加载边界测试 | 5 项通过 |
| 既有服务回归测试 | 12 项通过 |
| GPU 公开资源 | 127 个文件，不含参考实现、私有用例、缺陷元数据 |
| 最终模型 test | 尚未运行 |

模型成功率尚不存在。此处的 42/42 指已知正确/错误夹具的验收结果，不是模型修复成绩。

## 排除项

| 原题 | 排除理由 |
|---|---|
| mbpp-133 | 冻结缺陷生成器没有产生能被两组用例检出的有效缺陷 |
| mbpp-134 | 未定义重复 p 次的具体操作 |
| mbpp-172 | 合法字符串以 s 或 st 结束时参考实现越界 |
| mbpp-248 | 浮点调和和不适合冻结的严格类型/精确相等验收 |
| mbpp-327 | 示例将不满足三角不等式的输入称为等腰三角形 |
| mbpp-397 | 示例期望 float，但参考实现返回 int，与冻结比较器冲突 |
| mbpp-452 | 题述为亏损，参考实现与示例计算正利润 |
| mbpp-463 | 参考实现在合法最大乘积子数组边界上错误 |

排除在任何模型 test 运行之前完成，与 step70 成绩无关。契约状态为 agent_reviewed_not_human_signed_off，不冒充人工签字。

## 文件和复现命令

数据位于 data/mbpp_repair/test-v0.1，公开导出位于 runs/final_test/public_data；构建规则和后续模型评估协议位于 training/final_test。

在 Mac 项目目录执行：

~~~bash
cd /Users/zzh/Documents/ChatGPT/agent-r1
python3 scripts/build_final_test.py --check
python3 scripts/verify_final_test.py --static-only
python3 scripts/verify_final_test.py
python3 scripts/seal_final_test.py
python3 -m unittest discover -s tests -p test_final_test.py -v
~~~

第一次生成数据使用 build_final_test.py 不带 --check。数据或封存协议已经存在且内容变化时，脚本拒绝覆盖。

默认 train/dev 服务和加载器保持原样，仍拒绝 test；临时 Docker 验收使用显式 FinalTestRegistry，端口由系统动态分配并在验收后关闭。现有 8765 服务和隧道未被替换。未来模型 test 可以使用单独的 serve_final_test.py，默认仅绑定 127.0.0.1:8766；它要求已封存协议和环境中的私密 token，本阶段没有启动该持久服务。

## 之后的 GPU 评估

每个模型：42 题 × 种子 17、29、43 = 126 条单次轨迹；SFT-only 和 step70 合计 252 条。沿用 dev 的 Transformers SDPA BF16、temperature=0.6、top_p=0.95、最多 6 次决策等预算，不算 best-of-three/pass@3。

目前只生成了公开数据传输包 runs/final_test/final-test-public.tar.gz；GPU test 入口和运行步骤需在正式执行前准备并校验。本阶段未上传 test 数据、未启动 GPU test。

如实报告包含/排除来源、每个种子和来源的表现。相同原题的重复种子相关，不能当作 126 个独立原题。与本项目 train/dev 隔离不等于排除了预训练模型对公开 MBPP 的潜在接触。根据 test 再调参后，应另准备独立留出集支撑后续结论。
