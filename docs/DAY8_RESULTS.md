# 第八天实测结果：完整 dev 基线与真实多轮 GRPO 更新

日期：2026-10-15。**第八天验收通过，14/14 项检查通过。**

本日完成完整 Base / SFT-only dev 对照、自建代码修复 recipe 的 5 次 GRPO 更新、实际训练 batch 检查、相对 SFT 起点的权重比较及 GPU checkpoint 重载。正式 GRPO、独立 test 和 ZzhClaw 回接尚未完成。

总验收：[day8_acceptance.json](../reports/day8_acceptance.json)。执行与验收方法：[DAY8_RUNBOOK.md](DAY8_RUNBOOK.md)。

## 1. 完整开发集基线

评测覆盖全部 32 个 dev 缺陷任务，来自 14 个原始来源。每个模型每题 seed 17/29/43，96 条有效单次 episode；两组共 192 条，无基础设施失败或重试。

| 指标 | Base | SFT-only |
|---|---:|---:|
| 成功 / 有效单次轨迹 | 2/96 | 63/96 |
| 完整 dev 单次成功率 | 2.08% | 65.63% |
| 动作可解析率 | 56.01% | 100% |
| 工具契约合法率 | 50.32% | 100% |
| 生成 token 合计 | 28129 | 14078 |
| 有效覆盖率 | 100% | 100% |

配对结果：62 条仅 SFT 成功，1 条仅 Base 成功，1 条两者都成功，32 条两者都失败。因此不能说 SFT 在每个样本上都改善。

两组使用相同工具、提示词、公开反馈、终局私有验收和预算。temperature=0.6、top_p=0.95，每条最多 6 次决策，prompt≤4096、response≤512。第七天的 temperature=0.8 小样本是探索诊断，应单独报告。统计全部单次 episode，不挑三个种子中的最好结果；重复采样和同源变体不是独立题目。

这是当前冻结 dev 集上的 **SFT 前后观察**，没有测量 GRPO 后的 dev 提升，也不是最终独立测试成绩。SFT 标签来自 train 的修复源码及工具轨迹，未用 dev/test 标签。

证据：[完整配对报告](../reports/day8_baseline_comparison.json)、[冻结评测协议](../training/day8/evaluation_protocol.json)。192 条原始轨迹已备份到本机 `runs/day8/baseline/`。

## 2. 自建修复环境真正参与 GRPO

第七天使用 LoRA 做 SFT，再合并成完整模型。本日从该 SFT-only 合并权重开始，运行的是**全参数 GRPO smoke**，不是 LoRA GRPO，也不是官方 GSM8K 示例。只重复使用 4 个 train 任务，各题 n=4，每个更新 16 条自主轨迹，共 5 次更新、80 条轨迹。

所有 80 条都是实际 vLLM 生成的多轮工具轨迹，经过 Mac Docker 验收，再进入真实优化器。模型自行选择动作，没有教师脚本逐步指定工具或补丁。原模型生成 token 保留，工具观察进入下一轮 prompt，生成 mask=1、padding=0。

| 更新 | 整条 train episode 成功率 | 有差异的同题分组 / 4 | actor 梯度范数 | 原生 step 耗时 |
|---|---:|---:|---:|---:|
| 1 | 81.25% | 1/4 | 0.63949 | 171.6 秒 |
| 2 | 87.50% | 2/4 | 0.98917 | 98.9 秒 |
| 3 | 93.75% | 1/4 | 1.14563 | 102.2 秒 |
| 4 | 75.00% | 2/4 | 1.07862 | 101.0 秒 |
| 5 | 100.00% | 0/4 | 0.0001232 | 101.0 秒 |

5 次更新损失有限、梯度非零；20 个分组中有 6 个存在相对奖励信号。**第五次全 1，GRPO 策略优势为零、pg_loss=0，非零梯度来自 KL 正则项。**不能把这一次解释成有效的相对奖励学习，也不能把小训练集上的 100% 当作泛化提升。

实际更新前检查直接读取 trainer batch：同题分组完整，环境总奖励与 trainer 一致，终局奖励只计一次；实际优势张量等于轨迹总奖励的组内标准化结果，广播到同一轨迹的每个生成 step。检查后调用固定上游优化器实现，没有修改 GRPO 算法。

原生 5 个 step 总耗时约 574.7 秒，首步之后平均约 100.8 秒/update；这不含初始化、基线评测和导出。该速度只适用于本次 4 题、n=4 的配置，不能直接套到正式 batch=16 的训练上。

配置要点：单张 32GB GPU、BF16、learning rate=1e-6、micro batch=1、梯度 checkpoint、FSDP 参数/optimizer offload、actor KL loss 系数 0.001。单卡下 FSDP 自动使用 NO_SHARD，不能描述成多卡分布式训练。reference 使用相同 SFT 起点。

证据：[训练指标](../reports/day8_training_report.json)、[实际 Hydra 配置](../training/day8/resolved_config.yaml)、[启动配置与 argv](../training/day8/launch_train.json)。实际 batch 检查、原生 rollout 和 token 轨迹分别在本机 `runs/day8/smoke/training_batch_audit.jsonl`、`runs/day8/smoke/rollouts/`、`runs/day8/smoke_traces/`。

## 3. 参数变化与 checkpoint

以 **SFT-only 起点** 为参照核对 338 个张量：282 个张量、69350135 个元素变化，所有训练后权重数值有限。导出为 HF 模型后在 GPU 重新加载成功。另行验证了 BF16 重载后的权重差异仍然存在，避免只在存储精度上看到变化。

这证明自建修复训练链路和模型保存有效；重载时生成文本不能证明修复能力提升。

证据：[checkpoint 验收](../reports/day8_checkpoint_verification.json)、[模型文件 SHA256](../reports/day8_checkpoint_manifest.json)、[导出精度检查](../reports/day8_export_precision.json)。

## 4. 发现的真实问题

- Base 能偶尔修复，但动作格式不稳定：共有 139 次动作解析错误。必须把可解析、参数契约合法、源码写入成功、测试通过四件事分别统计。
- SFT-only 的动作契约合法率达到 100%，仍有 7 次源码写入被拒绝，说明合法 JSON 不等于有效补丁。
- `mbpp-526-m01 / seed17` 中，SFT 模型看到公开测试 0/2 通过后直接结束，私有验收只通过 2/7。工具链可用，不代表模型会根据反馈继续修复。
- `mbpp-548-m02 / seed43` 是退化样本：Base 成功，SFT 失败；SFT 公开测试 0/2，私有验收 3/7。因此必须保留逐题配对结果与失败轨迹。
- `critic/score/mean` 是 step 层面的平均分；整条 episode 应看 `critic/score/trajectory/mean` 或实际 batch 汇总，不能混用。
- 评测启动时修正了一处 split 元数据读取位置错误；训练启动前修正了 Hydra 对字典参数的解析方式。前者发生在任何评测样本产生前，后者发生在训练开始前，均不计作模型失败或训练更新。

## 5. 备份、停机与下一步

配置、报告、192 条 dev 轨迹、80 条训练轨迹、batch 检查和日志均已备份到本机；SHA256 记录见 [day8_backup.json](../reports/day8_backup.json)。第七天 LoRA adapter 的本机备份仍保留。

本日完整 checkpoint 与约 3.55GB 的合并权重仍在远端数据盘：

```text
/root/autodl-tmp/agent-r1-day6/runs/day8/smoke/global_step_5/actor
/root/autodl-tmp/agent-r1-day6/runs/day8/smoke/merged-step5
```

smoke 仅保存 model 和 extra 状态，没有 optimizer 状态，支持重新加载模型，不能声称精确续训优化器。当前 50GB 数据盘已用约 46GB，剩余约 4.4GB；正式实验前先整理可重建下载缓存或扩充存储，再配置完整续训状态与检查点保存预算。本次未删除已有模型 checkpoint。

GPU 作业全部退出，Mac 项目执行服务与反向隧道已停止，Docker 可以关闭。AutoDL 实例未停机或释放，可在控制台停机以结束本轮 GPU 计费。实际清理状态见 [day8_cleanup.json](../reports/day8_cleanup.json)。

下一步按第九至十天计划扩充经过验证的 train 数据，再根据实测吞吐安排有上限的正式 GRPO。正式效果比较需要 Base、SFT-only、SFT+GRPO；当前 5-update smoke 不替代正式实验、完整训练后 dev 对照或独立 test。
