# 第八天：完整 dev 基线与自建多轮 GRPO 小试车

日期：2026-10-15。状态：**已完成，14/14 项验收通过。**本文件说明执行方法，实际结果见 [DAY8_RESULTS.md](DAY8_RESULTS.md) 与 [day8_acceptance.json](../reports/day8_acceptance.json)。

## 目标

第七天完成了真实环境接入和小样本诊断，发现原模型工具输出不稳定，并完成 80 步 LoRA SFT 预热。第八天保存完整 Base / SFT-only dev 基线，并确认自建代码修复轨迹能通过 vLLM、AgentFlow、奖励汇总、GRPO 优势计算和优化器，最终得到可重载的 checkpoint。

5 次更新用于验证链路，不用于证明强化学习能提升泛化能力。正式训练及 SFT-only / SFT+GRPO 效果对照属于后续阶段。

## 评测协议先冻结

- 数据：冻结版本全部 32 个 dev 缺陷任务，来自 14 个来源；不运行最终 test 来源。
- 模型：固定 revision 的原始 Qwen2.5-Coder-1.5B-Instruct，以及第七天合并的 SFT-only checkpoint。
- 每个模型每题 seed 17 / 29 / 43，共 96 次单独 episode；两组总计 192 次。
- temperature=0.6、top_p=0.95。第七天 temperature=0.8 用于小规模探索诊断，两者应单独报告，不能混为同一评测。
- 每条最多 6 次决策，每次 prompt≤4096、response≤512；工具、提示词、模型观察编码和终局奖励保持冻结。
- Transformers SDPA BF16，顺序单 episode 生成；两种模型使用完全相同设置。
- 每次从原始缺陷恢复。主指标统计所有有效单次 episode，不能挑三个种子中最好的一个。
- 基础设施异常按同一 seed 最多重试 2 次；仍失败则保留未完成状态，不静默丢弃。

协议在 `runs/day8/evaluation_protocol.json`，SHA256 见 [day8_preparation.json](../reports/day8_preparation.json)。首次启动有一处任务 split 属性读取错误，在产生任何评测 episode 前已修正；启动错误保留在日志中，不计为模型失败。

## GRPO smoke 的范围

起点是第七天的 SFT-only 合并权重，reference 也使用该权重作为 KL 锚点。只使用已在第七天诊断过的 4 个 train 任务，循环 5 个 epochs，每个 epoch 一个 batch，严格限制 total_training_steps=5。此小数据循环不是正式数据规模或训练成绩。

train_batch_size=4 表示每次 4 道题；rollout.n=4 表示每题 4 条候选，因此每次收集 16 条轨迹，5 次共 80 条。每条包含最多 6 个模型生成 step，优化器输入不能误算成只有 16 个序列。

采样 temperature=0.8、top_p=0.95；其余协议与固定修复环境一致。单卡 BF16、learning rate=1e-6、micro batch=1、梯度 checkpoint、FSDP 参数和 optimizer offload。使用 actor KL loss，系数 0.001；环境奖励仍为终局 0/1，不重复加入 reward KL，不奖励格式或工具调用次数。

模型生成必须由真实 vLLM 驱动，模型自主决定工具顺序。真实候选始终通过鉴权 HTTP 和反向 SSH 隧道进入 Mac Docker 执行，不使用 trusted-local 执行生成代码。运行期间 Mac、Docker 和隧道需保持可用。

## 如何核验实际训练

自定义 `AuditedCodeRepairFlow` 沿用第七天的共享 episode runner，仅增加记录与断言。逐步保存真实 prompt/response token、工具反馈、终局摘要和生成 mask；上游 padding 后再次检查生成 token 未改写、生成 mask 为 1、padding 为 0。

`AuditedRayAgentTrainer` 在真实 `_update_actor` 前读取当前 batch，检查：

1. 每个同题分组恰好 4 条完整轨迹，不串题或删单条候选。
2. 环境与 trainer 的轨迹总奖励一致，只有最后一步可以有非零终局奖励。
3. 用轨迹总奖励计算的组内标准化优势与实际 `advantages` 张量一致，并广播到同轨迹每步生成 token；padding 不含优势。
4. 基础设施无效 episode 没有进入优化器。

检查后调用固定上游的优化器实现。上游源码本身不改写；运行入口从已校验的官方文件生成，只替换 observer 子类导入并指定绝对 Hydra 配置目录。原入口与扩展入口 SHA256、配置及 argv 保存在 `runs/day8/smoke/launch_train.json`。

预先运行的 `day8_credit_probe.py` 用合成张量调用真实上游 GRPO 函数，检查跨步骤优势、padding 和重复终局奖励拒绝；它不是训练结果。只有真实训练 batch 日志、更新指标和 checkpoint 验证齐备才算 smoke 通过。

## 本日验收标准

- Base 与 SFT-only 各覆盖全部 32 dev 任务、3 seeds，共 96 条有效轨迹，输出配对结果与完整轨迹。
- Hydra 配置解析成功，真实上游信用分配探针通过。
- 自建 recipe 完成恰好 5 次 GRPO 更新，损失和梯度有限、梯度非零。
- 5 个真实训练 batch 分组和奖励/优势检查通过；至少存在有相对奖励差异的分组。
- 真正的多轮 vLLM 工具轨迹参与更新，不能用脚本动作或单步 GSM8K 替代。
- 相对 **SFT-only 起点** 检查训练后权重变化，而不只与原始 Base 比较。
- 合并 checkpoint 并在 GPU 重新加载生成文本。
- 保存协议、配置、日志、评测/训练轨迹、模型位置和备份状态；冻结 test 来源未执行。

最后一项生成文本只证明 checkpoint 可加载，不等于模型修复能力提升。

## 运行入口

Mac 执行服务与隧道：

```bash
python3 scripts/day6_local_service.py start --dataset data/mbpp_repair/v0.1
python3 scripts/day6_tunnel.py start
```

远端项目在 `/root/autodl-tmp/agent-r1-day6`，由 `scripts/day8_control.py start --job baseline/config/smoke/checkpoint` 管理有时限的任务；`status --job ...` 只读状态。GPU 任务按基线 → smoke → checkpoint 顺序运行，不能并发占卡。

产物：`reports/day8_baseline_base.json`、`day8_baseline_sft.json`、`day8_credit_probe.json`、`day8_config_status.json`、`day8_smoke_status.json`、`day8_checkpoint_verification.json`。训练 batch 检查在 `runs/day8/smoke/training_batch_audit.jsonl`，原始模型轨迹在 `runs/day8/baseline/` 与 `runs/day8/smoke_traces/`。
