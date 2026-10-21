# 第七天：接入代码修复 recipe 与少量自主模型诊断

更新日期：2026-10-15。

当前状态：**第七天验收完成。**原模型 32 条自主轨迹全部奖励为 0；80 步 LoRA SFT 预热后相同条件复测，train/dev 各 12/16 成功，train 2/4 组有奖励差异。最终结果见 [DAY7_RESULTS.md](DAY7_RESULTS.md) 与 [day7_sft_acceptance.json](../reports/day7_sft_acceptance.json)。尚未进行代码修复 GRPO 或完整 dev/test 评测。

## 今天要解决什么

第六天分别跑通了官方 GSM8K 参数更新和引导式代码修复工具调用。第七天接上自建 Agent-R1 接口，先测原始模型自主交互的格式、终局奖励和组内差异，不直接进行长时间 GRPO。

当天完成标准是：工具和环境接口可运行，实际模型轨迹与训练输入格式经过检查，有明确的协议/奖励诊断结果，并依据结果判断能否直接开始 RL，还是先需要格式 SFT。若同组奖励全部相同，不能只因代码检查通过就宣布已有可学习信号。

## 已完成的本地工作

| 项目 | 结果与证据 |
|---|---|
| 固定模型动作协议 | repair-json-v1，支持完整 JSON、单个 JSON 代码块和 Hermes；只接受 name/arguments 或显式 final |
| 契约与生成格式分离 | JSON 可解析率、工具契约合法率和工具执行成功分别统计；保留原始生成轨迹 |
| 真实 AgentEnv 适配 | `CodeRepairAgentEnv` 继承固定上游类并注册，不使用本地伪接口替代 |
| 自定义 AgentFlow | 与诊断脚本共享同一个 episode runner，每轮模型生成对应一个训练 step |
| 工具观察与 token mask | 模型响应保持原始 token；观察进入下一轮 prompt；仅生成 token 对应 response_mask=1；远端实际上游 padding 检查已通过 |
| 故障与清理 | 无效基础设施 episode 抛出异常，终止 rollout/batch，避免作为有效零奖励训练；异常和终止清理工作区 |
| 公开数据导出 | 104 个 train/dev 任务，只复制 task.json、starter/solution.py、public_tests.py；不复制参考源码和私有用例 |
| 诊断样本冻结 | 4 train + 4 dev，8 个不同来源；每题 4 次采样，种子 17/29/43/59，共 32 episodes |
| 适配器测试 | 13/13，无跳过；包括原始输出保留、格式拒绝、上下文预算和真实接口的鉴权 HTTP 检查 |
| 真实 Docker 往返 | 8 个已选任务，各跑错误原始代码与已知正确补丁，共 16 episodes；奖励为预期 0/1，工作区清理通过 |
| 上传包 | `runs/day7/day7-overlay.tar.gz`，全部归档字节校验通过；不含凭据、模型权重、参考源码或私有用例 |

本地验收：[day7_local_acceptance.json](../reports/day7_local_acceptance.json)。Docker 验收：[day7_docker_adapter.json](../reports/day7_docker_adapter.json)。公开导出：[day7_data_preparation.json](../reports/day7_data_preparation.json)。上传包记录：[day7_bundle.json](../reports/day7_bundle.json)。

Docker 检查由已知 train/dev 补丁驱动，没有调用模型，不能写成模型修复成功率。测试中的 trusted-local 后端仅用于已知人工 fixture；真实模型诊断始终使用远端鉴权客户端和 Mac Docker 服务。

## 接口设计的几个关键点

1. **工具顺序由模型决定。**诊断没有第六天的逐步工具指令，也没有指定正确补丁；初始提示固定后用于所有样本。只有明确的 `{"final":"..."}` 才表示模型主动结束，格式错误消耗一步并返回反馈。
2. **不能改写生成文本冒充模型动作。**原始输出留在 trace 和训练 response_ids；下一轮聊天内容仅去掉由聊天模板重新添加的末尾 EOS 边界，不把动作重写成另一套 token 序列。
3. **观察只进入下一轮 prompt。**每一轮的 response_ids 只来自生成端，mask 对这些 token 为 1；上游补齐后的 padding 为 0。远端探针已执行真实 `_postprocess` 核验，结果见 `reports/day7_trainer_contract.json`；该探针使用脚本动作，不能代替模型生成诊断。
4. **基础设施错误不参与训练。**当前方案是终止整个 rollout/batch，不是假设上游会识别一个随意添加的 sample_mask 字段。后续若要选择性重试或过滤，需要另行实现并检查组内样本一致性。
5. **达到上下文预算时不伪造模型回复。**自动终止对当前补丁做终局验收，将奖励归入最近一次真实生成 step；没有凭空添加一个带奖励的模型 token。
6. **控制面独立。**数据行的 env_kwargs 只允许 task_id。执行地址、token 路径和公开资源根目录来自可信环境配置，不接受样本覆盖。观察中不包含终局私有用例内容。

## 开机后的执行顺序

1. 用户提供当前 SSH 命令、GPU 型号和显存；若换实例，先迁移第六天系统盘和数据盘。上传包是已有第六天环境的增量，不能代替基础 torch、venv 或模型权重。
2. 连接后检查 GPU、驱动、Python、固定源码和模型文件路径；若更换显存或卡型，按实际配置检查兼容性。
3. 在 Mac 启动正式 train/dev Docker 服务，并按当前 SSH 信息建立反向隧道。凭据单独传到可信控制面，不能放进数据行或公开上传包。
4. 上传并验证 Day-7 overlay，在已有项目根目录解包。所有目标文件 SHA256 会在远端 preflight 再核对。
5. 执行远端 preflight：核心训练模块/CUDA 检查 → 公开 JSONL 转 parquet → 真实 Agent-R1 张量探针。任何一步失败均停止，不开始模型诊断。
6. 检查通过后运行有 1 小时进程上限的 32-episode 原始模型诊断。该上限是保护运行窗口，不是预估一定要用满一小时。
7. 保存原始轨迹、统计和失败分类，根据实际组内奖励差异做 RL/SFT 决策，再记录整天验收状态。

Mac 服务使用已验证命令：

```bash
python3 scripts/day6_local_service.py start --dataset data/mbpp_repair/v0.1
```

远端已有第六天项目目录 `/root/autodl-tmp/agent-r1-day6`，在隧道及 overlay 就绪后运行：

```bash
/root/autodl-tmp/agent-r1-day6/.venv/bin/python /root/autodl-tmp/agent-r1-day6/scripts/day7_remote_run.py preflight
/root/autodl-tmp/agent-r1-day6/.venv/bin/python /root/autodl-tmp/agent-r1-day6/scripts/day7_remote_run.py start-diagnostics
/root/autodl-tmp/agent-r1-day6/.venv/bin/python /root/autodl-tmp/agent-r1-day6/scripts/day7_remote_run.py status
```

上述入口已在本次 AutoDL 实例执行。原模型运行时的 overlay 已保留逐文件 SHA256；后来增加的 SFT 代码和监督数据另有 `runs/day7/sft_incremental_manifest.json`，不要将后续代码变更当作原 overlay 的原始字节。

## 远端实际要验证的内容

`day7_trainer_probe.py` 使用固定 tokenizer、真实自定义 Flow 和上游张量后处理，脚本驱动读取、测试、结束三步。检查 response_ids 与脚本生成 token 一致、观察只在下一轮 prompt、生成 mask 为 1、padding 为 0。它不加载模型计算动作，也不更新权重，不能替代真实模型行为诊断。

`day7_diagnose.py` 使用固定原始 Instruct 权重及 Transformers 生成后端，与 Flow 共享相同提示词、解析器和 episode runner。参数固定为 temperature=0.8、top_p=0.95、最多 6 次决策、prompt 4096 / response 512。逐步调用受限工具，终局使用 Mac 上的私有验收。该小样本用于诊断，不是第八天完整 dev baseline，也不是效果提升评测；训练用 vLLM 的采样路径仍需后续自建 smoke 检查。

产物计划：

- `reports/day7_remote_preflight.json`：Linux 依赖、公开 parquet 和真实 trainer 张量路径。
- `reports/day7_trainer_contract.json`：脚本轨迹的真实上游 mask 检查。
- `reports/day7_model_diagnostics.json`：合法动作、有效 episode、终局奖励和同题奖励差异。
- `runs/day7/diagnostic/`：按题目与种子保存真实模型原始输出和反馈。

## 什么情况下不能直接进入正式 GRPO

- 模型大多没有合法动作，或将工具结果当作自己输出；先定位格式和观察编码。
- 服务故障或超时占比明显；先修基础设施，不混为模型失败。
- 所有同题候选都得到同样奖励；检查任务、预算和探索，必要时考虑格式 SFT，并保留 SFT-only 对照。
- mask、奖励传递或真实多轮轨迹未验证；不能仅因已有 GSM8K 更新成功就跳过。

第七天没有代码修复 GRPO 更新；因原模型自主写入失败，已触发执行计划中的小规模 SFT 备选路线。63 个 train 任务来自 27 个来源，排除全部 8 个诊断来源；315 个监督样本均来自经 Docker 验证的成功教师轨迹。监督包含正确修复源码，不只是格式标签。此监督包单独上传到可信训练进程，参考源码不进入模型的工具工作区；私有测试始终留在 Mac 验收端。

SFT 配置见 `training/day7/sft_warmup.json`，实际更新与 GPU checkpoint 重载见 `reports/day7_sft_warmup.json`。原模型与 SFT-only 诊断的任务、提示词、工具、种子、采样参数和预算保持相同，结果分别保存在独立报告和轨迹目录，不能覆盖原模型的零成功结果。只有实际获得组内奖励差异，才进入第八天完整 Base/SFT-only dev 基线及自建 5-update GRPO smoke；第九至十天再决定正式 GRPO 范围。
