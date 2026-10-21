# 第七天实测结果：代码修复 recipe 与 SFT 预热

日期：2026-10-15。当天验收通过；已具备进入第八天完整基线与自建 GRPO 小试车的条件。

## 结论与范围

已接入固定版本 Agent-R1 的真实 AgentEnv、AgentFlow 和训练张量后处理，完成原模型 32 条自主代码修复轨迹。原模型全部奖励为 0，检查轨迹后发现工具调用和写入源码不稳定，按执行计划触发小规模 SFT 备选路线。80 步 LoRA 预热后，在相同任务、提示词、工具、种子、采样参数与预算下再次完成 32 条自主轨迹；train 的 4 个同题分组中有 2 组出现不同奖励。

最终验收：[day7_sft_acceptance.json](../reports/day7_sft_acceptance.json)，10 项执行检查全部通过，`complete=true`、`ready_for_grpo_smoke=true`。原模型阶段报告 [day7_acceptance.json](../reports/day7_acceptance.json) 保留原始失败状态：运行完成，但没有学习信号，`complete=false`。后者并非整个第七天的最终结论。

**本日没有代码修复 GRPO 更新。**观察到的是 SFT 后的小样本变化，不能写成强化学习提升，也不能把这些数字当作完整开发集或独立测试集成绩。

## 实际完成的工作

| 环节 | 验证结果 |
|---|---|
| 服务器与依赖 | 同一 AutoDL 32GB 实例，RTX 4080 SUPER；Linux GPU 体检 8/8 通过 |
| 本地适配 | 13 项回归检查通过；已知补丁的 16 次真实 Docker 往返奖励正确 |
| 实际训练张量路径 | 真实上游 `_postprocess`：3 步脚本轨迹，生成 token mask=1、padding=0，工具观察只进入下一轮 prompt |
| 原模型自主诊断 | 4 train + 4 dev 来源，每题 4 个种子，共 32 条有效轨迹；无逐步动作引导 |
| 教师数据 | 63 个 train 任务、27 个来源、315 个监督样本；63 条教师轨迹均通过 Docker 终局验收 |
| SFT 更新 | 恰好 80 次 LoRA optimizer 更新；损失和梯度有限，梯度非零 |
| 参数与 checkpoint | 28 个注意力 q_proj 张量发生变化；保存 adapter 和合并权重；合并 checkpoint 在 GPU 重载并生成文本 |
| SFT 后复测 | 固定原诊断协议，32/32 有效轨迹；train 2/4 个分组奖励有差异 |
| 数据冻结 | 6 个冻结数据构建文件 SHA256 不变；冻结 test 来源未训练、未执行 |

上游张量检查是脚本驱动，模型诊断使用 Transformers。两项证据相互补充，但还没有证明 vLLM 生成的真实多轮修复轨迹参与了 GRPO 参数更新；这属于第八天自建 smoke 的验收范围。

## 原模型与 SFT-only 对照

| 指标 | 原模型 train | SFT-only train | 原模型 dev | SFT-only dev |
|---|---:|---:|---:|---:|
| 成功轨迹 / 有效轨迹 | 0/16 | 12/16 | 0/16 | 12/16 |
| 诊断成功率 | 0% | 75% | 0% | 75% |
| JSON/动作可解析率 | 68.1% | 98.8% | 69.6% | 100% |
| 工具契约合法率 | 56.9% | 98.8% | 62.5% | 100% |
| 同题奖励有差异的分组 | 0/4 | 2/4 | 0/4 | 0/4 |

SFT-only 的 train 分组奖励如下；每组种子依次为 17、29、43、59。

| 任务 | 4 次采样奖励 | 有组内相对信号 |
|---|---|---|
| mbpp-602-m01 | 1、1、0、1 | 是 |
| mbpp-608-m01 | 1、1、1、1 | 否 |
| mbpp-610-m01 | 0、0、1、0 | 是 |
| mbpp-619-m01 | 1、1、1、1 | 否 |

同题全 1 仍然缺少本批次的相对信号。dev 仅用于诊断；不能把它拿来补充训练分组。这里每个 split 只有 4 个来源，且每题重复采样，不能当成 16 个独立任务，也不能据此推断大规模泛化效果。

详细记录：[原模型诊断](../reports/day7_model_diagnostics.json)、[SFT-only 诊断](../reports/day7_sft_diagnostics.json)。原始轨迹分别在 `runs/day7/diagnostic/` 与 `runs/day7/diagnostic_sft/`，保留生成文本、工具反馈和终局验收摘要。

## 遇到的问题与处理

原模型可读文件，但将 `<code>$output$</code>` 等占位符当作修复源码：37 次写入请求中没有成功写入，33 次被源码校验拒绝。还出现解释性散文、未知工具名和错误参数。基础设施正常，32 条轨迹均有效，不能把它们归类成服务故障，也不能通过伪造动作或发放格式奖励掩盖问题。

处理方式是保留这些失败轨迹与原模型基线，使用 train 成功工具轨迹做有明确上限的监督训练。预热后共 32 次写入请求，30 次成功，仍有 2 次源码拒绝；另有 1 次动作解析失败。后续仍需检查模型根据失败反馈继续修复的能力，而不只看能否生成合法 JSON。

## SFT 的数据边界与配置

监督来源仅为 train，排除了全部 8 个诊断来源。每条教师轨迹依次读取源码、读取公开测试、写入正确 train 修复、运行公开测试、结束。监督标签包含正确修复源码，所以此次训练同时教授工具使用和修复行为，不能称为纯格式 SFT。

原有公开资源上传包不含参考实现。此次单独的 SFT 监督包将 train 正确修复作为训练标签上传到可信训练进程；这些答案不进入候选代码的工具工作区。dev/test 答案未作为标签，私有测试仍只由 Mac Docker 验收服务持有。

LoRA rank=16、alpha=32、dropout=0.05、all-linear；BF16 基座，AdamW learning rate=1e-4，micro batch=1、梯度累积=4、最多 80 更新、进程时限 1200 秒。prompt≤4096、response≤512，仅 assistant 响应位置计算监督损失。315 个样本全部符合长度预算，无截断或排除。

配置：[sft_warmup.json](../training/day7/sft_warmup.json)。数据与实际更新：[day7_sft_data.json](../reports/day7_sft_data.json)、[day7_sft_warmup.json](../reports/day7_sft_warmup.json)。模型文件校验：[day7_sft_checkpoint_manifest.json](../reports/day7_sft_checkpoint_manifest.json)。

## 下一步与运行状态

第八天先完成完整 Base / SFT-only dev 基线，再运行自建代码修复 5-update GRPO smoke。需检查真实 vLLM 多轮轨迹、组内奖励、响应 mask、有限非零梯度、权重变化与 checkpoint 重载。正式训练后的收益必须比较 Base、SFT-only、SFT+GRPO。

本次 GPU 作业全部退出，Mac 执行服务和本项目 SSH 反向隧道已停止；Docker 可关闭。AutoDL 实例仍开机，需在控制台停机以结束 GPU 计费；此操作不同于释放/删除实例。合并权重与 adapter 保留在 `/root/autodl-tmp/agent-r1-day6/runs/day7/sft_warmup/`。

LoRA adapter 已完整备份到本机 `runs/day7/sft_warmup/adapter/`，3 个文件逐项 SHA256 与远端一致；见 [day7_sft_backup.json](../reports/day7_sft_backup.json)。该 adapter 必须配合固定 revision 的原始基座加载，不能单独作为完整模型使用。约 3GB 合并权重仍仅在远端数据盘，不得把 adapter 备份写成全部模型权重已迁移。
