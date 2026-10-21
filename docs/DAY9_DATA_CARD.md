# 第九天数据卡：MBPP repair v0.2

这是正式 GRPO 的训练数据扩充记录，数据验证结果不代表模型成功率。

| 项目 | v0.1 | v0.2 |
|---|---:|---:|
| train 缺陷任务 | 72 | 300 |
| train 原题来源 | 31 | 74 |
| dev 缺陷任务 | 32 | 32 |
| dev 原题来源 | 14 | 14 |
| 冻结 test 来源 | 50 | 原文件不变，未执行 |

v0.2 manifest SHA256：`37b846babd6d9949e2247752042c3669d618d0f367212b65ba32e39717da9555`。

## 构造与隔离

沿用已锁定的官方 MBPP 快照和原始来源划分，仅扩充原始 train 范围。新增 43 道经过代理审查的原题契约，每道编写 6 条回归用例，与上游用例合并后，每个任务保留 2 条公开测试、7 条私有验收用例。期望值按题意编写，再检查参考实现；没有把运行参考实现的输出直接当作独立期望值。

保留全部 104 个旧任务的五份资源，逐字节一致；dev 的模型初始消息、starter 和公开测试也与第七天导出一致。v0.1 本身未覆盖，50 个 test 来源冻结文件原样复制。仅对冻结 test 参考源码做静态去重特征比较，没有执行 test 参考实现、生成 test 任务或查看 test 成功率。

每个候选仅允许一个可定位的 AST 变更，独立 verifier 重放该变更。原有边界、索引、初始化、遗漏分支规则之外，增加算术、数值常量、布尔运算规则。候选必须完成执行，且同时触发公开和私有测试失败；超时、未完成或不满足单处变更的候选拒绝。参考实现必须通过全部测试。

按源码哈希和固定测试输入上的带类型返回值、异常记录去除重复变体。这只能排除已观测行为重复，不是程序语义等价证明。每个来源最多 8 个任务，保留旧 72 个 train 后，从 378 个合格新增候选按来源轮询选择 228 个；没有使用模型评测分数挑题。

源码按规范化 AST、常量抽象 AST 等规则与其他来源、dev、冻结 test 和原型题比较。首版独立复验发现 `mbpp-644` 与 `mbpp-610` 近重复；已归档并拒绝该版，修正为对所有非继承来源执行去重，包括此前审查过但未入选的来源。最终版不含 `mbpp-644`，审计记录见 [构建尝试](../reports/day9_build_attempts.json)。

## 缺陷分布

以下为 train + dev 共 332 个任务。

| 缺陷类型 | 数量 |
|---|---:|
| 索引 / 切片 | 78 |
| 边界判断 | 57 |
| 初始化 | 34 |
| 遗漏分支 | 38 |
| 算术运算 | 83 |
| 数值常量 | 29 |
| 布尔逻辑 | 13 |

## 验收证据

- [独立数据验证](../reports/day9_data_validation.json)：332/332，参考实现公开/私有全过，starter 公开/私有均有失败。
- [真实 Docker 验证](../reports/day9_docker_data_validation.json)：332/332，共 1328 次 HTTP → Docker 执行，没有模型参与。
- [离线重建检查](../reports/day9_reproducibility.json)：`build_mbpp_v2.py --check` 通过，冻结资源逐字节一致。
- [公开导出](../reports/day9_preparation.json)：997 个文件，仅含三种公开资源及 manifest；无参考实现、私有用例、mutation 定位信息。

GPU 上每题 `task.json` 仅含 `task_id/source_id/split/entrypoint/instruction`；模型只能看到题意、starter、公开测试和受限工具观察。此前第七天元数据中的 mutation 信息也未进入模型 prompt；本次进一步收紧了上传边界。

## 复现

```bash
python3 scripts/build_mbpp_v2.py --check
python3 scripts/verify_mbpp_v2.py
python3 scripts/day9_prepare.py
python3 -m unittest discover -s tests -p test_day9.py -v
```

以上 fixture 检查不调用模型。真实 Docker 复验还需启动 v0.2 执行服务后运行 `scripts/verify_day9_docker.py`；已通过且数据未修改时无需重复执行 1328 个容器。

## 适用范围

人工签字复核尚未完成，记录明确为 `agent_reviewed_not_human_signed_off`。300 个缺陷变体仅来自 74 个原题，样本相关，不能等同 300 个独立原题。任务仍是受限函数级合成缺陷，不代表真实多文件仓库修复或 ZzhClaw 的端到端能力。正式 GRPO 收益必须另做 SFT-only / SFT+GRPO 对照；最终 test 仍待独立阶段构建和冻结协议后运行。
