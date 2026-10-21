# 第 13–14 天：ZzhClaw 回接结果与验收

2026-10-21，受限 CLI 代码修复 profile 的接入和迁移对照完成。`python3 scripts/check_day14.py` 的 **15/15 项通过，complete=true**。本阶段没有继续训练，也没有再次运行最终 test。

## 本阶段交付

将第 70 步 HF 模型通过 AutoDL vLLM 0.11.0 服务接回 Mac 上的 ZzhClaw。新增 `python -m zzhclaw repair`，实际使用 `CodeRepairAgent`、ZzhClaw 会话和结构化事件；冻结 benchmark 的批量驱动为 `scripts/run_zzhclaw_repair.py`。评估直接复用训练侧的 `RepairSession` / `run_trajectory` 和三个受限工具，并未改动冻结运行时。

本次交付是独立 CLI profile 和批量迁移评估入口；未切换通用 Agent 的工具集，也没有完成 CLI / TUI / Web 全界面或通用 ZzhClaw-Eval 任务类型的接入。不能据此声称模型已经能够自主修复任意真实仓库。

模型生成原始 JSON 动作，vLLM 负责 tokenize / token completions / detokenize，应用侧沿用训练解析器调度工具。这个选择保证提示、工具和反馈格式与训练一致，因此没有使用原生 Hermes 工具调用解析器。Mac 无需完整模型权重，实际候选代码经现有 Docker 服务执行；私有输入与期望值不进入模型。

## 同环境应用 dev 对照

32 个缺陷任务来自 14 道原题，每题 seeds 17 / 29 / 43，各模型 96 条单次有效 episode，不是 pass@3。

| 指标 | SFT-only | GRPO step70 |
| --- | ---: | ---: |
| 成功 / 有效 episode | 69/96 | 75/96 |
| 成功率 | 71.875% | 78.125% |
| seed17 | 23/32 | 24/32 |
| seed29 | 21/32 | 23/32 |
| seed43 | 25/32 | 28/32 |
| 模型决策总数 | 483 | 481 |
| prompt tokens（每次请求累加） | 490756 | 488353 |
| response tokens | 13968 | 14122 |
| 有效 episode 耗时合计 | 491.16 秒 | 467.51 秒 |
| 基础设施无效尝试 | 0 | 1 |
| 非法模型动作 | 0 | 1 |

step70 比 SFT 增加 **6.25 个百分点**；同题同 seed 配对改善 **9** 条、退化 **3** 条，其余 84 条相同。三个 seed 的成功数差值分别为 +1 / +2 / +3。该结果是在这份 dev 与受限应用协议上的观察；未做统计显著性检验，同源变体与重复 seeds 存在相关性。

token 数量反映每轮实际服务端 token IDs 的计数，prompt 统计包含重复发送的对话历史，不是独立上下文 token 数。耗时为 episode 计时，包含推理、HTTP 与工具执行，不含权重预检和模型服务冷启动；没有专门控制缓存/机器负载，不能把耗时差归因为 GRPO 的稳定性能收益。

## 与已有结果的关系

| 评估范围 | 后端 | SFT | step70 | 差值 |
| --- | --- | ---: | ---: | ---: |
| 原冻结 dev | Transformers SDPA BF16 | 63/96 | 72/96 | +9.375 pp |
| 独立最终 test | Transformers SDPA BF16 | 90/126 | 93/126 | +2.381 pp |
| 本次 ZzhClaw 应用 dev | vLLM 0.11.0 BF16 | 69/96 | 75/96 | +6.25 pp |

每行分别比较同环境的 SFT / step70，不能拿新后端 step70 的 75 与旧后端 SFT 的 63 相减。vLLM 与 Transformers 的数值实现、采样随机流与服务调度不同，未承诺逐字输出相同。应用 dev 仍是开发数据，不能替代独立 test。最终 test 使用 42 个原题来源，另外 8 个按模型无关规则排除；既有报告保留，不因应用结果修改测试结论。

## 遇到的问题与处理

1. **工具协议不同。** 普通 ZzhClaw 使用原生工具调用与完整工具集，而训练模型输出固定 JSON。通过显式受限 profile 调用共享 runner，保留三工具、工具反馈、6 次决策、4096/512 token 及 240 秒 episode 限制，普通 Agent 回归测试仍通过。
2. **模型输出文本和 EOS 的处理。** API 文本可能省略停止 token，因此从 vLLM 获取生成 token IDs，再调用 detokenize。每个 episode 的初始 prompt 必须匹配 GPU 离线 HF tokenizer 指纹；预算按实际 token 计数。
3. **SSH 隧道中断。** step70 完成 55 条后，第 56 条 detokenize 请求连接重置。只读检查确认 GPU 服务仍活跃，Mac 18000 监听已消失。用户恢复隧道后重跑原命令，保留 55 条有效结果并完成剩余 41 条；无效尝试完整保留，不按模型失败计分。
4. **模型失败照常保留。** step70 在 `mbpp-577-m01 / seed29` 有一次无法解析的动作，按冻结契约消耗决策，该 episode 最终奖励 0。API smoke 的另一例仅修改首字母、未修改尾字母，公开测试失败后仍结束；未通过改提示或补答案掩盖这些失败。

## 验收证据

- 冻结迁移协议：`training/integration/evaluation_protocol.json`，SHA256 `ae96b0f262c0facf3a034198e605ff50af852ceb49df6cd5d21809089cee2818`。
- ZzhClaw 新 profile / 原 Agent 回归 51 项通过，迁移结果计数与拒绝错误输入测试 4 项通过。
- 脚本 HTTP / Docker 验收：`reports/day13_local_profile_acceptance.json`；真实模型两题验收：`reports/day13_real_api_acceptance.json`。
- 原始应用 dev 逐步轨迹与补丁：`reports/day13_sft_dev.json`、`reports/day13_step70_dev.json`；应用会话位于 `runs/day13/sessions/`。
- 两模型服务身份与初始 prompt 指纹：`runs/day13/model-sft.json`、`model-step70.json`，包含在 GPU 上实际计算的完整导出权重 SHA256。
- 配对对照：`reports/day14_application_comparison.json`；最终验收：`reports/day14_acceptance.json`。
- 当前验收重新解析所有 192 条 episode 的原始模型文本、工具契约与终局奖励，核对有效覆盖、token 预算和原始报告哈希。此审查没有重新加载模型或重新哈希 FSDP 源权重。

## 后续范围

当前可以进入第 15 天：整理 README、训练曲线、正反案例、演示和可复现材料。受限 profile 交付完成不等于训练已达原 225 步目标：实际更新到 74 步后保护停止，采用 checkpoint70，71–74 未保存；优化器动量未保存。若追加训练至 225/255，需另建实验记录，并明确既有 test 已被查看。

完整权重仍主要保存在 AutoDL，Mac 完整备份未验收。本次结果整理可在本机完成，不再需要 GPU 计算；是否停止模型服务、关机或备份由用户后续操作，本次验收没有更改运行中的远端服务和实例。
